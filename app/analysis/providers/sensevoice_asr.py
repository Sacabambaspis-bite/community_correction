"""SenseVoice 真实 ASR Provider：HTTP 失败时回退到确定性 Mock 并标记 degraded。

只从 os.environ 读取配置，不自动加载 .env，避免测试环境误触真实服务。
"""

from __future__ import annotations

import logging
import os
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
TIMEOUT_SEC = 10.0


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
        self, scenario: dict[str, Any], *, timeout: float = TIMEOUT_SEC
    ) -> None:
        self._scenario = scenario
        self._mock = MockAsrProvider(scenario)
        self._timeout = timeout

    def available(self) -> bool:
        return True

    def analyze(self, input: ProviderInput) -> dict[str, Any]:
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
                    files={"file": ("audio.wav", handle, "audio/wav")},
                    headers={"Authorization": f"Bearer {api_key}"},
                    timeout=self._timeout,
                )
            response.raise_for_status()
            transcript = self._extract_text(response.json())
            if not transcript:
                raise ValueError("sensevoice_empty_text")
        except Exception as exc:
            # 日志只记异常类型，不记响应体、转写文本或密钥。
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
    def _extract_text(payload: Any) -> str:
        """兼容 {"text": ...} 与 {"data": {"text": ...}} 两种返回结构。"""
        if not isinstance(payload, dict):
            return ""
        text = payload.get("text")
        if text is None and isinstance(payload.get("data"), dict):
            text = payload["data"].get("text")
        return text.strip() if isinstance(text, str) else ""

    def _fallback(self, input: ProviderInput) -> dict[str, Any]:
        """保留 Mock 的可用输出，仅把通道标记为降级，不阻塞后续通道。"""
        result = self._mock.analyze(input)
        result["status"] = "degraded"
        result["reason"] = "sensevoice_fallback"
        return result
