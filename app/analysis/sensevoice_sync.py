"""思想汇报音频同步：SenseVoice 转写 + 情绪映射（严格模式，仅适配层脚手架）。

协议状态：SenseVoice 服务（默认 http://8.133.237.222:8000）当前不可达，情绪接口
协议尚未确认，因此情绪响应按防御式规则映射为 ``emotion@1.0``：只识别约定内的
``{"emotion": {...}}`` 与顶层 ``{primary, confidence, scores, triggers}``，其余
结构一律抛错，不做猜测。功能开关 ``SENSEVOICE_SYNC_ENABLED`` 默认关闭，由 API
层判断，本模块不读取该开关。

与 ``providers/sensevoice_asr.py`` 的关键差异：后者为保障分析管线可继续，HTTP
失败会回退 Mock；同步写库场景绝不能把占位文本冒充真实转写，因此本模块任何失败
都直接抛 ``SensevoiceSyncError``，绝不回退、绝不返回占位内容。

配置只从 ``os.environ`` 读取，不自动加载 ``.env``，与现有 Provider 保持一致。
日志只记录异常类型、耗时与 HTTP 状态码，不记录转写文本、密钥或音频绝对路径。
"""

from __future__ import annotations

import logging
import math
import os
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import httpx

logger = logging.getLogger(__name__)

ENV_ASR_URL = "SENSEVOICE_API_URL"
ENV_API_KEY = "SENSEVOICE_API_KEY"
ENV_EMOTION_URL = "SENSEVOICE_EMOTION_API_URL"

CODE_UNAVAILABLE = "sensevoice_unavailable"
CODE_TRANSCRIPTION_FAILED = "transcription_failed"
CODE_EMOTION_FAILED = "emotion_failed"

PROVIDER = "sensevoice"
DATA_VERSION_PREFIX = "sensevoice@1.0"
EMOTION_SCHEMA_VERSION = "emotion@1.0"

_ASR_FILENAME = "audio.wav"
_ASR_MIME = "audio/wav"


class SensevoiceSyncError(Exception):
    """同步失败的业务异常；``code`` 供 API 层直接映射错误码。"""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message

    def __str__(self) -> str:
        return f"{self.code}: {self.message}"


@dataclass(frozen=True)
class SensevoiceSyncResult:
    """一次同步的完整产物；媒体只保留路径，正文只有转写文本。"""

    provider: str
    transcript_text: str
    transcript_language: Optional[str]
    emotion: dict[str, Any]
    data_version: str


def _env(name: str) -> str:
    return (os.environ.get(name) or "").strip()


def sync_configured() -> bool:
    """三项配置齐全才认为同步可用；功能开关由 API 层判断。"""
    return bool(_env(ENV_ASR_URL) and _env(ENV_API_KEY) and _env(ENV_EMOTION_URL))


def _fail(code: str, message: str) -> SensevoiceSyncError:
    return SensevoiceSyncError(code, message)


def _log_failure(
    code: str, exc_type: str, status: object, started: float
) -> None:
    """只允许异常类型/耗时/HTTP 状态码，禁止敏感内容与绝对路径。"""
    logger.warning(
        "sensevoice sync failed code=%s exc=%s status=%s latency_ms=%d",
        code,
        exc_type,
        status,
        max(0, round((time.monotonic() - started) * 1000)),
    )


def _unit_float(value: Any) -> Optional[float]:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    if not math.isfinite(value) or value < 0 or value > 1:
        return None
    return float(value)


def _optional_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    if not math.isfinite(value):
        return None
    return float(value)


def _extract_transcript(payload: Any) -> tuple[str, Optional[str]]:
    """兼容 {"text": ...} 与 {"data": {"text": ...}}，空文本视为失败。"""
    if not isinstance(payload, dict):
        raise _fail(CODE_TRANSCRIPTION_FAILED, "asr response not an object")

    node: dict[str, Any] = payload
    top_text = payload.get("text")
    data = payload.get("data")
    if not isinstance(top_text, str) and isinstance(data, dict):
        node = data

    text = node.get("text")
    if not isinstance(text, str) or not text.strip():
        raise _fail(CODE_TRANSCRIPTION_FAILED, "asr returned empty text")

    language = node.get("language")
    if not isinstance(language, str) or not language.strip():
        language = node.get("lang")
    language = language.strip() if isinstance(language, str) and language.strip() else None
    return text.strip(), language


def _transcribe(path: Path, url: str, api_key: str, timeout: float) -> tuple[str, Optional[str]]:
    started = time.monotonic()
    try:
        with path.open("rb") as handle:
            response = httpx.post(
                url,
                files={"file": (_ASR_FILENAME, handle, _ASR_MIME)},
                headers={"Authorization": f"Bearer {api_key}"},
                timeout=timeout,
            )
    except OSError as exc:
        _log_failure(CODE_TRANSCRIPTION_FAILED, type(exc).__name__, None, started)
        raise _fail(CODE_TRANSCRIPTION_FAILED, "audio file unreadable") from None
    except httpx.HTTPError as exc:
        _log_failure(CODE_UNAVAILABLE, type(exc).__name__, None, started)
        raise _fail(CODE_UNAVAILABLE, "asr request failed") from None

    status = response.status_code
    if not 200 <= status < 300:
        _log_failure(CODE_UNAVAILABLE, "http_status", status, started)
        raise _fail(CODE_UNAVAILABLE, f"asr http status {status}")

    try:
        payload = response.json()
    except ValueError as exc:
        _log_failure(CODE_TRANSCRIPTION_FAILED, type(exc).__name__, status, started)
        raise _fail(CODE_TRANSCRIPTION_FAILED, "asr response not json") from None

    try:
        return _extract_transcript(payload)
    except SensevoiceSyncError:
        _log_failure(CODE_TRANSCRIPTION_FAILED, "unparsable_response", status, started)
        raise


