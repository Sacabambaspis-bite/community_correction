"""周期趋势规则：偏移边界 + 基线/窗口不足 + std=0 + 跨月 + 数值断言。"""

from __future__ import annotations

import pytest

from app.grading import (
    R_BASELINE_INSUFFICIENT,
    R_TREND_BLUE,
    R_TREND_GREEN,
    R_TREND_YELLOW,
    evaluate_period,
)
from app.grading.config import THRESHOLDS

from .conftest import NOW, WINDOW, WINDOW_CROSS_MONTH, make_analysis, make_baseline


def _sessions(signals: list[float]) -> list[dict]:
    return [make_analysis(signal_strength=float(s)) for s in signals]


# 为让 offset 可控：基线 mean=0、std=BASELINE_MIN_STD -> offset == 窗口均值
_BASE_OFFSET = make_baseline(sample_count=5, psych_signal_mean=0.0,
                             psych_signal_std=THRESHOLDS["BASELINE_MIN_STD"])


# ---------- 趋势黄 / 蓝 / 绿 边界 ----------

@pytest.mark.parametrize(
    "offset,expect_color,expect_rule",
    [
        (1.499, "blue", "R_TREND_BLUE"),
        (1.5, "yellow", "R_TREND_YELLOW"),
        (1.501, "yellow", "R_TREND_YELLOW"),
    ],
)
def test_trend_yellow_boundary(offset, expect_color, expect_rule):
    period = evaluate_period(_sessions([offset, offset]), _BASE_OFFSET, WINDOW, NOW)
    assert period.trend_color == expect_color
    assert period.rule_hits[0].rule_id == expect_rule
    assert period.offset_score == pytest.approx(offset)


@pytest.mark.parametrize(
    "offset,expect_color",
    [
        (0.799, "green"),
        (0.8, "blue"),
        (1.499, "blue"),
    ],
)
def test_trend_blue_boundary(offset, expect_color):
    period = evaluate_period(_sessions([offset, offset]), _BASE_OFFSET, WINDOW, NOW)
    assert period.trend_color == expect_color


@pytest.mark.parametrize("offset", [-2.0, -0.5, 0.0, 0.5, 0.799])
def test_trend_green(offset):
    period = evaluate_period(_sessions([offset, offset]), _BASE_OFFSET, WINDOW, NOW)
    assert period.trend_color == "green"
    assert period.rule_hits[0].rule_id == "R_TREND_GREEN"


# ---------- 规则函数直接调用 ----------

def test_trend_rule_functions_disjoint():
    # 同一 offset 只能命中一条趋势规则
    for offset in (0.5, 1.0, 2.0):
        hits = [
            R_TREND_GREEN(offset, WINDOW),
            R_TREND_BLUE(offset, WINDOW),
            R_TREND_YELLOW(offset, WINDOW),
        ]
        assert sum(h is not None for h in hits) == 1


def test_trend_evidence_includes_offset_and_window():
    period = evaluate_period(_sessions([1.0, 1.0]), _BASE_OFFSET, WINDOW, NOW)
    ev = period.rule_hits[0].to_evidence()
    assert ev["offset_score"] == pytest.approx(1.0)
    assert ev["window"] == list(WINDOW)
    assert ev["triggered_at"] == NOW


# ---------- 偏移数值断言 ----------

def test_offset_numeric_value():
    baseline = make_baseline(sample_count=5, psych_signal_mean=28.4, psych_signal_std=7.9)
    # 窗口均值 41.2 -> (41.2 - 28.4) / 7.9
    period = evaluate_period(_sessions([41.2, 41.2]), baseline, WINDOW, NOW)
    assert period.offset_score == pytest.approx((41.2 - 28.4) / 7.9)


def test_offset_deterioration_only():
    # 窗口均值低于基线 -> offset 负 -> 绿（不升级）
    baseline = make_baseline(sample_count=5, psych_signal_mean=60.0, psych_signal_std=5.0)
    period = evaluate_period(_sessions([30.0, 30.0]), baseline, WINDOW, NOW)
    assert period.trend_color == "green"
    assert period.offset_score < 0


# ---------- std = 0 不除零 ----------

def test_std_zero_uses_min_std():
    baseline = make_baseline(sample_count=5, psych_signal_mean=0.0, psych_signal_std=0.0)
    period = evaluate_period(_sessions([50.0, 50.0]), baseline, WINDOW, NOW)
    # denom = max(0, BASELINE_MIN_STD) = 1.0 -> offset = 50.0
    assert period.offset_score == pytest.approx(50.0)
    assert period.trend_color == "yellow"


# ---------- 基线 / 窗口不足 ----------

def test_baseline_insufficient():
    baseline = make_baseline(sample_count=2)  # < BASELINE_MIN_SAMPLES(3)
    period = evaluate_period(_sessions([10.0, 10.0]), baseline, WINDOW, NOW)
    assert period.trend_color == "blue"
    assert period.offset_score == 0.0
    hit = period.rule_hits[0]
    assert hit.rule_id == "R_BASELINE_INSUFFICIENT"
    assert hit.to_evidence()["insufficient"] == "baseline_insufficient"


def test_window_sessions_insufficient():
    baseline = make_baseline(sample_count=5)
    period = evaluate_period(_sessions([10.0]), baseline, WINDOW, NOW)  # 1 条 < 2
    assert period.trend_color == "blue"
    assert period.offset_score == 0.0
    assert period.rule_hits[0].to_evidence()["insufficient"] == "window_sessions_insufficient"


def test_baseline_insufficient_takes_priority_over_window():
    # 基线不足优先于窗口不足判定
    baseline = make_baseline(sample_count=1)
    period = evaluate_period(_sessions([10.0]), baseline, WINDOW, NOW)
    assert period.rule_hits[0].to_evidence()["insufficient"] == "baseline_insufficient"


def test_zero_usable_sessions_is_window_insufficient():
    # psych.status != ok 的会话不计入 usable -> 0 条 -> 窗口不足蓝
    baseline = make_baseline(sample_count=5)
    sessions = [make_analysis(signal_strength=90.0, psych_status="skipped")]
    period = evaluate_period(sessions, baseline, WINDOW, NOW)
    assert period.trend_color == "blue"
    assert period.rule_hits[0].to_evidence()["insufficient"] == "window_sessions_insufficient"


# ---------- 跨月窗口 ----------

def test_cross_month_window():
    period = evaluate_period(_sessions([1.0, 1.0]), _BASE_OFFSET, WINDOW_CROSS_MONTH, NOW)
    assert period.window == WINDOW_CROSS_MONTH
    assert period.trend_color == "blue"
    assert period.rule_hits[0].to_evidence()["window"] == list(WINDOW_CROSS_MONTH)


# ---------- R_BASELINE_INSUFFICIENT 始终返回 ----------

def test_baseline_insufficient_always_returns_hit():
    hit = R_BASELINE_INSUFFICIENT("window_sessions_insufficient", WINDOW)
    assert hit.severity == "blue"
    assert hit.offset_score == 0.0
    assert hit.insufficient == "window_sessions_insufficient"
