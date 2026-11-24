from __future__ import annotations

import json
from copy import deepcopy
from dataclasses import replace
from pathlib import Path

import pytest

from app.analysis.errors import AnalysisSchemaError
from app.analysis.providers import build_mock_providers
from app.analysis.schema import validate_result


class FakeProvider:
    def __init__(
        self,
        name,
        *,
        available=True,
        error=None,
        result=None,
    ):
        self.name = name
        self.version = f"test-{name}@1.0"
        self._available = available
        self._error = error
        self._result = result

    def available(self):
        if isinstance(self._available, Exception):
            raise self._available
        return self._available

    def analyze(self, input):
        if self._error is not None:
            raise self._error
        return deepcopy(self._result)


def _assert_valid_run(run, expected_status):
    assert run.analysis_status == expected_status
    assert run.error is None
    assert run.result is not None
    assert "analysis_status" not in run.result
    validate_result(run.result)


def test_mock_end_to_end(analysis_input, run_pipeline):
    run = run_pipeline(analysis_input)
    _assert_valid_run(run, "done")
    result = run.result
    assert result["consistency"] == "high"
    assert result["degraded"] is False
    assert result["needs_review"] is False
    assert result["latency_ms"] == 85
    assert result["started_at"] == "2026-11-24T10:00:00.000+08:00"
    assert set(result["channels"]) == {"asr", "emotion", "face", "psych"}
    assert all(
        channel["status"] == "ok" for channel in result["channels"].values()
    )
    transcript_path = result["channels"]["asr"]["output"]["transcript_path"]
    assert not Path(transcript_path).is_absolute()
    assert transcript_path.startswith("subjects/")
    assert (analysis_input.storage_root / transcript_path).is_file()


@pytest.mark.parametrize(
    ("scenario", "expected_consistency", "expected_intent", "expected_review"),
    [
        ("normal", "high", "none", False),
        ("negative", "high", "none", False),
        ("crisis", "high", "suicide_intent", False),
        ("conflict", "low", "none", True),
    ],
)
def test_four_mock_scenarios(
    analysis_input,
    run_pipeline,
    scenario,
    expected_consistency,
    expected_intent,
    expected_review,
):
    run = run_pipeline(
        analysis_input,
        scenario=scenario,
        overall_risk_level_generator=lambda *_: "watch",
    )
    _assert_valid_run(run, "done")
    assert run.result["consistency"] == expected_consistency
    assert run.result["needs_review"] is expected_review
    assert run.result["channels"]["psych"]["output"]["intent_flag"] == expected_intent
    assert run.result["overall"]["risk_level"] == "watch"


@pytest.mark.parametrize("coverage", ["audio_only", "face_only"])
def test_single_modality_forces_low_and_review(
    analysis_input, run_pipeline, coverage
):
    if coverage == "audio_only":
        face_file = analysis_input.storage_root / analysis_input.face_path
        face_file.unlink()
        single_input = replace(
            analysis_input,
            capture_status="no_face",
            coverage="audio_only",
            face_path=None,
        )
    else:
        audio_file = analysis_input.storage_root / analysis_input.audio_path
        audio_file.unlink()
        single_input = replace(
            analysis_input,
            capture_status="no_audio",
            coverage="face_only",
            audio_path=None,
        )

    run = run_pipeline(single_input)
    _assert_valid_run(run, "degraded")
    assert run.result["consistency"] == "low"
    assert run.result["needs_review"] is True
    assert run.result["degraded"] is True
    if coverage == "audio_only":
        assert run.result["channels"]["face"]["status"] == "skipped"
        assert run.result["channels"]["psych"]["status"] == "ok"
        assert run.result["consistency_basis"]["agree_count"] == 2
    else:
        assert run.result["channels"]["face"]["status"] == "ok"
        assert run.result["channels"]["asr"]["status"] == "skipped"
        assert run.result["channels"]["emotion"]["status"] == "skipped"
        assert run.result["channels"]["psych"]["status"] == "skipped"
        assert run.result["consistency_basis"]["agree_count"] == 1


