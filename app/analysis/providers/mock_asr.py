"""确定性 ASR mock：只把固定文本写入本会话 transcript.txt。"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.analysis.models import ProviderInput
from app.analysis.paths import session_directory, transcript_relative_path


def write_transcript(input: ProviderInput, transcript: str) -> str:
    """原子写入会话 transcript.txt，返回契约规定的相对路径。"""
    session_dir = session_directory(
        Path(input.storage_root), input.subject_id, input.session_id
    )
    target = session_dir / "transcript.txt"
    temporary = session_dir / ".transcript.txt.tmp"
    try:
        session_dir.mkdir(parents=True, exist_ok=True)
        temporary.write_text(transcript, encoding="utf-8")
        temporary.replace(target)
    except Exception:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass
        raise
    return transcript_relative_path(input.subject_id, input.session_id)


class MockAsrProvider:
    name = "asr"
    version = "mock-asr@1.0"

    def __init__(self, scenario: dict[str, Any]) -> None:
        self._scenario = scenario

    def available(self) -> bool:
        return True

    def analyze(self, input: ProviderInput) -> dict[str, Any]:
        if not input.audio_path:
            raise ValueError("audio_unavailable")

        transcript = self._scenario["transcript"]
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
            "latency_ms": self._scenario["latency_ms"][self.name],
            "reason": None,
        }
