from __future__ import annotations

from dataclasses import replace

import pytest

from app.analysis.schema import validate_result


@pytest.fixture
def face_only_input(analysis_input):
    (analysis_input.storage_root / analysis_input.audio_path).unlink()
    return replace(
        analysis_input,
        capture_status="no_audio",
        coverage="face_only",
        audio_path=None,
        duration_sec=0.0,
        speech_ratio=0.0,
    )


def test_checkin_single_face_uses_neutral_consistency_without_review(
    face_only_input, run_pipeline
):
    run = run_pipeline(face_only_input, kind="checkin")

    assert run.analysis_status == "done"
    assert run.error is None
    assert run.result is not None
    result = run.result
    validate_result(result)
    assert result["degraded"] is False
    assert result["consistency"] == "medium"
    assert result["needs_review"] is False
    assert result["consistency_basis"] == {
        "agree_count": 1,
        "conflict": False,
        "low_confidence_channels": [],
    }
    assert result["channels"]["face"]["status"] == "ok"
    for name in ("asr", "emotion", "psych"):
        assert result["channels"][name]["status"] == "skipped"
        assert result["channels"][name]["output"] is None


def test_report_face_only_still_forces_low_consistency_and_review(
    face_only_input, run_pipeline
):
    run = run_pipeline(face_only_input)

    assert run.analysis_status == "degraded"
    assert run.error is None
    assert run.result is not None
    validate_result(run.result)
    assert run.result["degraded"] is True
    assert run.result["consistency"] == "low"
    assert run.result["needs_review"] is True
