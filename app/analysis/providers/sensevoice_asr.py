"""SenseVoice 真实 ASR Provider：HTTP 失败时回退到确定性 Mock 并标记 degraded。

只从 os.environ 读取配置，不自动加载 .env，避免测试环境误触真实服务。
"""

from __future__ import annotations

import logging
import os
import re
import time
from pathlib import Path
from typing import Any

import httpx

from app.analysis.models import ProviderInput
from app.analysis.paths import resolve_session_file
from app.analysis.providers.mock_asr import MockAsrProvider, write_transcript

logger = logging.getLogger(__name__)

ENV_URL = "SENSEVOICE_API_URL"
ENV_KEY = "SENSEVOICE_API_KEY"
ENV_TIMEOUT = "SENSEVOICE_TIMEOUT_SEC"
# 云端 SenseVoice 需先经 ffmpeg 转码再推理，冷启动实测约 20s，默认给足超时。
DEFAULT_TIMEOUT_SEC = 120.0
TIMEOUT_SEC = DEFAULT_TIMEOUT_SEC

# SenseVoice 返回会内嵌 <|zh|><|NEUTRAL|><|Speech|><|withitn|> 之类的控制标签。
_TAG_PATTERN = re.compile(r"<\|[^|]*\|>")
_TAG_CAPTURE = re.compile(r"<\|([^|]+)\|>")

# SenseVoice 支持的情感标签；与 <|Speech|> 等音频事件标签区分开。
_EMOTION_LABELS = frozenset(
    {"NEUTRAL", "HAPPY", "SAD", "ANGRY", "FEARFUL", "DISGUSTED", "SURPRISED"}
)
_AUDIO_EVENTS = frozenset(
    {"SPEECH", "BGM", "APPLAUSE", "LAUGHTER", "CRYING", "COUGH", "SNEEZE"}
)


def sensevoice_timeout() -> float:
    """超时可经 SENSEVOICE_TIMEOUT_SEC 覆盖，非法值回落到默认值。"""
    raw = (os.environ.get(ENV_TIMEOUT) or "").strip()
    if not raw:
        return DEFAULT_TIMEOUT_SEC
    try:
        value = float(raw)
    except ValueError:
        return DEFAULT_TIMEOUT_SEC
    return value if value > 0 else DEFAULT_TIMEOUT_SEC


def sensevoice_settings() -> tuple[str, str]:
    """读取环境变量；URL 与 Key 任一缺失即视为未配置。"""
    url = (os.environ.get(ENV_URL) or "").strip()
    api_key = (os.environ.get(ENV_KEY) or "").strip()
    return url, api_key


def sensevoice_configured() -> bool:
    url, api_key = sensevoice_settings()
    return bool(url and api_key)


class SenseVoiceAsrProvider:
    name = "asr"
    version = "sensevoice-asr@1.0"

    def __init__(
        self, scenario: dict[str, Any], *, timeout: float | None = None
    ) -> None:
        self._scenario = scenario
        self._mock = MockAsrProvider(scenario)
        self._timeout = timeout if timeout is not None else sensevoice_timeout()
        # 本次成功识别时解析出的情绪标签；供 pipeline 传给 emotion 通道复用。
        self.last_emotion: dict[str, Any] | None = None

    def available(self) -> bool:
        return True

    def analyze(self, input: ProviderInput) -> dict[str, Any]:
        self.last_emotion = None
        if not input.audio_path:
            raise ValueError("audio_unavailable")

        url, api_key = sensevoice_settings()
        if not (url and api_key):
            return self._mock.analyze(input)

        started = time.monotonic()
        try:
            audio_file = resolve_session_file(
                Path(input.storage_root),
                input.subject_id,
                input.session_id,
                input.audio_path,
            )
            with audio_file.open("rb") as handle:
                response = httpx.post(
                    url,
                    # Cloud SenseVoice 服务端期望 multipart 字段名为 'audio'（不是 'file'）。
                    files={"audio": ("audio.wav", handle, "audio/wav")},
                    # Cloud SenseVoice 服务端使用 X-API-Key 头认证（不是 Authorization Bearer）。
                    headers={"X-API-Key": api_key},
                    timeout=self._timeout,
                )
            response.raise_for_status()
            payload = response.json()
            transcript = self._extract_text(payload)
            if not transcript:
                raise ValueError("sensevoice_empty_text")
            self.last_emotion = self._parse_emotion(payload)
        except httpx.HTTPStatusError as exc:
            # 记状态码（不记响应体，避免泄露密钥或返回文本）。
            logger.warning(
                "sensevoice http_error status=%s (%s), fallback to mock",
                exc.response.status_code,
                type(exc).__name__,
            )
            return self._fallback(input)
        except httpx.TimeoutException as exc:
            logger.warning(
                "sensevoice timeout (%s), fallback to mock",
                type(exc).__name__,
            )
            return self._fallback(input)
        except Exception as exc:
            logger.warning(
                "sensevoice request failed (%s), fallback to mock",
                type(exc).__name__,
            )
            return self._fallback(input)

        relative_path = write_transcript(input, transcript)
        return {
            "status": "ok",
            "output": {
                "transcript_path": relative_path,
                "duration_sec": float(input.duration_sec),
                "speech_ratio": float(input.speech_ratio),
                "char_count": len(transcript),
            },
            "confidence": self._scenario["confidence"][self.name],
            "latency_ms": max(0, round((time.monotonic() - started) * 1000)),
            "reason": None,
        }

    @staticmethod
    def _raw_text(payload: Any) -> str:
        """兼容 {"text": ...} 与 {"data": {"text": ...}}，保留原始标签。"""
        if not isinstance(payload, dict):
            return ""
        text = payload.get("text")
        if text is None and isinstance(payload.get("data"), dict):
            text = payload["data"].get("text")
        return text if isinstance(text, str) else ""

    @staticmethod
    def _extract_text(payload: Any) -> str:
        """剥离 SenseVoice 控制标签后返回纯转写文本。"""
        return _TAG_PATTERN.sub("", SenseVoiceAsrProvider._raw_text(payload)).strip()

    @staticmethod
    def _parse_emotion(payload: Any) -> dict[str, Any] | None:
        """从响应标签中提取情感与音频事件；无情感标签时返回 None。"""
        raw = SenseVoiceAsrProvider._raw_text(payload)
        if not raw:
            return None
        tags = [tag.strip().upper() for tag in _TAG_CAPTURE.findall(raw)]
        label = next((tag for tag in tags if tag in _EMOTION_LABELS), None)
        if label is None:
            return None
        event = next((tag for tag in tags if tag in _AUDIO_EVENTS), None)
        return {"label": label, "event": event}

    def _fallback(self, input: ProviderInput) -> dict[str, Any]:
        """保留 Mock 的可用输出，仅把通道标记为降级，不阻塞后续通道。"""
        result = self._mock.analyze(input)
        result["status"] = "degraded"
        result["reason"] = "sensevoice_fallback"
        return result
