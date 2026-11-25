"""AI 援助接口测试：状态、参数校验、SSE 流、降级与审计（api@1.5 §7.19-§7.20）。

上游一律使用 `httpx.MockTransport`，不真实联网。
"""

from __future__ import annotations

import json
import uuid

import httpx
import pytest
from sqlalchemy import select

from app.api import deps
from app.api.routers import ai_assist
from app.db.models import AuditLog, Subject

_SUBJECT_ID = "3b1e7c90-2f4a-4d51-8c6b-7d9e0f1a2b3c"
_CREATED_AT = "2026-11-25T10:12:03+08:00"
_UPDATED_AT = "2026-11-25T10:12:36+08:00"

_ENV_KEYS = (
    "DEEPSEEK_API_KEY",
    "DEEPSEEK_BASE_URL",
    "DEEPSEEK_MODEL",
    "DEEPSEEK_WEB_SEARCH_ENABLED",
    "DEEPSEEK_TIMEOUT_SEC",
    "DEEPSEEK_MAX_TOKENS",
)


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    """隔离外部环境，避免真实 Key 或开关渗入测试。"""
    for name in _ENV_KEYS:
        monkeypatch.delenv(name, raising=False)


@pytest.fixture()
def ai_client(client, db_factory, monkeypatch):
    """审计写入改走临时库，与请求级 Session 分离（契约要求新会话）。"""
    monkeypatch.setattr(deps, "get_session_factory", lambda: db_factory)
    return client


def _add_subject(db_factory, subject_id: str = _SUBJECT_ID) -> None:
    with db_factory() as db:
        db.add(
            Subject(
                id=subject_id,
                code=f"S{subject_id[:8]}",
                name="张某某",
                status="active",
                consent_json=None,
                baseline_json=None,
                created_at=_CREATED_AT,
                updated_at=_UPDATED_AT,
            )
        )
        db.commit()


