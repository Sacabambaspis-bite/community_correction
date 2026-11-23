"""确定性语音情感 mock，不读取音频内容。"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from app.analysis.models import ProviderInput


class MockEmotionProvider:
    name = "emotion"
    version = "mock-emotion@1.0"

    def __init__(self, scenario: dict[str, Any]) -> None:
        self._scenario = scenario

    def available(self) -> bool:
        return True

    def analyze(self, input: ProviderInput) -> dict[str, Any]:
        if not input.audio_path:
            raise ValueError("audio_unavailable")
        return {
            "status": "ok",
            "output": deepcopy(self._scenario["emotion"]),
            "confidence": self._scenario["confidence"][self.name],
            "latency_ms": self._scenario["latency_ms"][self.name],
            "reason": None,
        }