def _emotion_body(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise _fail(CODE_EMOTION_FAILED, "emotion response not an object")
    inner = payload.get("emotion")
    if isinstance(inner, dict):
        return inner
    if any(key in payload for key in ("primary", "confidence", "scores")):
        return payload
    raise _fail(CODE_EMOTION_FAILED, "emotion response structure unknown")


def _normalize_triggers(raw: Any) -> list[dict[str, Any]]:
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise _fail(CODE_EMOTION_FAILED, "emotion triggers not a list")

    triggers: list[dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, dict):
            raise _fail(CODE_EMOTION_FAILED, "emotion trigger not an object")
        text = item.get("text")
        label = item.get("label")
        triggers.append(
            {
                "text": text if isinstance(text, str) else "",
                "label": label if isinstance(label, str) else "",
                "start_sec": _optional_float(
                    item.get("start_sec", item.get("start"))
                ),
                "end_sec": _optional_float(item.get("end_sec", item.get("end"))),
            }
        )
    return triggers


def _normalize_emotion(payload: Any) -> dict[str, Any]:
    """把未确认协议映射为 emotion@1.0，任何非法字段直接判 emotion_failed。"""
    body = _emotion_body(payload)

    raw_scores = body.get("scores")
    scores: dict[str, float] = {}
    if raw_scores is not None:
        if not isinstance(raw_scores, dict):
            raise _fail(CODE_EMOTION_FAILED, "emotion scores not an object")
        for label, value in raw_scores.items():
            score = _unit_float(value)
            if score is None:
                raise _fail(CODE_EMOTION_FAILED, "emotion score out of range")
            scores[str(label)] = score

    primary_raw = body.get("primary")
    primary = primary_raw.strip() if isinstance(primary_raw, str) else ""
    if not primary:
        if not scores:
            raise _fail(CODE_EMOTION_FAILED, "emotion primary missing")
        primary = max(scores, key=lambda label: scores[label])

    confidence_raw = body.get("confidence")
    provided: Optional[float] = None
    if confidence_raw is not None:
        provided = _unit_float(confidence_raw)
        if provided is None:
            raise _fail(CODE_EMOTION_FAILED, "emotion confidence invalid")

    # confidence 与 scores[primary] 强一致：有分数时以分数为准。
    if primary in scores:
        confidence = scores[primary]
    elif provided is not None:
        confidence = provided
        scores[primary] = confidence
    else:
        raise _fail(CODE_EMOTION_FAILED, "emotion confidence missing")

    triggers = _normalize_triggers(body.get("triggers"))
    return {
        "schema_version": EMOTION_SCHEMA_VERSION,
        "primary": primary,
        "confidence": confidence,
        "scores": scores,
        "triggers": triggers,
    }


def _analyze_emotion(text: str, url: str, api_key: str, timeout: float) -> dict[str, Any]:
    started = time.monotonic()
    try:
        response = httpx.post(
            url,
            json={"text": text},
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=timeout,
        )
    except httpx.HTTPError as exc:
        _log_failure(CODE_UNAVAILABLE, type(exc).__name__, None, started)
        raise _fail(CODE_UNAVAILABLE, "emotion request failed") from None

    status = response.status_code
    if not 200 <= status < 300:
        _log_failure(CODE_UNAVAILABLE, "http_status", status, started)
        raise _fail(CODE_UNAVAILABLE, f"emotion http status {status}")

    try:
        payload = response.json()
    except ValueError as exc:
        _log_failure(CODE_EMOTION_FAILED, type(exc).__name__, status, started)
        raise _fail(CODE_EMOTION_FAILED, "emotion response not json") from None

    try:
        return _normalize_emotion(payload)
    except SensevoiceSyncError:
        _log_failure(CODE_EMOTION_FAILED, "unparsable_response", status, started)
        raise


def _data_version(now: datetime) -> str:
    return f"{DATA_VERSION_PREFIX}+{now.strftime('%Y%m%dT%H%M%S')}"


def sync_report(
    audio_file: Path,
    *,
    timeout: float = 30.0,
    duration_sec: Optional[float] = None,
) -> SensevoiceSyncResult:
    """严格同步执行一次「转写 → 情绪」，失败即抛 ``SensevoiceSyncError``。

    ``duration_sec`` 仅作为调用方上下文保留（例如未来用于触发片段裁剪），当前
    不参与请求构造。``timeout`` 为单次 HTTP 请求的超时秒数。
    """
    path = Path(audio_file)
    if not path.is_file() or path.stat().st_size <= 0:
        raise _fail(CODE_TRANSCRIPTION_FAILED, "audio file missing or empty")

    asr_url = _env(ENV_ASR_URL)
    api_key = _env(ENV_API_KEY)
    emotion_url = _env(ENV_EMOTION_URL)
    if not (asr_url and api_key and emotion_url):
        raise _fail(CODE_UNAVAILABLE, "sensevoice sync not configured")

    transcript, language = _transcribe(path, asr_url, api_key, timeout)
    emotion = _analyze_emotion(transcript, emotion_url, api_key, timeout)

    return SensevoiceSyncResult(
        provider=PROVIDER,
        transcript_text=transcript,
        transcript_language=language,
        emotion=emotion,
        data_version=_data_version(datetime.now()),
    )


__all__ = [
    "SensevoiceSyncError",
    "SensevoiceSyncResult",
    "sync_configured",
    "sync_report",
]
