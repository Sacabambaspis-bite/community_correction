"""对象心理状态趋势聚合（api@1.5 §7.18）。

本模块只做**纯函数 / 只读**聚合：不访问数据库、不读文件、不写库、不写审计。
路由负责取数与序列化，这里负责日期区间校验、日粒度指标与信号判定。

所有阈值均为**契约常量，待标定**：后续统一迁入阈值配置并版本化，
变更需走 api.md §9 流程。
"""

from __future__ import annotations

import json
import logging
import statistics
from datetime import date, datetime, timedelta
from typing import Any, Mapping, Optional, Sequence

logger = logging.getLogger("app.api")

#: 日粒度指标允许进入统计的分析状态。
USABLE_ANALYSIS_STATUSES = frozenset({"done", "degraded"})
#: 分析侧风险档位由低到高（契约固定顺序）。
RISK_ORDER = {"none": 0, "watch": 1, "elevated": 2, "high": 3, "crisis": 4}
#: 行为依从性涉及的两类会话。
BEHAVIOR_KINDS = ("checkin", "report")
#: 缺省窗口天数（含端点）。
DEFAULT_RANGE_DAYS = 14
#: 区间跨度上限（含端点）。
MAX_RANGE_DAYS = 366

# ---- 信号阈值（api@1.5 §7.18，全部「待标定」）----
INSUFFICIENT_DATA_MIN_POINTS = 3  # 待标定
LOW_AROUSAL_NEGATIVE_SIGNAL_MAX = 35.0  # 待标定
HIGH_AROUSAL_NEGATIVE_SIGNAL_MIN = 70.0  # 待标定
PERSISTENT_LOW_VALENCE_MAX = -0.3  # 待标定
PERSISTENT_LOW_VALENCE_MIN_POINTS = 3  # 待标定
VALENCE_VOLATILITY_MIN_STD = 0.35  # 待标定
SIGNAL_ESCALATION_DELTA = 15.0  # 待标定
SIGNAL_ESCALATION_TAIL = 3  # 待标定
SIGNAL_ESCALATION_MIN_POINTS = 6  # 待标定
LOW_CONSISTENCY_MIN_COUNT = 3  # 待标定
LOW_CONSISTENCY_RATIO = 0.4  # 待标定
CAPTURE_DEGRADED_MIN_COUNT = 3  # 待标定
BEHAVIOR_OVERDUE_MIN_DAYS = 3  # 待标定
QUADRANT_SIGNAL_BOUNDARY = 50.0  # 待标定

_DATE_FORMAT = "%Y-%m-%d"


class TrendRangeError(ValueError):
    """日期区间非法；`reason` 直接作为业务错误 message（api@1.5 §7.18）。"""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


def to_local_date(value: Optional[str]) -> Optional[date]:
    """把 `captured_at` / `window_end` 解析为自然日。

    与 dashboard 的 `_review_date` 口径一致：优先按 ISO 8601 原样解析
    （保留落库时携带的时区偏移），失败时再尝试纯日期字符串。
    """
    if not value:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text).date()
    except ValueError:
        pass
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None


def _parse_cli_date(value: str, reason: str) -> date:
    if len(value) != 10 or value[4] != "-" or value[7] != "-":
        raise TrendRangeError(reason)
    try:
        return datetime.strptime(value, _DATE_FORMAT).date()
    except ValueError:
        raise TrendRangeError(reason) from None


def resolve_date_range(
    start_date: Optional[str], end_date: Optional[str], today: date
) -> tuple[date, date]:
    """解析闭区间；缺省/单侧补齐 14 天窗口，跨度上限 366 天（含端点）。

    校验顺序：格式（invalid_date）→ start>end（invalid_date_range）
    → 跨度过大（date_range_too_large）。
    """
    start = _parse_cli_date(start_date, "invalid_date") if start_date else None
    end = _parse_cli_date(end_date, "invalid_date") if end_date else None

    if start is None and end is None:
        end = today
        start = end - timedelta(days=DEFAULT_RANGE_DAYS - 1)
    elif start is None:
        assert end is not None
        start = end - timedelta(days=DEFAULT_RANGE_DAYS - 1)
    elif end is None:
        end = start + timedelta(days=DEFAULT_RANGE_DAYS - 1)

    if start > end:
        raise TrendRangeError("invalid_date_range")
    if (end - start).days + 1 > MAX_RANGE_DAYS:
        raise TrendRangeError("date_range_too_large")
    return start, end


