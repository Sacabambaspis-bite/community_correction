"""确定性心理文本 mock，只读取本次 ASR 成功生成的转写。"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from app.analysis.models import ProviderInput
from app.analysis.paths import resolve_session_file


class MockPsychProvider:
    name = "psych"
    version = "mock-psych@1.0"

    def __init__(self, scenario: dict[str, Any]) -> None:
        self._scenario = scenario

    def available(self) -> bool:
        return True

    def analyze(self, input: ProviderInput) -> dict[str, Any]:
        if not input.transcript_path:
            raise ValueError("transcript_unavailable")
        transcript_file = resolve_session_file(
            input.storage_root,
            input.subject_id,
            input.session_id,
            input.transcript_path,
        )
        transcript = transcript_file.read_text(encoding="utf-8")
        if not transcript.strip():
            raise ValueError("empty_transcript")

        return {
            "status": "ok",
            "output": deepcopy(self._scenario["psych"]),
            "confidence": self._scenario["confidence"][self.name],
            "latency_ms": self._scenario["latency_ms"][self.name],
            "reason": None,
        }
