"""单次风险规则：R_SINGLE_RED / R_SINGLE_ORANGE / evaluate_session。"""

from __future__ import annotations

import pytest

from app.grading import R_SINGLE_ORANGE, R_SINGLE_RED, evaluate_session
from app.grading.config import THRESHOLDS

from .conftest import NOW, make_analysis


# ---------- R_SINGLE_RED 边界 ----------

@pytest.mark.parametrize(
    "signal,expect_hit",
    [
        (79.9, False),
        (80.0, True),
        (80.1, True),
    ],
)
def test_red_selfharm_boundary(signal, expect_hit):
    analysis = make_analysis(signal_strength=signal, intent_flag="self_harm_mention")
    hit = R_SINGLE_RED(analysis)
    assert (hit is not None) is expect_hit
    if hit is not None:
        assert hit.severity == "red"
        assert hit.field_path == "channels.psych.output.signal_strength"
        assert hit.threshold_key == "SINGLE_RED_SELFHARM_SIGNAL"


def test_red_suicide_intent_direct():
    analysis = make_analysis(signal_strength=10.0, intent_flag="suicide_intent")
    hit = R_SINGLE_RED(analysis)
    assert hit is not None
    assert hit.severity == "red"
    assert hit.field_path == "channels.psych.output.intent_flag"
    assert hit.observed_value == "suicide_intent"
    assert hit.threshold_value == THRESHOLDS["SINGLE_RED_INTENT_FLAG"]


def test_red_not_triggered_for_none_intent():
    analysis = make_analysis(signal_strength=95.0, intent_flag="none")
    assert R_SINGLE_RED(analysis) is None


def test_red_selfharm_below_threshold_no_hit():
    analysis = make_analysis(signal_strength=50.0, intent_flag="self_harm_mention")
    assert R_SINGLE_RED(analysis) is None


# ---------- R_SINGLE_ORANGE 边界 ----------

@pytest.mark.parametrize(
    "signal,expect_hit",
    [
        (69.9, False),
        (70.0, True),
        (70.1, True),
    ],
)
def test_orange_signal_boundary(signal, expect_hit):
    analysis = make_analysis(signal_strength=signal, intent_flag="none")
    hit = R_SINGLE_ORANGE(analysis)
    assert (hit is not None) is expect_hit
    if hit is not None:
        assert hit.severity == "orange"
        assert hit.threshold_key == "SINGLE_ORANGE_SIGNAL_MIN"


def test_orange_not_triggered_for_suicide_intent():
    # 明确意图走红，橙不触发
    analysis = make_analysis(signal_strength=90.0, intent_flag="suicide_intent")
    assert R_SINGLE_ORANGE(analysis) is None


def test_orange_not_triggered_when_psych_skipped():
    analysis = make_analysis(signal_strength=90.0, intent_flag="none", psych_status="skipped")
    assert R_SINGLE_ORANGE(analysis) is None


def test_orange_not_triggered_when_output_none():
    analysis = make_analysis(signal_strength=90.0, intent_flag="none", psych_status="degraded")
    # degraded + output 为 None 时不触发
    analysis["channels"]["psych"]["output"] = None
    assert R_SINGLE_ORANGE(analysis) is None


# ---------- evaluate_session 编排 ----------

def test_evaluate_session_red_priority():
    # signal 同时满足橙(>=70)与红(self_harm>=80)，应返回红，橙不出现
    analysis = make_analysis(signal_strength=85.0, intent_flag="self_harm_mention")
    result = evaluate_session(analysis, NOW)
    assert result.single_session_risk == "red"
    assert len(result.rule_hits) == 1
    assert result.rule_hits[0].rule_id == "R_SINGLE_RED"
    assert result.rule_hits[0].session_id == analysis["session_id"]
    assert result.rule_hits[0].triggered_at == NOW


def test_evaluate_session_orange_with_aux_evidence():
    analysis = make_analysis(
        signal_strength=75.0,
        intent_flag="none",
        emotion_label="strong_negative",
        face_expression="sad",
    )
    result = evaluate_session(analysis, NOW)
    assert result.single_session_risk == "orange"
    rule_ids = [h.rule_id for h in result.rule_hits]
    # 1 主证据 + emotion 佐证 + face 佐证
    assert rule_ids == ["R_SINGLE_ORANGE", "R_SINGLE_ORANGE", "R_SINGLE_ORANGE"]
    field_paths = [h.field_path for h in result.rule_hits]
    assert "channels.psych.output.signal_strength" in field_paths
    assert "channels.emotion.output.label" in field_paths
    assert "channels.face.output.expression_label" in field_paths


def test_evaluate_session_orange_aux_anxious_face():
    analysis = make_analysis(
        signal_strength=72.0,
        intent_flag="none",
        emotion_label="neutral",
        face_expression="anxious",
    )
    result = evaluate_session(analysis, NOW)
    assert result.single_session_risk == "orange"
    assert len(result.rule_hits) == 2  # 主 + face 佐证
    assert {h.field_path for h in result.rule_hits} == {
        "channels.psych.output.signal_strength",
        "channels.face.output.expression_label",
    }


def test_evaluate_session_orange_no_aux():
    analysis = make_analysis(
        signal_strength=70.0,
        intent_flag="none",
        emotion_label="neutral",
        face_expression="neutral",
    )
    result = evaluate_session(analysis, NOW)
    assert result.single_session_risk == "orange"
    assert len(result.rule_hits) == 1


def test_evaluate_session_none():
    analysis = make_analysis(signal_strength=12.0, intent_flag="none")
    result = evaluate_session(analysis, NOW)
    assert result.single_session_risk == "none"
    assert result.rule_hits == []


def test_evaluate_session_missing_psych_raises():
    analysis = make_analysis()
    del analysis["channels"]["psych"]
    with pytest.raises(ValueError, match="missing_psych_channel"):
        evaluate_session(analysis, NOW)


def test_evaluate_session_evidence_has_min_fields():
    analysis = make_analysis(signal_strength=80.0, intent_flag="suicide_intent")
    result = evaluate_session(analysis, NOW)
    ev = result.rule_hits[0].to_evidence()
    for key in ("rule_id", "rule_version", "field_path", "observed_value",
                "threshold_key", "threshold_value", "triggered_at"):
        assert key in ev
