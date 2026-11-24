from __future__ import annotations

from dataclasses import replace

import pytest

from app.analysis.pipeline import generate_overall_risk_level
from app.analysis.providers import build_mock_providers
from app.analysis.schema import validate_result


class FailingFaceProvider:
    version = "test-face@1.0"

    def available(self):
        return True

    def analyze(self, input):
        raise RuntimeError("face execution failed")


@pytest.fixture
def checkin_input(analysis_input):
    (analysis_input.storage_root / analysis_input.audio_path).unlink()
    return replace(
        analysis_input,
        capture_status="no_audio",
        coverage="face_only",
        audio_path=None,
        duration_sec=0.0,
        speech_ratio=0.0,
    )


def _assert_expected_audio_skips(result):
    for name in ("asr", "emotion", "psych"):
        channel = result["channels"][name]
        assert channel["status"] == "skipped"
        assert channel["output"] is None
        assert channel["reason"] == "audio_unavailable"


def test_checkin_face_only_expected_skips_do_not_degrade(
    checkin_input, run_pipeline
):
    risk_calls = []

    def risk_generator(text_valence, intent_flag):
        risk_calls.append((text_valence, intent_flag))
        return generate_overall_risk_level(text_valence, intent_flag)

    run = run_pipeline(
        checkin_input,
        kind="checkin",
        overall_risk_level_generator=risk_generator,
    )

    assert run.analysis_status == "done"
    assert run.error is None
    assert run.result is not None
    result = run.result
    validate_result(result)
    assert result["degraded"] is False
    assert set(result["channels"]) == {"asr", "emotion", "face", "psych"}
    _assert_expected_audio_skips(result)
    assert result["channels"]["face"]["status"] == "ok"
    assert result["channels"]["face"]["output"] is not None
    assert risk_calls == [(0.0, "none")]
    assert result["overall"]["risk_level"] == "none"


def test_same_face_only_input_with_report_kind_remains_degraded(
    checkin_input, run_pipeline
):
    run = run_pipeline(checkin_input, kind="report")

    assert run.analysis_status == "degraded"
    assert run.error is None
    assert run.result is not None
    validate_result(run.result)
    assert run.result["degraded"] is True
    assert run.result["needs_review"] is True
    _assert_expected_audio_skips(run.result)
    assert run.result["channels"]["face"]["status"] == "ok"


def test_checkin_face_exception_still_degrades(checkin_input, run_pipeline):
    providers = build_mock_providers("normal")
    providers["face"] = FailingFaceProvider()

    run = run_pipeline(checkin_input, providers=providers, kind="checkin")

    assert run.analysis_status == "degraded"
    assert run.error is None
    assert run.result is not None
    validate_result(run.result)
    assert run.result["degraded"] is True
    assert run.result["needs_review"] is True
    assert run.result["channels"]["face"]["status"] == "degraded"
    assert run.result["channels"]["face"]["output"] is None
    assert run.result["channels"]["face"]["reason"] == "provider_execution_failed"
    _assert_expected_audio_skips(run.result)
