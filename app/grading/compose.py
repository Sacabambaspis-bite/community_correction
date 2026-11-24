"""合成：取大 -> 低一致性封顶 -> 标记复核。顺序不可调。"""

from __future__ import annotations

from dataclasses import replace
from typing import Optional

from .config import RULE_VERSION, THRESHOLDS, color_rank
from .models import FinalGrading, PeriodGrading, RuleHit, SessionGrading


def R_CONSISTENCY_CAP(consistency: str, prior_color: str) -> Optional[RuleHit]:
    """低一致性封顶：``consistency==low`` 且 ``prior != red`` 时命中（红不受封顶）。"""
    if consistency == "low" and prior_color != "red":
        return RuleHit(
            rule_id="R_CONSISTENCY_CAP",
            rule_version=RULE_VERSION,
            field_path="consistency",
            observed_value=consistency,
            threshold_key="CONSISTENCY_CAP_COLOR",
            threshold_value=THRESHOLDS["CONSISTENCY_CAP_COLOR"],
            severity="orange",
        )
    return None


def R_DEGRADED_REVIEW(degraded: bool, final_color: str, now: str) -> Optional[RuleHit]:
    """分析降级 -> 仅用于建单（不改色），severity 取 final_color。"""
    if degraded:
        return RuleHit(
            rule_id="R_DEGRADED_REVIEW",
            rule_version=RULE_VERSION,
            field_path="degraded",
            observed_value=degraded,
            threshold_key="DEGRADED_REVIEW",
            threshold_value=True,
            severity=final_color,
            triggered_at=now,
        )
    return None


def _pick_prior(single: str, trend: str) -> str:
    """取大：single(none/red/orange) 与 trend(green/blue/yellow) 按等级序比较。"""
    return single if color_rank(single) >= color_rank(trend) else trend


def _default_review_reason(consistency: str, degraded: bool) -> str:
    """review_reason 默认值（调用方可在已知 capture_status 时覆写为 capture_degraded）。"""
    if degraded:
        return "analysis_degraded"
    if consistency == "low":
        return "consistency_conflict"
    return "routine_check"


def compose(
    session_grading: SessionGrading,
    period_grading: PeriodGrading,
    consistency: str,
    degraded: bool,
    now: str,
) -> FinalGrading:
    """严格四步合成（顺序不可调换）::

        step1  prior = max(single_session_risk, period_trend)
        step2  若命中 R_CONSISTENCY_CAP：final = min(prior, orange)，且 prior 为 green
               时抬至 orange（低一致性下不得结论为绿，强制复核）；红不受封顶
        step3  manual_review = (consistency == low)
        step4  needs_review = degraded；若 degraded 追加 R_DEGRADED_REVIEW
    """
    # step1
    prior = _pick_prior(session_grading.single_session_risk, period_grading.trend_color)

    # step2
    cap_hit = R_CONSISTENCY_CAP(consistency, prior)
    if cap_hit is not None:
        cap_color = THRESHOLDS["CONSISTENCY_CAP_COLOR"]
        if prior == "green":
            # 低一致性下不得结论为「绿」：无法确认无风险，抬至封顶色强制人工复核
            final_color = cap_color
        elif color_rank(prior) <= color_rank(cap_color):
            final_color = prior
        else:
            final_color = cap_color
        cap_hit = replace(cap_hit, triggered_at=now)
    else:
        final_color = prior

    # step3
    manual_review = consistency == "low"

    # step4
    needs_review = bool(degraded)
    degraded_hit = R_DEGRADED_REVIEW(needs_review, final_color, now)

    # 汇总所有命中：按严重度从高到低排序；rules_fired 去重，evidence 一一对应
    all_hits: list[RuleHit] = []
    all_hits.extend(session_grading.rule_hits)
    all_hits.extend(period_grading.rule_hits)
    if cap_hit is not None:
        all_hits.append(cap_hit)
    if degraded_hit is not None:
        all_hits.append(degraded_hit)

    all_hits.sort(key=lambda h: -color_rank(h.severity))

    rules_fired: list[str] = []
    seen: set[str] = set()
    for hit in all_hits:
        if hit.rule_id not in seen:
            seen.add(hit.rule_id)
            rules_fired.append(hit.rule_id)

    evidence = [hit.to_evidence() for hit in all_hits]

    return FinalGrading(
        final_color=final_color,
        manual_review=manual_review,
        needs_review=needs_review,
        rules_fired=rules_fired,
        evidence=evidence,
        grading_version=RULE_VERSION,
        review_reason=_default_review_reason(consistency, degraded),
    )
