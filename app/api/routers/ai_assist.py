"""用户端「AI 援助」：可用状态与 SSE 流式对话（api.md §7.19–§7.20）。

硬约束：
- 配置在请求时读取环境变量；响应、日志、审计均不得输出 Key；
- 对话无状态、不落业务表，仅写一条 `audit_logs(action="ai_assist.chat")` 元数据；
- 上游在产生正文前失败且已声明联网工具时，自动降级为不带 `tools` 的一次重试。
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from dataclasses import dataclass
from datetime import datetime
from typing import AsyncIterator, Optional

import httpx
from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.api import deps
from app.api.deps import get_db, require_user
from app.api.errors import (
    AI_UNAVAILABLE,
    INVALID_REQUEST,
    NOT_FOUND,
    RATE_LIMITED,
    BizError,
    current_request_id,
    envelope,
)
from app.api.schemas import AiAssistStatusOut, AiChatRequest
from app.db.models import AuditLog, Subject

logger = logging.getLogger("app.api")

router = APIRouter(prefix="/api/user/ai-assist", tags=["user-ai-assist"])

#: 固定合规文案（api.md §7.20 meta.disclaimer）。
DISCLAIMER = "目前测试版本的回答基于公开网络信息，仅供参考，不构成专业建议"
DISABLED_NOTICE = "智能援助暂未开通，请联系工作人员"
WEB_SEARCH_UNAVAILABLE = {
    "code": "web_search_unavailable",
    "message": "本次回答未启用联网搜索",
}
KEEPALIVE_SECONDS = 15
MAX_TOTAL_CHARS = 12000

SYSTEM_PROMPT = (
    "你是社区矫正对象的智能援助助手，只提供心理援助与法律援助方面的一般性信息。"
    "必须遵守以下规则："
    "1. 只回答心理援助与法律援助相关问题；超出范围时明确说明无法回答，并建议联系工作人员获取帮助；"
    "2. 不做医学诊断、不开具或推荐药物、不对任何行为定罪、不预测再次违法或再犯风险；"
    "3. 遇到自伤、伤人、自杀念头等紧急情形，立即建议联系工作人员，并拨打 120 或 110 寻求紧急帮助；"
    "4. 提醒用户不要输入身份证号、住址、案件细节等敏感信息；"
    "5. 如引用网络信息，必须给出真实可核查的来源，不得编造或猜测链接；"
    "6. 回答结尾固定附上「仅供参考，不构成专业建议」。"
    "回答使用简洁、平实的中文，不作价值评判。"
)


# ---- 配置 ----


@dataclass(frozen=True)
class _Config:
    api_key: str
    base_url: str
    model: str
    web_search: bool
    timeout_sec: float
    max_tokens: int


def _env_flag(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() not in {"0", "false", "no", "off"}


def _env_int(name: str, default: int) -> int:
    raw = (os.environ.get(name) or "").strip()
    try:
        value = int(raw)
    except ValueError:
        return default
    return value if value > 0 else default


def _env_float(name: str, default: float) -> float:
    raw = (os.environ.get(name) or "").strip()
    try:
        value = float(raw)
    except ValueError:
        return default
    return value if value > 0 else default


def _load_config() -> _Config:
    """运行时读取环境变量；Key 不落日志、不进响应。"""
    base_url = (os.environ.get("DEEPSEEK_BASE_URL") or "").strip()
    model = (os.environ.get("DEEPSEEK_MODEL") or "").strip()
    return _Config(
        api_key=(os.environ.get("DEEPSEEK_API_KEY") or "").strip(),
        base_url=(base_url or "https://api.deepseek.com").rstrip("/"),
        model=model or "deepseek-flash",
        web_search=_env_flag("DEEPSEEK_WEB_SEARCH_ENABLED", True),
        timeout_sec=_env_float("DEEPSEEK_TIMEOUT_SEC", 60.0),
        max_tokens=_env_int("DEEPSEEK_MAX_TOKENS", 800),
    )


def _build_client(timeout_sec: float) -> httpx.AsyncClient:
    """上游 HTTP 客户端工厂；测试可 monkeypatch 注入 MockTransport。"""
    return httpx.AsyncClient(timeout=httpx.Timeout(timeout_sec))


def _now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


# ---- 审计（新会话、失败吞掉） ----


def _write_audit(
    *,
    subject_id: str,
    request_id: str,
    model: Optional[str],
    web_search: bool,
    turns: int,
    status: str,
    degraded: list[str],
) -> None:
    """只写元数据；严禁写入用户原话、AI 回复、prompt 或上游响应体。"""
    detail = {
        "model": model,
        "web_search": web_search,
        "turns": turns,
        "status": status,
        "degraded": degraded,
    }
    try:
        factory = deps.get_session_factory()
        with factory() as session:
            session.add(
                AuditLog(
                    actor_type="subject",
                    actor_id=subject_id,
                    action="ai_assist.chat",
                    target_type="subject",
                    target_id=subject_id,
                    detail_json=json.dumps(detail, ensure_ascii=False),
                    request_id=request_id,
                    created_at=_now(),
                )
            )
            session.commit()
    except Exception as exc:  # noqa: BLE001 - 审计失败不得影响已发送的流
        logger.warning(
            "ai_assist.audit_failed request_id=%s exception_type=%s",
            request_id,
            type(exc).__name__,
        )


# ---- SSE 事件 ----


def _sse(event: str, payload: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"


_CITATION_CONTAINERS = ("annotations", "citations", "search_results")


def _iter_citation_candidates(chunk: dict, choice: dict, delta: dict):
    for container in (delta, choice, chunk):
        if not isinstance(container, dict):
            continue
        for key in _CITATION_CONTAINERS:
            value = container.get(key)
            if isinstance(value, list):
                for item in value:
                    yield item


def _normalize_citation(item) -> Optional[tuple[str, str]]:
    """仅接受同时带真实 title 与 http(s) url 的来源，绝不构造 URL。"""
    if not isinstance(item, dict):
        return None
    for node in (
        item,
        item.get("url_citation"),
        item.get("web_search"),
        item.get("source"),
    ):
        if not isinstance(node, dict):
            continue
        title = node.get("title")
        url = node.get("url")
        if not isinstance(title, str) or not title.strip():
            continue
        if not isinstance(url, str):
            continue
        url = url.strip()
        if not url.lower().startswith(("http://", "https://")):
            continue
        return title.strip(), url
    return None


def _parse_chunk(chunk: dict, state: dict) -> list[tuple[str, object]]:
    """把上游一个 SSE chunk 转为内部事件，并累积状态。"""
    items: list[tuple[str, object]] = []
    choices = chunk.get("choices")
    choice = choices[0] if isinstance(choices, list) and choices else {}
    if not isinstance(choice, dict):
        choice = {}
    delta = choice.get("delta")
    if not isinstance(delta, dict):
        delta = {}

    content = delta.get("content")
    if isinstance(content, str) and content:
        state["content_seen"] = True
        items.append(("delta", content))

    if delta.get("tool_calls") or choice.get("finish_reason") == "tool_calls":
        state["tool_calls"] = True

    finish_reason = choice.get("finish_reason")
    if isinstance(finish_reason, str) and finish_reason:
        state["finish_reason"] = finish_reason

    urls: set[str] = state.setdefault("citation_urls", set())
    for candidate in _iter_citation_candidates(chunk, choice, delta):
        normalized = _normalize_citation(candidate)
        if normalized is None:
            continue
        title, url = normalized
        if url in urls:
            continue
        urls.add(url)
        items.append(
            ("citation", {"index": len(urls), "title": title, "url": url})
        )
    return items


def _error_payload(state: dict, request_id: str) -> dict:
    """按契约映射错误码；不返回上游响应体。"""
    error = state.get("error")
    if isinstance(error, tuple) and error and error[0] == "http":
        status_code = error[1] if len(error) > 1 else 0
        if status_code == 429:
            return {
                "code": RATE_LIMITED,
                "message": "ai_rate_limited",
                "request_id": request_id,
            }
        if status_code in (401, 403):
            message = "ai_upstream_auth_failed"
        else:
            message = "ai_upstream_failed"
        return {"code": AI_UNAVAILABLE, "message": message, "request_id": request_id}
    if isinstance(error, tuple) and error and error[0] == "timeout":
        return {
            "code": AI_UNAVAILABLE,
            "message": "ai_upstream_timeout",
            "request_id": request_id,
        }
    return {
        "code": AI_UNAVAILABLE,
        "message": "ai_upstream_failed",
        "request_id": request_id,
    }


def _needs_fallback(state: dict) -> bool:
    """产生正文前失败或要求客户端执行工具，且没有任何正文时需降级/报错。"""
    if state.get("content_seen"):
        return False
    return bool(state.get("error") is not None or state.get("tool_calls"))


# ---- 上游调用 ----


def _build_payload(
    config: _Config, messages: list[tuple[str, str]], declare_tools: bool
) -> dict:
    payload = {
        "model": config.model,
        "stream": True,
        "thinking": {"type": "disabled"},
        "messages": [{"role": "system", "content": SYSTEM_PROMPT}]
        + [{"role": role, "content": content} for role, content in messages],
        "temperature": 0.3,
        "max_tokens": config.max_tokens,
    }
    # 绝不设置 tool_choice；是否联网由模型决定。
    if declare_tools:
        payload["tools"] = [{"type": "deepseek_web_search"}]
    return payload


async def _pump(
    config: _Config,
    messages: list[tuple[str, str]],
    declare_tools: bool,
    queue: asyncio.Queue,
    state: dict,
) -> None:
    """执行一次上游请求，把内部事件放入队列；异常只记类型。"""
    payload = _build_payload(config, messages, declare_tools)
    headers = {
        "Authorization": f"Bearer {config.api_key}",
        "Content-Type": "application/json",
        "Accept": "text/event-stream",
    }
    started = time.perf_counter()
    try:
        async with _build_client(config.timeout_sec) as client:
            async with client.stream(
                "POST",
                f"{config.base_url}/chat/completions",
                json=payload,
                headers=headers,
            ) as response:
                state["http_status"] = response.status_code
                if response.status_code >= 400:
                    state["error"] = ("http", response.status_code)
                    return
                async for line in response.aiter_lines():
                    line = line.strip()
                    if not line or line.startswith(":") or not line.startswith("data:"):
                        continue
                    data = line[5:].strip()
                    if data == "[DONE]":
                        state["done"] = True
                        return
                    try:
                        chunk = json.loads(data)
                    except ValueError:
                        continue
                    if not isinstance(chunk, dict):
                        continue
                    for item in _parse_chunk(chunk, state):
                        await queue.put(item)
    except asyncio.CancelledError:
        raise
    except httpx.TimeoutException:
        state["error"] = ("timeout",)
    except httpx.HTTPError:
        state["error"] = ("connect",)
    except Exception as exc:  # noqa: BLE001 - 只记类型，不记原文
        state["error"] = ("other",)
        logger.warning(
            "ai_assist.upstream_failed request_id=%s exception_type=%s",
            state.get("request_id", ""),
            type(exc).__name__,
        )
    finally:
        logger.info(
            "ai_assist.upstream request_id=%s http_status=%s elapsed_ms=%s",
            state.get("request_id", ""),
            state.get("http_status"),
            int((time.perf_counter() - started) * 1000),
        )
        try:
            queue.put_nowait(None)
        except Exception:  # noqa: BLE001
            pass


async def _attempt(
    config: _Config,
    messages: list[tuple[str, str]],
    declare_tools: bool,
    state: dict,
) -> AsyncIterator[tuple[str, object]]:
    """包装一次上游请求：空闲 15s 发 keep-alive，结束/取消时停止上游。"""
    queue: asyncio.Queue = asyncio.Queue()
    task = asyncio.create_task(_pump(config, messages, declare_tools, queue, state))
    try:
        while True:
            try:
                item = await asyncio.wait_for(queue.get(), KEEPALIVE_SECONDS)
            except asyncio.TimeoutError:
                yield ("keepalive", None)
                continue
            if item is None:
                break
            yield item
    finally:
        if not task.done():
            task.cancel()
        try:
            await task
        except BaseException:  # noqa: BLE001 - 含取消，交给外层处理
            pass


async def _relay(stream: AsyncIterator[tuple[str, object]]) -> AsyncIterator[str]:
    async for kind, value in stream:
        if kind == "delta":
            yield _sse("delta", {"text": value})
        elif kind == "citation":
            yield _sse("citation", value)  # type: ignore[arg-type]
        elif kind == "keepalive":
            yield ": keep-alive\n\n"


async def _event_stream(
    config: _Config,
    subject_id: str,
    messages: list[tuple[str, str]],
    request_id: str,
) -> AsyncIterator[str]:
    """meta →（notice/citation）→ delta… → done；异常发 error。"""
    turns = len(messages)
    # 默认视为客户端断连；正常结束、错误与未配置会在下方覆盖。
    status = "aborted"
    degraded: list[str] = []
    declare_tools = False
    try:
        if not config.api_key:
            status = "disabled"
            yield _sse(
                "notice",
                {"code": "ai_not_configured", "message": DISABLED_NOTICE},
            )
            yield _sse(
                "done",
                {
                    "finish_reason": "disabled",
                    "degraded": [],
                    "request_id": request_id,
                },
            )
            return

        declare_tools = config.web_search
        yield _sse(
            "meta",
            {
                "request_id": request_id,
                "model": config.model,
                "web_search": declare_tools,
                "disclaimer": DISCLAIMER,
            },
        )

        state: dict = {"request_id": request_id}
        async for chunk in _relay(_attempt(config, messages, declare_tools, state)):
            yield chunk

        if _needs_fallback(state) and declare_tools:
            # 声明了联网工具但上游不支持/不可达：降级为普通对话并提示。
            degraded.append("web_search")
            yield _sse("notice", dict(WEB_SEARCH_UNAVAILABLE))
            state = {"request_id": request_id}
            async for chunk in _relay(_attempt(config, messages, False, state)):
                yield chunk

        # 已产生正文后再失败不重试，只发 error；要求客户端执行工具也不算成功。
        if state.get("error") is not None or (
            state.get("tool_calls") and not state.get("content_seen")
        ):
            status = "error"
            yield _sse("error", _error_payload(state, request_id))
            return

        finish_reason = state.get("finish_reason") or "stop"
        status = "degraded" if degraded else "ok"
        yield _sse(
            "done",
            {
                "finish_reason": finish_reason,
                "degraded": degraded,
                "request_id": request_id,
            },
        )
    except (asyncio.CancelledError, GeneratorExit):
        status = "aborted"
        raise
    except Exception as exc:  # noqa: BLE001 - 流内兜底，不 500、不泄露原文
        status = "error"
        logger.warning(
            "ai_assist.stream_failed request_id=%s exception_type=%s",
            request_id,
            type(exc).__name__,
        )
        yield _sse(
            "error",
            {
                "code": AI_UNAVAILABLE,
                "message": "ai_upstream_failed",
                "request_id": request_id,
            },
        )
    finally:
        _write_audit(
            subject_id=subject_id,
            request_id=request_id,
            model=config.model if config.api_key else None,
            web_search=declare_tools and status != "disabled",
            turns=turns,
            status=status,
            degraded=degraded,
        )


# ---- 端点 ----


@router.get("/status")
def get_status(
    subject_id: str = Query(...),
    _role: str = Depends(require_user),
    db: Session = Depends(get_db),
) -> dict:
    """返回可用状态；无 Key 时中性提示，HTTP 200、code=0。"""
    if db.get(Subject, subject_id) is None:
        raise BizError(NOT_FOUND, "not_found")

    config = _load_config()
    enabled = bool(config.api_key)
    data = AiAssistStatusOut(
        enabled=enabled,
        web_search=enabled and config.web_search,
        model=config.model if enabled else None,
        notice=None if enabled else DISABLED_NOTICE,
    )
    return envelope(data=data.model_dump())


@router.post("/chat")
def chat(
    payload: AiChatRequest,
    _role: str = Depends(require_user),
    db: Session = Depends(get_db),
) -> StreamingResponse:
    """校验通过后开流；校验失败在开流前返回 JSON 信封。"""
    if db.get(Subject, payload.subject_id) is None:
        raise BizError(NOT_FOUND, "not_found")
    if payload.messages[-1].role != "user":
        raise BizError(INVALID_REQUEST, "invalid_request")
    if sum(len(item.content) for item in payload.messages) > MAX_TOTAL_CHARS:
        raise BizError(INVALID_REQUEST, "invalid_request")

    # 必须在返回 StreamingResponse 之前捕获，流内不依赖 contextvar。
    request_id = current_request_id()
    config = _load_config()
    messages = [(item.role, item.content) for item in payload.messages]

    return StreamingResponse(
        _event_stream(config, payload.subject_id, messages, request_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )
