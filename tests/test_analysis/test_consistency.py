from __future__ import annotations

import pytest

from app.analysis.config import CONFIDENCE_THRESHOLD
from app.analysis.consistency import calculate_consistency


def _channel(status="ok", confidence=0.9, output=None):
    if output is None and status == "ok":
        output = {}
    return {"status": status, "confidence": confidence, "output": output}


def _channels(*, emotion_valence=0.0, face_label="neutral"):
    return {
        "asr": _channel(output={"transcript_path": "transcript.txt"}),
        "emotion": _channel(output={"valence": emotion_valence}),
        "face": _channel(output={"expression_label": face_label}),
        "psych": _channel(output={"signal_strength": 10.0}),
    }


def _calculate(channels, *, text_valence=0.0, capture_status="ok", coverage="both"):
    return calculate_consistency(
        capture_status=capture_status,
        coverage=coverage,
        channels=channels,
        text_valence=text_valence,
        confidence_threshold=CONFIDENCE_THRESHOLD,
    )


def test_three_same_directions_are_high():
    consistency, basis = _calculate(
        _channels(emotion_valence=-0.6, face_label="sad"), text_valence=-0.7
    )
    assert consistency == "high"
    assert basis == {
        "agree_count": 3,
        "conflict": False,
        "low_confidence_channels": [],
    }


def test_two_negative_and_one_neutral_are_medium_without_conflict():
    consistency, basis = _calculate(
        _channels(emotion_valence=-0.6, face_label="neutral"), text_valence=-0.7
    )
    assert consistency == "medium"
    assert basis["agree_count"] == 2
    assert basis["conflict"] is False


def test_positive_negative_conflict_overrides_two_channel_agreement():
    consistency, basis = _calculate(
        _channels(emotion_valence=-0.6, face_label="positive"), text_valence=-0.7
    )
    assert consistency == "low"
    assert basis["agree_count"] == 2
    assert basis["conflict"] is True


def test_three_distinct_directions_have_one_agreement_and_conflict():
    consistency, basis = _calculate(
        _channels(emotion_valence=-0.5, face_label="neutral"), text_valence=0.5
    )
    assert consistency == "low"
    assert basis["agree_count"] == 1
    assert basis["conflict"] is True


@pytest.mark.parametrize("channel_name", ["asr", "emotion", "face", "psych"])
@pytest.mark.parametrize(
    ("confidence", "expected"),
    [(CONFIDENCE_THRESHOLD - 0.01, "low"), (CONFIDENCE_THRESHOLD, "high")],
)
def test_low_confidence_boundary_for_every_provider(
    channel_name, confidence, expected
):
    channels = _channels()
    channels[channel_name]["confidence"] = confidence
    consistency, basis = _calculate(channels)
    assert consistency == expected
    expected_low = [channel_name] if expected == "low" else []
    assert basis["low_confidence_channels"] == expected_low


@pytest.mark.parametrize("coverage", ["face_only", "audio_only"])
def test_single_modality_is_always_low_even_when_directions_agree(coverage):
    consistency, _ = _calculate(_channels(), coverage=coverage)
    assert consistency == "low"


def test_partial_capture_with_both_modalities_is_always_low():
    consistency, basis = _calculate(_channels(), capture_status="partial")
    assert consistency == "low"
    assert basis["agree_count"] == 3


def test_analysis_degradation_caps_three_agreements_at_medium():
    channels = _channels()
    channels["asr"]["status"] = "degraded"
    consistency, basis = _calculate(channels)
    assert consistency == "medium"
    assert basis["agree_count"] == 3


def test_two_remaining_directions_can_be_medium_after_psych_is_skipped():
    channels = _channels()
    channels["psych"] = _channel(status="skipped", confidence=0.0)
    consistency, basis = _calculate(channels)
    assert consistency == "medium"
    assert basis["agree_count"] == 2
