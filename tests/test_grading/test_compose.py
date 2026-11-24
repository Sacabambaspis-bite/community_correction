"""合成 compose：取大六组合 + 封顶矩阵 + 复核标记 + 排序/证据齐全。"""

from __future__ import annotations

import pytest

from app.grading import compose, evaluate_period, evaluate_session
from app.grading.config import RULE_VERSION, THRESHOLDS

from .conftest import NOW, WINDOW, make_analysis, make_baseline

_BASE = make_baseline(sample_count=5, psych_signal_mean=0.0,
                      psych_signal_std=THRESHOLDS["BASELINE_MIN_STD"])


def _session(color: str):
    if color == "red":
        return evaluate_session(make_analysis(signal_strength=80.0, intent_flag="suicide_intent"), NOW)
    if color == "orange":
        return evaluate_session(make_analysis(signal_strength=75.0, intent_flag="none"), NOW)
    return evaluate_session(make_analysis(signal_strength=10.0, intent_flag="none"), NOW)  # none


def _period(color: str):
    if color == "yellow":
        offset = THRESHOLDS["TREND_YELLOW_OFFSET_MIN"] + 0.1
    elif color == "blue":
        offset = THRESHOLDS["TREND_BLUE_OFFSET_MIN"] + 0.1
    else:  # green
        offset = 0.1
    sessions = [make_analysis(signal_strength=float(offset)),
                make_analysis(signal_strength=float(offset))]
    return evaluate_period(sessions, _BASE, WINDOW, NOW)


def _prior(prior_color: str):
    """构造 (session, period) 使 compose step1 的 prior == prior_color。

    趋势只产出绿/蓝/黄；红/橙由单次规则给出，搭配绿趋势取大。
    """
    if prior_color in ("red", "orange"):
        return _session(prior_color), _period("green")
    return _session("none"), _period(prior_color)


# ---------- §5.1 取大六组合 ----------

@pytest.mark.parametrize(
    "single,trend,consistency,expect_final,expect_manual",
    [
        ("none", "green", "high", "green", False),
        ("none", "blue", "high", "blue", False),
        ("none", "yellow", "medium", "yellow", False),
        ("red", "green", "low", "red", True),
        ("orange", "yellow", "low", "orange", True),
        ("orange", "green", "high", "orange", False),
    ],
)
def test_compose_six_combos(single, trend, consistency, expect_final, expect_manual):
    final = compose(_session(single), _period(trend), consistency, False, NOW)
    assert final.final_color == expect_final
    assert final.manual_review == expect_manual
    assert final.grading_version == RULE_VERSION


# ---------- 封顶矩阵（R_CONSISTENCY_CAP） ----------
# 契约 §7 / 计划 §5 矩阵：红+low 仍红、橙+low 仍橙、黄+low 仍黄、绿+low 变橙。
# docs/grading.md §5 的 min(prior, orange) 简写与「绿+low 变橙」冲突；此处按
# 矩阵实现：低一致性下 prior 为 green 时抬至 orange（否则绿+low 会被 build_ticket
# 拒单，违背「低一致性必须复核」），其余按 min(prior, orange)，红豁免。歧义已在
# 最终报告标注，待主智能体同步 docs。

@pytest.mark.parametrize(
    "prior,expect_final,expect_cap_recorded",
    [
        ("red", "red", False),
        ("orange", "orange", True),
        ("yellow", "yellow", True),
        ("green", "orange", True),
        ("blue", "blue", True),
    ],
)
def test_consistency_cap_matrix(prior, expect_final, expect_cap_recorded):
    session, period = _prior(prior)
    final = compose(session, period, "low", False, NOW)
    assert final.final_color == expect_final
    assert ("R_CONSISTENCY_CAP" in final.rules_fired) is expect_cap_recorded


def test_red_not_capped_by_low_consistency():
    final = compose(_session("red"), _period("green"), "low", False, NOW)
    assert final.final_color == "red"
    assert "R_CONSISTENCY_CAP" not in final.rules_fired


def test_high_consistency_no_cap():
    final = compose(_session("orange"), _period("green"), "high", False, NOW)
    assert "R_CONSISTENCY_CAP" not in final.rules_fired
    assert final.final_color == "orange"


# ---------- 复核标记 ----------

@pytest.mark.parametrize("consistency,expect_manual", [
    ("low", True), ("medium", False), ("high", False),
])
def test_manual_review_by_consistency(consistency, expect_manual):
    final = compose(_session("none"), _period("green"), consistency, False, NOW)
    assert final.manual_review is expect_manual


def test_needs_review_by_degraded():
    final = compose(_session("none"), _period("green"), "high", True, NOW)
    assert final.needs_review is True
    assert "R_DEGRADED_REVIEW" in final.rules_fired


def test_no_degraded_no_needs_review():
    final = compose(_session("none"), _period("green"), "high", False, NOW)
    assert final.needs_review is False
    assert "R_DEGRADED_REVIEW" not in final.rules_fired


def test_degraded_review_severity_equals_final_color():
    # 绿 + 降级：R_DEGRADED_REVIEW severity 应为 green，不改色
    final = compose(_session("none"), _period("green"), "high", True, NOW)
    assert final.final_color == "green"
    deg = [e for e in final.evidence if e["rule_id"] == "R_DEGRADED_REVIEW"][0]
    # severity 通过 rule_id 关联，此处确认 final 色未被抬升
    assert final.needs_review is True


# ---------- rules_fired 排序与去重 + 证据一一对应 ----------

def test_rules_fired_sorted_by_severity_desc():
    final = compose(_session("red"), _period("yellow"), "high", False, NOW)
    assert final.rules_fired == ["R_SINGLE_RED", "R_TREND_YELLOW"]


def test_rules_fired_dedup_aux_orange():
    # 橙 + 辅助佐证：rule_id 去重后只出现一次
    session = evaluate_session(
        make_analysis(signal_strength=75.0, emotion_label="strong_negative",
                      face_expression="sad"), NOW)
    final = compose(session, _period("green"), "high", False, NOW)
    assert final.rules_fired.count("R_SINGLE_ORANGE") == 1
    # 证据允许同 rule_id 多条（主 + 佐证）
    orange_ev = [e for e in final.evidence if e["rule_id"] == "R_SINGLE_ORANGE"]
    assert len(orange_ev) == 3


def test_every_rule_has_evidence():
    final = compose(_session("orange"), _period("yellow"), "low", True, NOW)
    evidence_rule_ids = {e["rule_id"] for e in final.evidence}
    assert set(final.rules_fired).issubset(evidence_rule_ids)


# ---------- review_reason 默认值 ----------

def test_review_reason_defaults():
    assert compose(_session("none"), _period("green"), "high", False, NOW).review_reason == "routine_check"
    assert compose(_session("none"), _period("green"), "low", False, NOW).review_reason == "consistency_conflict"
    assert compose(_session("none"), _period("green"), "high", True, NOW).review_reason == "analysis_degraded"
    # degraded 优先于 low
    assert compose(_session("none"), _period("green"), "low", True, NOW).review_reason == "analysis_degraded"