def test_partial_with_both_modalities_forces_low_without_channel_degradation(
    analysis_input, run_pipeline
):
    run = run_pipeline(replace(analysis_input, capture_status="partial"))
    _assert_valid_run(run, "done")
    assert run.result["consistency"] == "low"
    assert run.result["needs_review"] is True
    assert run.result["degraded"] is False
    assert run.result["consistency_basis"]["agree_count"] == 3


def test_missing_all_inputs_fails_before_analysis(analysis_input, run_pipeline):
    (analysis_input.storage_root / analysis_input.face_path).unlink()
    (analysis_input.storage_root / analysis_input.audio_path).unlink()
    missing = replace(
        analysis_input,
        capture_status="no_face_no_audio",
        coverage=None,
        face_path=None,
        audio_path=None,
    )
    run = run_pipeline(missing)
    assert run.analysis_status == "failed"
    assert run.result is None
    assert run.error == "capture_not_analyzable"


def test_missing_media_file_fails_safely(analysis_input, run_pipeline):
    (analysis_input.storage_root / analysis_input.face_path).unlink()
    run = run_pipeline(analysis_input)
    assert run.analysis_status == "failed"
    assert run.result is None
    assert run.error == "media_file_missing"


def test_non_captured_session_is_rejected(analysis_input, run_pipeline):
    run = run_pipeline(replace(analysis_input, session_status="failed"))
    assert run.analysis_status == "failed"
    assert run.result is None
    assert run.error == "session_not_captured"


def test_path_traversal_is_rejected_without_echoing_path(analysis_input, run_pipeline):
    run = run_pipeline(replace(analysis_input, face_path="../secret.jpg"))
    assert run.analysis_status == "failed"
    assert run.result is None
    assert run.error == "unsafe_media_path"
    assert "secret.jpg" not in run.error


@pytest.mark.parametrize("failed_name", ["asr", "emotion", "face", "psych"])
def test_each_unavailable_provider_is_isolated(
    analysis_input, run_pipeline, failed_name
):
    providers = build_mock_providers("normal")
    providers[failed_name] = FakeProvider(failed_name, available=False)
    run = run_pipeline(analysis_input, providers=providers)
    _assert_valid_run(run, "degraded")
    assert run.result["channels"][failed_name]["status"] == "skipped"
    assert run.result["needs_review"] is True
    for name in ("emotion", "face", "psych"):
        if name == failed_name or (failed_name == "asr" and name == "psych"):
            continue
        assert run.result["channels"][name]["status"] == "ok"


@pytest.mark.parametrize("failed_name", ["emotion", "face", "psych"])
def test_each_provider_exception_preserves_independent_channels(
    analysis_input, run_pipeline, failed_name
):
    providers = build_mock_providers("normal")
    providers[failed_name] = FakeProvider(
        failed_name, error=RuntimeError("sensitive provider failure")
    )
    run = run_pipeline(analysis_input, providers=providers)
    _assert_valid_run(run, "degraded")
    assert run.result["channels"][failed_name]["status"] == "degraded"
    assert run.result["channels"][failed_name]["reason"] == "provider_execution_failed"
    for name in ("asr", "emotion", "face", "psych"):
        if name != failed_name:
            assert run.result["channels"][name]["status"] == "ok"


def test_asr_failure_skips_psych_but_keeps_emotion_and_face(
    analysis_input, run_pipeline
):
    providers = build_mock_providers("normal")
    providers["asr"] = FakeProvider("asr", error=RuntimeError("asr failed"))
    run = run_pipeline(analysis_input, providers=providers)
    _assert_valid_run(run, "degraded")
    assert run.result["channels"]["asr"]["status"] == "degraded"
    assert run.result["channels"]["psych"]["status"] == "skipped"
    assert run.result["channels"]["psych"]["reason"] == "asr_unavailable"
    assert run.result["channels"]["emotion"]["status"] == "ok"
    assert run.result["channels"]["face"]["status"] == "ok"


