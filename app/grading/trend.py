"""周期趋势规则：七日窗口相对个人基线的偏移，产出绿 / 蓝 / 黄。"""

from __future__ import annotations

from dataclasses import replace
from statistics import mean
from typing import Optional

from .config import RULE_VERSION, THRESHOLDS
from .models import PeriodGrading, RuleHit


def _usable_signals(sessions: list[dict]) -> list[float]:
    """窗口内 ``psych.status == ok`` 且 output 为 dict 的会话 signal_strength 列表。"""
    signals: list[float] = []
    for session in sessions:
        channels = session.get("channels") if isinstance(session, dict) else None
        psych = channels.get("psych") if isinstance(channels, dict) else None
        if not isinstance(psych, dict):
            continue
        if psych.get("status") != "ok":
            continue
        output = psych.get("output")
        if not isinstance(output, dict):
            continue
        signal = output.get("signal_strength")
        if isinstance(signal, (int, float)):
            signals.append(float(signal))
    return signals


def _compute_offset(signals: list[float], baseline: dict) -> float:
    """偏移分 = (窗口均值 - 基线均值) / max(基线std, BASELINE_MIN_STD)。"""
    window_mean = mean(signals)  # 调用方保证 signals 非空
    base_mean = float(baseline.get("psych_signal_mean", 0.0))
    base_std = float(baseline.get("psych_signal_std", 0.0))
    denom = max(base_std, THRESHOLDS["BASELINE_MIN_STD"])
    return (window_mean - base_mean) / denom


def _norm_window(window) -> tuple[str, str]:
    return (str(window[0]), str(window[1]))


def R_TREND_GREEN(offset: float, window) -> Optional[RuleHit]:
    """偏移低于蓝门槛（含 <=0 的无恶化方向）-> 绿。"""
    if offset < THRESHOLDS["TREND_BLUE_OFFSET_MIN"]:
        return RuleHit(
            rule_id="R_TREND_GREEN",
            rule_version=RULE_VERSION,
            field_path="channels.psych.output.signal_strength",
            observed_value=offset,
            threshold_key="TREND_BLUE_OFFSET_MIN",
            threshold_value=THRESHOLDS["TREND_BLUE_OFFSET_MIN"],
            severity="green",
            window=_norm_window(window),
            offset_score=offset,
        )
    return None


def R_TREND_BLUE(offset: float, window) -> Optional[RuleHit]:
    """蓝门槛 <= 偏移 < 黄门槛 -> 蓝。"""
    blue_min = THRESHOLDS["TREND_BLUE_OFFSET_MIN"]
    yellow_min = THRESHOLDS["TREND_YELLOW_OFFSET_MIN"]
    if blue_min <= offset < yellow_min:
        return RuleHit(
            rule_id="R_TREND_BLUE",
            rule_version=RULE_VERSION,
            field_path="channels.psych.output.signal_strength",
            observed_value=offset,
            threshold_key="TREND_BLUE_OFFSET_MIN",
            threshold_value=blue_min,
            severity="blue",
            window=_norm_window(window),
            offset_score=offset,
        )
    return None


def R_TREND_YELLOW(offset: float, window) -> Optional[RuleHit]:
    """偏移 >= 黄门槛 -> 黄。"""
    yellow_min = THRESHOLDS["TREND_YELLOW_OFFSET_MIN"]
    if offset >= yellow_min:
        return RuleHit(
            rule_id="R_TREND_YELLOW",
            rule_version=RULE_VERSION,
            field_path="channels.psych.output.signal_strength",
            observed_value=offset,
            threshold_key="TREND_YELLOW_OFFSET_MIN",
            threshold_value=yellow_min,
            severity="yellow",
            window=_norm_window(window),
            offset_score=offset,
        )
    return None


def R_BASELINE_INSUFFICIENT(reason: str, window) -> RuleHit:
    """基线样本不足或窗口会话不足 -> 蓝（不升级）。

    ``offset_score`` 置 ``0.0``，证据标注 ``insufficient`` 原因。
    """
    if reason == "baseline_insufficient":
        field_path = "baseline.sample_count"
        threshold_key = "BASELINE_MIN_SAMPLES"
        threshold_value = THRESHOLDS["BASELINE_MIN_SAMPLES"]
    else:
        field_path = "window.usable_session_count"
        threshold_key = "TREND_MIN_SESSIONS"
        threshold_value = THRESHOLDS["TREND_MIN_SESSIONS"]
    return RuleHit(
        rule_id="R_BASELINE_INSUFFICIENT",
        rule_version=RULE_VERSION,
        field_path=field_path,
        observed_value=reason,
        threshold_key=threshold_key,
        threshold_value=threshold_value,
        severity="blue",
        window=_norm_window(window),
        offset_score=0.0,
        insufficient=reason,
    )


def evaluate_period(
    sessions: list[dict],
    baseline: dict,
    window: tuple[str, str],
    now: str,
) -> PeriodGrading:
    """周期趋势：基线/会话不足返回 R_BASELINE_INSUFFICIENT，否则算偏移映射。"""
    norm_window = _norm_window(window)
    sample_count = int(baseline.get("sample_count", 0))
    signals = _usable_signals(sessions)

    if sample_count < THRESHOLDS["BASELINE_MIN_SAMPLES"]:
        hit = replace(
            R_BASELINE_INSUFFICIENT("baseline_insufficient", norm_window),
            triggered_at=now,
        )
        return PeriodGrading(
            trend_color="blue",
            offset_score=0.0,
            rule_hits=[hit],
            window=norm_window,
        )

    if len(signals) < THRESHOLDS["TREND_MIN_SESSIONS"]:
        hit = replace(
            R_BASELINE_INSUFFICIENT("window_sessions_insufficient", norm_window),
            triggered_at=now,
        )
        return PeriodGrading(
            trend_color="blue",
            offset_score=0.0,
            rule_hits=[hit],
            window=norm_window,
        )

    offset = _compute_offset(signals, baseline)
    hit = R_TREND_YELLOW(offset, norm_window) or R_TREND_BLUE(offset, norm_window) or R_TREND_GREEN(offset, norm_window)
    hit = replace(hit, triggered_at=now)
    color = {
        "R_TREND_YELLOW": "yellow",
        "R_TREND_BLUE": "blue",
        "R_TREND_GREEN": "green",
    }[hit.rule_id]
    return PeriodGrading(
        trend_color=color,
        offset_score=offset,
        rule_hits=[hit],
        window=norm_window,
    )
