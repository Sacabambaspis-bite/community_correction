"""tests/test_grading 共用夹具：sys.path、固定 NOW、analysis/baseline 构造器。"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pytest

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

NOW = "2026-11-24T10:00:00+08:00"
NOW_DT = datetime(2026, 11, 24, 10, 0, tzinfo=timezone(timedelta(hours=8)))
SESSION_ID = "8f3c1b2e-4a5d-4c6e-9f10-1a2b3c4d5e6f"
SUBJECT_ID = "3b1e7c90-2f4a-4d51-8c6b-7d9e0f1a2b3c"
REVIEW_ID = "c41d0a77-9b2e-4f83-a1c5-6d7e8f9a0b1c"

WINDOW = ("2026-11-17", "2026-11-23")
WINDOW_CROSS_MONTH = ("2026-01-28", "2026-02-03")


def _channel(status: str = "ok", output: Any = None, reason: Any = None) -> dict:
    return {
        "status": status,
        "model_version": "mock@1.0",
        "latency_ms": 10,
        "confidence": 0.9,
        "output": output,
        "reason": reason,
    }


def make_analysis(
    *,
    signal_strength: float = 12.0,
    intent_flag: str = "none",
    psych_status: str = "ok",
    emotion_label: str = "neutral",
    emotion_status: str = "ok",
    face_expression: str = "neutral",
    face_status: str = "ok",
    consistency: str = "high",
    degraded: bool = False,
    session_id: str = SESSION_ID,
    subject_id: str = SUBJECT_ID,
) -> dict:
    """构造一份最小可用的 AnalysisResult dict（供 grading 消费，无需完整 schema）。"""
    psych_output = None if psych_status != "ok" else {
        "signal_strength": signal_strength,
        "intent_flag": intent_flag,
        "keywords": [],
        "rationale_signal": "neutral",
    }
    emotion_output = None if emotion_status != "ok" else {
        "valence": 0.0,
        "arousal": 0.2,
        "label": emotion_label,
    }
    face_output = None if face_status != "ok" else {
        "expression_label": face_expression,
        "intensity": 0.1,
        "face_confidence": 0.9,
        "frame_count": 1,
        "valid_frames": 1,
    }
    return {
        "schema_version": "1.0",
        "session_id": session_id,
        "subject_id": subject_id,
        "overall": {
            "text_valence": 0.0,
            "text_signal": signal_strength,
            "risk_level": "none",
            "summary_signal": "neutral",
        },
        "channels": {
            "asr": _channel("ok", {"transcript_path": "x", "duration_sec": 1.0, "speech_ratio": 0.5, "char_count": 1}),
            "emotion": _channel(emotion_status, emotion_output),
            "face": _channel(face_status, face_output),
            "psych": _channel(psych_status, psych_output),
        },
        "consistency": consistency,
        "consistency_basis": {"agree_count": 3, "conflict": False, "low_confidence_channels": []},
        "needs_review": False,
        "degraded": degraded,
        "threshold_profile": "default@v1",
        "started_at": NOW,
        "finished_at": NOW,
        "latency_ms": 85,
    }


def make_baseline(
    *,
    sample_count: int = 5,
    psych_signal_mean: float = 28.4,
    psych_signal_std: float = 7.9,
) -> dict:
    return {
        "schema_version": "baseline@1.0",
        "sample_count": sample_count,
        "emotion_valence_mean": -0.05,
        "emotion_valence_std": 0.18,
        "psych_signal_mean": psych_signal_mean,
        "psych_signal_std": psych_signal_std,
        "updated_at": NOW,
    }


@pytest.fixture
def now() -> str:
    return NOW