def test_invalid_provider_output_only_degrades_that_channel(
    analysis_input, run_pipeline
):
    providers = build_mock_providers("normal")
    providers["face"] = FakeProvider(
        "face",
        result={
            "status": "ok",
            "output": {
                "expression_label": "neutral",
                "intensity": 0.1,
                "face_confidence": 0.9,
                "frame_count": 1,
                "valid_frames": 1,
            },
            "confidence": 1.2,
            "latency_ms": 6,
            "reason": None,
        },
    )
    run = run_pipeline(analysis_input, providers=providers)
    _assert_valid_run(run, "degraded")
    assert run.result["channels"]["face"]["status"] == "degraded"
    assert run.result["channels"]["face"]["output"] is None
    assert run.result["channels"]["psych"]["status"] == "ok"


def test_all_unavailable_channels_return_failed_without_grading_result(
    analysis_input, run_pipeline
):
    providers = {
        name: FakeProvider(name, available=False)
        for name in ("asr", "emotion", "face", "psych")
    }
    run = run_pipeline(analysis_input, providers=providers)
    assert run.analysis_status == "failed"
    assert run.result is None
    assert run.error == "no_usable_channel_output"


def test_all_provider_exceptions_return_failed_without_grading_result(
    analysis_input, run_pipeline
):
    providers = {
        name: FakeProvider(name, error=RuntimeError("failure"))
        for name in ("asr", "emotion", "face", "psych")
    }
    run = run_pipeline(analysis_input, providers=providers)
    assert run.analysis_status == "failed"
    assert run.result is None
    assert run.error == "no_usable_channel_output"


def test_final_schema_failure_returns_failed_wrapper(analysis_input, run_pipeline):
    def reject_result(_):
        raise AnalysisSchemaError("schema_validation_failed:test")

    run = run_pipeline(analysis_input, result_validator=reject_result)
    assert run.analysis_status == "failed"
    assert run.result is None
    assert run.error == "schema_validation_failed:test"


def test_invalid_risk_level_is_not_silently_accepted(
    analysis_input, run_pipeline
):
    run = run_pipeline(
        analysis_input,
        overall_risk_level_generator=lambda *_: "pending",
    )
    assert run.analysis_status == "failed"
    assert run.result is None
    assert run.error == "schema_validation_failed:overall.risk_level"


def test_low_confidence_forces_review_without_marking_channel_degraded(
    analysis_input, run_pipeline
):
    providers = build_mock_providers("normal")
    providers["emotion"] = FakeProvider(
        "emotion",
        result={
            "status": "ok",
            "output": {"valence": 0.0, "arousal": 0.25, "label": "neutral"},
            "confidence": 0.59,
            "latency_ms": 8,
            "reason": None,
        },
    )
    run = run_pipeline(analysis_input, providers=providers)
    _assert_valid_run(run, "done")
    assert run.result["consistency"] == "low"
    assert run.result["needs_review"] is True
    assert run.result["degraded"] is False
    assert run.result["channels"]["emotion"]["status"] == "ok"
    assert run.result["consistency_basis"]["low_confidence_channels"] == ["emotion"]
    assert run.result["overall"]["risk_level"] == "watch"


def test_repeated_runs_are_byte_deterministic(analysis_input, run_pipeline):
    first = run_pipeline(analysis_input, scenario="conflict")
    _assert_valid_run(first, "done")
    transcript_path = first.result["channels"]["asr"]["output"]["transcript_path"]
    transcript_file = analysis_input.storage_root / transcript_path
    first_bytes = transcript_file.read_bytes()

    second = run_pipeline(analysis_input, scenario="conflict")
    _assert_valid_run(second, "done")
    assert first.to_dict() == second.to_dict()
    assert transcript_file.read_bytes() == first_bytes


def test_results_and_failures_do_not_leak_sensitive_content(
    analysis_input, run_pipeline
):
    providers = build_mock_providers("negative")
    providers["face"] = FakeProvider(
        "face",
        error=RuntimeError("最近很累 C:/absolute/media raw-image-bytes"),
    )
    run = run_pipeline(analysis_input, scenario="negative", providers=providers)
    _assert_valid_run(run, "degraded")
    serialized = json.dumps(run.to_dict(), ensure_ascii=False)
    assert "最近很累" not in serialized
    assert "raw-image-bytes" not in serialized
    assert str(analysis_input.storage_root) not in serialized
    assert "C:/absolute/media" not in serialized
    assert "mock-audio-not-real-media" not in serialized
    assert "mock-face-not-real-media" not in serialized