def _install_transport(monkeypatch, handler):
    """把上游客户端替换为 MockTransport，并返回请求记录列表。"""
    requests: list[httpx.Request] = []

    def recording(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return handler(request)

    def factory(timeout_sec: float) -> httpx.AsyncClient:
        return httpx.AsyncClient(transport=httpx.MockTransport(recording))

    monkeypatch.setattr(ai_assist, "_build_client", factory)
    return requests


def _payload(request: httpx.Request) -> dict:
    return json.loads(request.content.decode("utf-8"))


def _upstream_stream(*chunks: dict) -> httpx.Response:
    body = "".join(
        f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n" for chunk in chunks
    )
    body += "data: [DONE]\n\n"
    return httpx.Response(
        200,
        content=body.encode("utf-8"),
        headers={"content-type": "text/event-stream"},
    )


def _content_chunk(text: str) -> dict:
    return {"choices": [{"index": 0, "delta": {"content": text}}]}


def _finish_chunk(reason: str = "stop") -> dict:
    return {"choices": [{"index": 0, "delta": {}, "finish_reason": reason}]}


def _broken_stream_response(text: str) -> httpx.Response:
    """先吐一个正文 chunk，再在读取中断开，模拟「已产生正文后失败」。"""

    class _Broken(httpx.AsyncByteStream):
        async def __aiter__(self):
            payload = json.dumps(_content_chunk(text), ensure_ascii=False)
            yield f"data: {payload}\n\n".encode("utf-8")
            raise httpx.ReadError("upstream broken")

    return httpx.Response(
        200,
        stream=_Broken(),
        headers={"content-type": "text/event-stream"},
    )


def _events(response) -> list[tuple[str, dict]]:
    """解析 SSE 响应；`: keep-alive` 等注释块无 event 名，自动跳过。"""
    events: list[tuple[str, dict]] = []
    for block in response.text.split("\n\n"):
        name = None
        payload = None
        for line in block.splitlines():
            if line.startswith("event: "):
                name = line[len("event: "):]
            elif line.startswith("data: "):
                payload = json.loads(line[len("data: "):])
        if name is not None:
            events.append((name, payload))
    return events


def _audit_logs(db_factory) -> list[AuditLog]:
    with db_factory() as db:
        return list(db.scalars(select(AuditLog)).all())


# ---- 状态 ----


def test_status_disabled_without_key(ai_client, db_factory, user_headers):
    _add_subject(db_factory)

    body = ai_client.get(
        "/api/user/ai-assist/status",
        params={"subject_id": _SUBJECT_ID},
        headers=user_headers,
    ).json()

    assert body["code"] == 0
    assert body["data"] == {
        "enabled": False,
        "web_search": False,
        "model": None,
        "notice": "智能援助暂未开通，请联系工作人员",
    }


def test_status_enabled_with_key(ai_client, db_factory, user_headers, monkeypatch):
    _add_subject(db_factory)
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test")

    body = ai_client.get(
        "/api/user/ai-assist/status",
        params={"subject_id": _SUBJECT_ID},
        headers=user_headers,
    ).json()

    assert body["code"] == 0
    assert body["data"] == {
        "enabled": True,
        "web_search": True,
        "model": "deepseek-flash",
        "notice": None,
    }


def test_status_unknown_subject(ai_client, user_headers):
    body = ai_client.get(
        "/api/user/ai-assist/status",
        params={"subject_id": _SUBJECT_ID},
        headers=user_headers,
    ).json()

    assert body["code"] == 1004
    assert body["message"] == "not_found"


# ---- 无 Key：notice + done，不请求上游 ----


def test_chat_without_key_returns_notice_and_done(
    ai_client, db_factory, user_headers, monkeypatch
):
    _add_subject(db_factory)

    def handler(request):  # pragma: no cover - 不应被调用
        raise AssertionError("未配置 Key 时不得请求上游")

    requests = _install_transport(monkeypatch, handler)

    response = ai_client.post(
        "/api/user/ai-assist/chat",
        json={"subject_id": _SUBJECT_ID, "messages": [{"role": "user", "content": "你好"}]},
        headers=user_headers,
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    events = _events(response)
    assert [name for name, _ in events] == ["notice", "done"]
    assert events[0][1]["code"] == "ai_not_configured"
    assert events[0][1]["message"] == "智能援助暂未开通，请联系工作人员"
    assert events[1][1]["degraded"] == []
    assert requests == []

    logs = _audit_logs(db_factory)
    assert len(logs) == 1
    detail = json.loads(logs[0].detail_json)
    assert detail["status"] == "disabled"
    assert detail["web_search"] is False
    assert detail["model"] is None


# ---- 参数校验（开流前 JSON 信封） ----


@pytest.mark.parametrize(
    "messages",
    [
        [],
        [{"role": "user", "content": "a"}, {"role": "assistant", "content": "b"}],
        [{"role": "user", "content": "x" * 2001}],
        # 11 条 × 1100 字 = 12100 > 12000（单条合规、条数合规）。
        [{"role": "user", "content": "x" * 1100} for _ in range(11)],
        [{"role": "system", "content": "x"}],
    ],
)
def test_chat_rejects_invalid_messages(
    ai_client, db_factory, user_headers, monkeypatch, messages
):
    _add_subject(db_factory)
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test")

    def handler(request):  # pragma: no cover - 不应被调用
        raise AssertionError("参数非法时不得请求上游")

    _install_transport(monkeypatch, handler)

    body = ai_client.post(
        "/api/user/ai-assist/chat",
        json={"subject_id": _SUBJECT_ID, "messages": messages},
        headers=user_headers,
    ).json()

    assert body["code"] == 1001
    assert body["message"] == "invalid_request"
    assert _audit_logs(db_factory) == []


def test_chat_unknown_subject(ai_client, db_factory, user_headers, monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test")

    body = ai_client.post(
        "/api/user/ai-assist/chat",
        json={
            "subject_id": str(uuid.uuid4()),
            "messages": [{"role": "user", "content": "你好"}],
        },
        headers=user_headers,
    ).json()

    assert body["code"] == 1004
    assert body["message"] == "not_found"


# ---- 正常流 ----


def test_chat_normal_stream(ai_client, db_factory, user_headers, monkeypatch):
    _add_subject(db_factory)
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test")

    def handler(request):
        return _upstream_stream(
            _content_chunk("你好"),
            _content_chunk("，世界"),
            _finish_chunk("stop"),
        )

    requests = _install_transport(monkeypatch, handler)

    response = ai_client.post(
        "/api/user/ai-assist/chat",
        json={
            "subject_id": _SUBJECT_ID,
            "messages": [{"role": "user", "content": "最近总是睡不着"}],
        },
        headers=user_headers,
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert response.headers["cache-control"] == "no-cache, no-transform"
    assert response.headers["x-accel-buffering"] == "no"

    events = _events(response)
    assert [name for name, _ in events] == ["meta", "delta", "delta", "done"]
    meta = events[0][1]
    assert meta["model"] == "deepseek-flash"
    assert meta["web_search"] is True
    assert meta["disclaimer"]
    assert meta["request_id"]
    assert events[1][1]["text"] + events[2][1]["text"] == "你好，世界"
    done = events[3][1]
    assert done["finish_reason"] == "stop"
    assert done["degraded"] == []
    assert done["request_id"] == meta["request_id"]

    assert len(requests) == 1
    request = requests[0]
    assert request.headers["authorization"] == "Bearer sk-test"
    body = _payload(request)
    assert body["model"] == "deepseek-flash"
    assert body["stream"] is True
    assert body["thinking"] == {"type": "disabled"}
    assert body["tools"] == [{"type": "deepseek_web_search"}]
    assert "tool_choice" not in body
    assert body["temperature"] == 0.3
    assert body["max_tokens"] == 800
    assert body["messages"][0]["role"] == "system"
    assert body["messages"][1] == {"role": "user", "content": "最近总是睡不着"}

    logs = _audit_logs(db_factory)
    assert len(logs) == 1
    log = logs[0]
    assert log.action == "ai_assist.chat"
    assert log.actor_type == "subject"
    assert log.actor_id == _SUBJECT_ID
    assert log.target_type == "subject"
    assert log.target_id == _SUBJECT_ID
    assert log.request_id == meta["request_id"]
    detail = json.loads(log.detail_json)
    assert detail == {
        "model": "deepseek-flash",
        "web_search": True,
        "turns": 1,
        "status": "ok",
        "degraded": [],
    }


# ---- 工具不支持：降级重试 ----


def test_chat_falls_back_without_tools(ai_client, db_factory, user_headers, monkeypatch):
    _add_subject(db_factory)
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test")

    def handler(request):
        if "tools" in _payload(request):
            return httpx.Response(400, json={"error": {"message": "tools unsupported"}})
        return _upstream_stream(_content_chunk("普通回答"), _finish_chunk("stop"))

    requests = _install_transport(monkeypatch, handler)

    response = ai_client.post(
        "/api/user/ai-assist/chat",
        json={
            "subject_id": _SUBJECT_ID,
            "messages": [{"role": "user", "content": "压力很大"}],
        },
        headers=user_headers,
    )

    assert response.status_code == 200
    events = _events(response)
    names = [name for name, _ in events]
    assert names[0] == "meta"
    assert names[-1] == "done"
    assert "notice" in names
    notice = next(payload for name, payload in events if name == "notice")
    assert notice == {"code": "web_search_unavailable", "message": "本次回答未启用联网搜索"}
    text = "".join(payload["text"] for name, payload in events if name == "delta")
    assert text == "普通回答"
    done = events[-1][1]
    assert "web_search" in done["degraded"]

    assert len(requests) == 2
    assert "tools" in _payload(requests[0])
    second = _payload(requests[1])
    assert "tools" not in second
    assert second["thinking"] == {"type": "disabled"}
    assert "tool_choice" not in second

    logs = _audit_logs(db_factory)
    assert len(logs) == 1
    detail = json.loads(logs[0].detail_json)
    assert detail["status"] == "degraded"
    assert detail["degraded"] == ["web_search"]
    assert detail["web_search"] is True


# ---- 上游错误映射 ----


def test_chat_rate_limited(ai_client, db_factory, user_headers, monkeypatch):
    _add_subject(db_factory)
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test")
    monkeypatch.setenv("DEEPSEEK_WEB_SEARCH_ENABLED", "0")

    def handler(request):
        return httpx.Response(429, json={"error": {"message": "rate limited"}})

    _install_transport(monkeypatch, handler)

    response = ai_client.post(
        "/api/user/ai-assist/chat",
        json={"subject_id": _SUBJECT_ID, "messages": [{"role": "user", "content": "你好"}]},
        headers=user_headers,
    )

    assert response.status_code == 200
    events = _events(response)
    assert events[-1][0] == "error"
    assert events[-1][1]["code"] == 1006
    assert events[-1][1]["message"] == "ai_rate_limited"
    meta = events[0][1]
    assert meta["web_search"] is False

    detail = json.loads(_audit_logs(db_factory)[0].detail_json)
    assert detail["status"] == "error"
    assert detail["web_search"] is False


def test_chat_upstream_timeout(ai_client, db_factory, user_headers, monkeypatch):
    _add_subject(db_factory)
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test")
    monkeypatch.setenv("DEEPSEEK_WEB_SEARCH_ENABLED", "0")

    def handler(request):
        raise httpx.ReadTimeout("upstream slow")

    _install_transport(monkeypatch, handler)

    response = ai_client.post(
        "/api/user/ai-assist/chat",
        json={"subject_id": _SUBJECT_ID, "messages": [{"role": "user", "content": "你好"}]},
        headers=user_headers,
    )

    assert response.status_code == 200
    events = _events(response)
    assert events[-1][0] == "error"
    assert events[-1][1]["code"] == 5001
    assert events[-1][1]["message"] == "ai_upstream_timeout"

    detail = json.loads(_audit_logs(db_factory)[0].detail_json)
    assert detail["status"] == "error"


def test_chat_error_after_content_does_not_retry(
    ai_client, db_factory, user_headers, monkeypatch
):
    """已产生正文后上游断开：只发 error，不降级重试。"""
    _add_subject(db_factory)
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test")

    requests = _install_transport(
        monkeypatch, lambda request: _broken_stream_response("已经说了一半")
    )

    response = ai_client.post(
        "/api/user/ai-assist/chat",
        json={"subject_id": _SUBJECT_ID, "messages": [{"role": "user", "content": "你好"}]},
        headers=user_headers,
    )

    assert response.status_code == 200
    events = _events(response)
    assert [name for name, _ in events] == ["meta", "delta", "error"]
    assert events[1][1]["text"] == "已经说了一半"
    assert events[2][1]["code"] == 5001
    assert events[2][1]["message"] == "ai_upstream_failed"
    assert len(requests) == 1

    detail = json.loads(_audit_logs(db_factory)[0].detail_json)
    assert detail["status"] == "error"


# ---- 审计不含正文 ----


def test_audit_detail_excludes_content(ai_client, db_factory, user_headers, monkeypatch):
    _add_subject(db_factory)
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test")

    user_text = "我最近总是失眠而且很焦虑"
    ai_text = "可以先尝试规律作息并联系工作人员"

    def handler(request):
        return _upstream_stream(_content_chunk(ai_text), _finish_chunk("stop"))

    _install_transport(monkeypatch, handler)

    response = ai_client.post(
        "/api/user/ai-assist/chat",
        json={
            "subject_id": _SUBJECT_ID,
            "messages": [
                {"role": "user", "content": user_text},
                {"role": "assistant", "content": "我在听"},
                {"role": "user", "content": "我该怎么办？"},
            ],
        },
        headers=user_headers,
    )

    assert response.status_code == 200
    logs = _audit_logs(db_factory)
    assert len(logs) == 1
    assert logs[0].action == "ai_assist.chat"
    assert set(json.loads(logs[0].detail_json)) == {
        "model",
        "web_search",
        "turns",
        "status",
        "degraded",
    }
    raw = logs[0].detail_json
    assert user_text not in raw
    assert "我该怎么办" not in raw
    assert ai_text not in raw
    assert json.loads(raw)["turns"] == 3