def _load_analysis(raw: Optional[str], session_id: str) -> Optional[dict]:
    """解析单条 `analysis_json`；失败只记录 session_id 并跳过该会话。"""
    if not raw:
        return None
    try:
        value = json.loads(raw)
    except (TypeError, ValueError):
        logger.warning("trend.analysis_skip session_id=%s", session_id)
        return None
    if not isinstance(value, dict):
        logger.warning("trend.analysis_skip session_id=%s", session_id)
        return None
    return value


def _as_number(value: Any) -> Optional[float]:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def _channel_output(analysis: Mapping[str, Any], name: str) -> Optional[dict]:
    channels = analysis.get("channels")
    if not isinstance(channels, dict):
        return None
    channel = channels.get(name)
    if not isinstance(channel, dict):
        return None
    output = channel.get("output")
    return output if isinstance(output, dict) else None


def _mean(values: Sequence[float]) -> Optional[float]:
    if not values:
        return None
    return round(statistics.fmean(values), 4)


def _sample_stdev(values: Sequence[float]) -> Optional[float]:
    """样本标准差；点数 < 2 时返回 None（契约要求）。"""
    if len(values) < 2:
        return None
    return round(statistics.stdev(values), 4)


def _stat_block(values: Sequence[float]) -> dict:
    return {
        "mean": _mean(values),
        "std": _sample_stdev(values),
        "count": len(values),
    }


def _is_expected(day: date, anchor: Optional[date], interval_days: int) -> bool:
    """历史回溯口径：从「不晚于区间终点的最近一次 completed 日」按周期回溯。

    `(day - anchor).days % interval == 0` 同时覆盖 anchor 前后两侧的周期日。
    该口径只用于趋势图的期望/逾期展示，**不同于** §7.6 / §7.11 的实时逾期。
    """
    if anchor is None or interval_days < 1:
        return False
    return (day - anchor).days % interval_days == 0


def _build_review_index(
    reviews: Sequence[Mapping[str, Any]], start: date, end: date
) -> dict[date, Mapping[str, Any]]:
    """按 `window_end` 自然日建索引；同日多条时优先精确日期串，其次取较新记录。"""
    index: dict[date, Mapping[str, Any]] = {}
    for review in reviews:
        raw = review.get("window_end")
        day = to_local_date(raw)
        if day is None or day < start or day > end:
            continue
        current = index.get(day)
        if current is None:
            index[day] = review
            continue
        exact = str(raw or "")[:10] == day.isoformat()
        current_exact = str(current.get("window_end") or "")[:10] == day.isoformat()
        if exact and not current_exact:
            index[day] = review
        elif exact == current_exact and str(review.get("created_at") or "") > str(
            current.get("created_at") or ""
        ):
            index[day] = review
    return index


def _review_payload(review: Optional[Mapping[str, Any]]) -> Optional[dict]:
    if review is None:
        return None
    return {
        "color": review.get("color"),
        "review_id": review.get("review_id"),
        "rules_fired": list(review.get("rules_fired") or []),
        "consistency": review.get("consistency"),
        "manual_review": bool(review.get("manual_review")),
        "evidence_available": bool(review.get("evidence_available")),
    }


