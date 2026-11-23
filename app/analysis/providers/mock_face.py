"""确定性表情 mock，不读取或保存图像内容。"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from app.analysis.models import ProviderInput


class MockFaceProvider:
    name = "face"
    version = "mock-face@1.0"

    def __init__(self, scenario: dict[str, Any]) -> None:
        self._scenario = scenario

    def available(self) -> bool:
        return True

    def analyze(self, input: ProviderInput) -> dict[str, Any]:
        if not input.face_path:
            raise ValueError("face_unavailable")
        return {
            "status": "ok",
            "output": deepcopy(self._scenario["face"]),
            "confidence": self._scenario["confidence"][self.name],
            "latency_ms": self._scenario["latency_ms"][self.name],
            "reason": None,
        }
