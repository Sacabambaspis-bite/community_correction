from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.analysis.models import AnalysisInput, ProviderInput
from app.analysis.pipeline import run_analysis

SESSION_ID = "a0000000-0000-0000-0000-000000000001"
SUBJECT_ID = "a0000000-0000-0000-0000-000000000002"
FIXED_NOW = datetime(2026, 11, 24, 10, 0, tzinfo=timezone(timedelta(hours=8)))


@pytest.fixture
def analysis_input(tmp_path: Path) -> AnalysisInput:
    storage_root = tmp_path / "storage"
    session_dir = (
        storage_root
        / "subjects"
        / SUBJECT_ID
        / "sessions"
        / SESSION_ID
    )
    session_dir.mkdir(parents=True)
    (session_dir / "face.jpg").write_bytes(b"mock-face-not-real-media")
    (session_dir / "audio.wav").write_bytes(b"mock-audio-not-real-media")
    return AnalysisInput(
        session_id=SESSION_ID,
        subject_id=SUBJECT_ID,
        capture_status="ok",
        coverage="both",
        storage_root=storage_root,
        face_path=f"subjects/{SUBJECT_ID}/sessions/{SESSION_ID}/face.jpg",
        audio_path=f"subjects/{SUBJECT_ID}/sessions/{SESSION_ID}/audio.wav",
        duration_sec=30.0,
        speech_ratio=0.62,
    )


@pytest.fixture
def provider_input(analysis_input: AnalysisInput) -> ProviderInput:
    return ProviderInput(
        session_id=analysis_input.session_id,
        subject_id=analysis_input.subject_id,
        storage_root=analysis_input.storage_root,
        face_path=analysis_input.face_path,
        audio_path=analysis_input.audio_path,
        duration_sec=analysis_input.duration_sec,
        speech_ratio=analysis_input.speech_ratio,
    )


@pytest.fixture
def run_pipeline():
    """完整 Schema 用例显式注入合法 risk_level；其他输入也可覆盖。"""

    def invoke(input: AnalysisInput, **overrides):
        ticks = iter((100.0, 100.085))
        options = {
            "scenario": "normal",
            "overall_risk_level_generator": lambda *_: "watch",
            "clock": lambda: FIXED_NOW,
            "monotonic": lambda: next(ticks),
        }
        options.update(overrides)
        return run_analysis(input, **options)

    return invoke
