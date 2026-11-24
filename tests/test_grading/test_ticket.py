"""build_ticket：绿抛异常 / 绿+降级建单 / 字段齐全 / due_at / priority / 幂等。"""

from __future__ import annotations

from dataclasses import replace

import pytest

from app.grading import FinalGrading, build_ticket, compose, evaluate_period, evaluate_session
from app.grading.config import DEADLINE_HOURS, RULE_VERSION, THRESHOLDS

from .conftest import NOW, REVIEW_ID, SUBJECT_ID, WINDOW, make_analysis, make_baseline

_BASE = make_baseline(sample_count=5, psych_signal_mean=0.0,
                      psych_signal_std=THRESHOLDS["BASELINE_MIN_STD"])


def _final(
    final_color: str = "blue",
    *,
    needs_review: bool = False,
    manual_review: bool = False,
    review_reason: str = "routine_check",
    rules_fired=None,
    evidence=None,
) -> FinalGrading:
    return FinalGrading(
        final_color=final_color,
        manual_review=manual_review,
        needs_review=needs_review,
        rules_fired=rules_fired or ["R_TREND_BLUE"],
        evidence=evidence or [{"rule_id": "R_TREND_BLUE", "rule_version": RULE_VERSION,
                               "field_path": "x", "observed_value": 1.0,
                               "threshold_key": "TREND_BLUE_OFFSET_MIN",
                               "threshold_value": 0.8, "triggered_at": NOW}],
        grading_version=RULE_VERSION,
        review_reason=review_reason,
    )


# ---------- 绿建单规则 ----------

def test_green_no_review_raises():
    final = _final("green", needs_review=False)
    with pytest.raises(ValueError, match="ticket_not_allowed_for_green"):
        build_ticket(final, REVIEW_ID, SUBJECT_ID, NOW)


def test_green_with_degraded_builds_ticket():
    # 规则 6：绿 + 降级 -> P1 + recapture，不抛异常
    final = _final("green", needs_review=True, review_reason="analysis_degraded",
                   rules_fired=["R_DEGRADED_REVIEW"])
    ticket = build_ticket(final, REVIEW_ID, SUBJECT_ID, NOW)
    assert ticket["priority"] == "P1"
    assert ticket["suggested_method"] == "recapture"


# ---------- 采集降级覆写（规则 8） ----------

def test_capture_degraded_overrides_to_p0_recapture():
    # backend 用 replace 覆写 review_reason 后建单
    base = _final("yellow", needs_review=False, review_reason="routine_check")
    final = replace(base, review_reason="capture_degraded", manual_review=True)
    ticket = build_ticket(final, REVIEW_ID, SUBJECT_ID, NOW)
    assert ticket["priority"] == "P0"
    assert ticket["suggested_method"] == "recapture"


def test_capture_degraded_green_builds_p0():
    final = _final("green", needs_review=False, review_reason="capture_degraded")
    ticket = build_ticket(final, REVIEW_ID, SUBJECT_ID, NOW)
    assert ticket["priority"] == "P0"
    assert ticket["suggested_method"] == "recapture"


# ---------- priority 按色码映射 ----------

@pytest.mark.parametrize(
    "color,expect_priority,expect_method",
    [
        ("red", "P0", "urgent_escalation"),
        ("orange", "P0", "priority_interview"),
        ("yellow", "P1", "focused_interview"),
        ("blue", "P2", "routine_checkin"),
    ],
)
def test_priority_and_method_by_color(color, expect_priority, expect_method):
    final = _final(color, needs_review=True)
    ticket = build_ticket(final, REVIEW_ID, SUBJECT_ID, NOW)
    assert ticket["priority"] == expect_priority
    assert ticket["suggested_method"] == expect_method


# ---------- due_at 按 P 级 ----------

@pytest.mark.parametrize("priority,expected", [
    ("P0", "2026-11-25T10:00:00.000+08:00"),
    ("P1", "2026-11-27T10:00:00.000+08:00"),
    ("P2", "2026-12-01T10:00:00.000+08:00"),
])
def test_due_at_by_priority(priority, expected):
    color = {"P0": "red", "P1": "yellow", "P2": "blue"}[priority]
    ticket = build_ticket(_final(color, needs_review=True), REVIEW_ID, SUBJECT_ID, NOW)
    assert ticket["due_at"] == expected
    assert ticket["priority"] == priority


def test_due_at_preserves_timezone():
    now = "2026-11-30T23:00:00+08:00"  # 跨月
    ticket = build_ticket(_final("blue", needs_review=True), REVIEW_ID, SUBJECT_ID, now)
    # +168h = 7 天 -> 12-07
    assert ticket["due_at"] == "2026-12-07T23:00:00.000+08:00"
    assert ticket["opened_at"] == now


def test_now_without_timezone_raises():
    with pytest.raises(ValueError, match="now_must_be_timezone_aware"):
        build_ticket(_final("blue", needs_review=True), REVIEW_ID, SUBJECT_ID,
                     "2026-11-24T10:00:00")


# ---------- 字段齐全 ----------

def test_ticket_fields_complete():
    final = compose(
        evaluate_session(make_analysis(signal_strength=75.0), NOW),
        evaluate_period([make_analysis(signal_strength=1.0), make_analysis(signal_strength=1.0)],
                        _BASE, WINDOW, NOW),
        "high", False, NOW,
    )
    ticket = build_ticket(final, REVIEW_ID, SUBJECT_ID, NOW)
    for key in ("review_id", "subject_id", "status", "priority", "due_at",
                "triggered_rules", "evidence_json", "suggested_method", "opened_at"):
        assert key in ticket
    assert ticket["status"] == "pending"
    assert ticket["review_id"] == REVIEW_ID
    assert ticket["subject_id"] == SUBJECT_ID
    assert ticket["triggered_rules"] == final.rules_fired
    assert ticket["evidence_json"] == final.evidence
    # deadline 小时数与配置一致
    assert ticket["due_at"]  # 非空


def test_due_at_matches_config_hours():
    ticket = build_ticket(_final("red", needs_review=True), REVIEW_ID, SUBJECT_ID, NOW)
    # 24h 后 = 次日同一时刻
    assert ticket["due_at"].startswith("2026-11-25T10:00:00")


# ---------- 幂等 ----------

def test_ticket_idempotent():
    final = _final("orange", needs_review=True, manual_review=True,
                   review_reason="consistency_conflict")
    t1 = build_ticket(final, REVIEW_ID, SUBJECT_ID, NOW)
    t2 = build_ticket(final, REVIEW_ID, SUBJECT_ID, NOW)
    assert t1 == t2