def build_trends(
    *,
    subject_id: str,
    start: date,
    end: date,
    interval_days: Mapping[str, int],
    sessions: Sequence[Mapping[str, Any]],
    reviews: Sequence[Mapping[str, Any]],
    behavior_anchors: Mapping[str, Optional[date]],
) -> dict:
    """组装 §7.18 的 `data`；调用方负责鉴权、错误码与信封。

    `sessions` / `reviews` 只含该对象的数据（跨对象隔离由调用方保证）。
    `behavior_anchors` 为每类会话「不晚于 end 的最近一次 completed 日」。
    """
    review_index = _build_review_index(reviews, start, end)

    sessions_by_day: dict[date, list[Mapping[str, Any]]] = {}
    parsed_by_id: dict[str, Optional[dict]] = {}
    for session in sessions:
        day = to_local_date(session.get("captured_at"))
        if day is None or day < start or day > end:
            continue
        sessions_by_day.setdefault(day, []).append(session)
        session_id = str(session.get("session_id") or "")
        parsed_by_id[session_id] = _load_analysis(
            session.get("analysis_json"), session_id
        )

    days: list[dict] = []
    scatter_points: list[dict] = []
    low_total = 0
    degraded_total = 0
    analyzed_total = 0
    overdue_days = 0

    cursor = start
    while cursor <= end:
        day_sessions = sessions_by_day.get(cursor, [])
        day_key = cursor.isoformat()

        checkin_count = sum(1 for item in day_sessions if item.get("kind") == "checkin")
        report_count = sum(1 for item in day_sessions if item.get("kind") == "report")
        analyzed_count_day = sum(
            1
            for item in day_sessions
            if item.get("analysis_status") in USABLE_ANALYSIS_STATUSES
        )
        failed_count = sum(
            1 for item in day_sessions if item.get("analysis_status") == "failed"
        )

        risk_level: Optional[str] = None
        valences: list[float] = []
        signals: list[float] = []
        degraded_count = 0
        low_count = 0
        conflict_count = 0
        day_points: list[dict] = []

        for session in day_sessions:
            session_id = str(session.get("session_id") or "")
            analysis = parsed_by_id.get(session_id)
            usable = session.get("analysis_status") in USABLE_ANALYSIS_STATUSES

            if usable and analysis is not None:
                overall = analysis.get("overall")
                if isinstance(overall, dict):
                    raw_risk = overall.get("risk_level")
                    if raw_risk in RISK_ORDER:
                        if risk_level is None or RISK_ORDER[raw_risk] > RISK_ORDER[
                            risk_level
                        ]:
                            risk_level = raw_risk

            # 一致性告警：degraded / low / conflict 各自独立计数。
            if session.get("analysis_status") == "degraded":
                degraded_count += 1
            elif analysis is not None and analysis.get("degraded") is True:
                degraded_count += 1
            if analysis is not None:
                if analysis.get("consistency") == "low":
                    low_count += 1
                basis = analysis.get("consistency_basis")
                if isinstance(basis, dict) and basis.get("conflict") is True:
                    conflict_count += 1

            if session.get("kind") != "report" or not usable or analysis is None:
                continue

            overall = analysis.get("overall")
            if not isinstance(overall, dict):
                continue
            valence = _as_number(overall.get("text_valence"))
            signal = _as_number(overall.get("text_signal"))
            if valence is not None:
                valences.append(valence)
            if signal is not None:
                signals.append(signal)

            if valence is None or signal is None:
                # 散点需要效价与信号两个数值；缺失时跳过该点（不臆造 0）。
                continue

            emotion = _channel_output(analysis, "emotion") or {}
            arousal = _as_number(emotion.get("arousal"))
            label = emotion.get("label")
            emotion_label = label if isinstance(label, str) else None
            review = review_index.get(cursor)
            day_points.append(
                {
                    "date": day_key,
                    "session_id": session_id,
                    "captured_at": session.get("captured_at"),
                    "kind": "report",
                    "valence": valence,
                    "signal": signal,
                    "arousal": arousal,
                    "emotion_label": emotion_label,
                    "review_color": review.get("color") if review else None,
                    "review_rules": list(review.get("rules_fired") or [])
                    if review
                    else [],
                    "review_id": review.get("review_id") if review else None,
                }
            )

        day_points.sort(key=lambda item: str(item.get("captured_at") or ""))
        scatter_points.extend(day_points)

        behavior: dict[str, dict] = {}
        for kind in BEHAVIOR_KINDS:
            completed = any(
                item.get("kind") == kind and item.get("status") == "captured"
                for item in day_sessions
            )
            expected = _is_expected(
                cursor, behavior_anchors.get(kind), int(interval_days.get(kind, 1))
            )
            behavior[kind] = {
                "expected": expected,
                "completed": completed,
                "overdue": expected and not completed,
            }
        if behavior["checkin"]["overdue"] or behavior["report"]["overdue"]:
            overdue_days += 1

        low_total += low_count
        degraded_total += degraded_count
        analyzed_total += analyzed_count_day

        days.append(
            {
                "date": day_key,
                "review": _review_payload(review_index.get(cursor)),
                "analysis_risk_level": risk_level,
                "sessions": {
                    "total": len(day_sessions),
                    "checkin": checkin_count,
                    "report": report_count,
                    "analyzed": analyzed_count_day,
                    "failed": failed_count,
                },
                "text_valence": _stat_block(valences),
                "text_signal": _stat_block(signals),
                "consistency": {
                    "degraded": degraded_count,
                    "low": low_count,
                    "conflict": conflict_count,
                },
                "behavior": behavior,
            }
        )
        cursor += timedelta(days=1)

    point_valences = [float(point["valence"]) for point in scatter_points]
    point_signals = [float(point["signal"]) for point in scatter_points]
    avg_valence = _mean(point_valences)
    avg_signal = _mean(point_signals)
    valence_std = _sample_stdev(point_valences)
    signal_std = _sample_stdev(point_signals)

    quadrants = {"q1": 0, "q2": 0, "q3": 0, "q4": 0}
    for point in scatter_points:
        valence = float(point["valence"])
        signal = float(point["signal"])
        if valence >= 0 and signal >= QUADRANT_SIGNAL_BOUNDARY:
            quadrants["q1"] += 1
        elif valence < 0 and signal >= QUADRANT_SIGNAL_BOUNDARY:
            quadrants["q2"] += 1
        elif valence < 0 and signal < QUADRANT_SIGNAL_BOUNDARY:
            quadrants["q3"] += 1
        else:
            quadrants["q4"] += 1

    expected_pairs = 0
    completed_expected_pairs = 0
    for day in days:
        for kind in BEHAVIOR_KINDS:
            state = day["behavior"][kind]
            if state["expected"]:
                expected_pairs += 1
                if state["completed"]:
                    completed_expected_pairs += 1
    coverage_rate = (
        round(completed_expected_pairs / expected_pairs, 4) if expected_pairs else 0
    )

    signals_out: list[str] = []
    point_count = len(scatter_points)
    if point_count < INSUFFICIENT_DATA_MIN_POINTS:
        signals_out.append("insufficient_data")
    if (
        avg_valence is not None
        and avg_signal is not None
        and avg_valence < 0
        and avg_signal < LOW_AROUSAL_NEGATIVE_SIGNAL_MAX
    ):
        signals_out.append("low_arousal_negative")
    if (
        avg_valence is not None
        and avg_signal is not None
        and avg_valence < 0
        and avg_signal >= HIGH_AROUSAL_NEGATIVE_SIGNAL_MIN
    ):
        signals_out.append("high_arousal_negative")
    if (
        point_count >= PERSISTENT_LOW_VALENCE_MIN_POINTS
        and all(value < PERSISTENT_LOW_VALENCE_MAX for value in point_valences)
    ):
        signals_out.append("persistent_low_valence")
    if (
        point_count >= PERSISTENT_LOW_VALENCE_MIN_POINTS
        and valence_std is not None
        and valence_std >= VALENCE_VOLATILITY_MIN_STD
    ):
        signals_out.append("valence_volatility_high")
    if point_count >= SIGNAL_ESCALATION_MIN_POINTS:
        head = statistics.fmean(point_signals[:SIGNAL_ESCALATION_TAIL])
        tail = statistics.fmean(point_signals[-SIGNAL_ESCALATION_TAIL:])
        if tail - head >= SIGNAL_ESCALATION_DELTA:
            signals_out.append("signal_escalating")
    if low_total >= LOW_CONSISTENCY_MIN_COUNT or (
        analyzed_total > 0 and low_total / analyzed_total >= LOW_CONSISTENCY_RATIO
    ):
        signals_out.append("frequent_low_consistency")
    if degraded_total >= CAPTURE_DEGRADED_MIN_COUNT:
        signals_out.append("frequent_capture_degraded")
    if overdue_days >= BEHAVIOR_OVERDUE_MIN_DAYS:
        signals_out.append("behavior_overdue_frequent")

    return {
        "subject_id": subject_id,
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "interval_days": {
            "checkin": int(interval_days.get("checkin", 1)),
            "report": int(interval_days.get("report", 1)),
        },
        "days": days,
        "scatter_points": scatter_points,
        "summary": {
            "analyzed_count": point_count,
            "avg_valence": avg_valence,
            "avg_signal": avg_signal,
            "valence_std": valence_std,
            "signal_std": signal_std,
            "coverage_rate": coverage_rate,
            "quadrants": quadrants,
            "signals": signals_out,
        },
        # 聚合接口与具体会话无关，固定不降级（契约要求）。
        "degraded": [],
    }
