"""分级模块阈值与常量的唯一来源。

规则函数只读本模块，不得在函数体内书写阈值数字字面量（由
``tests/test_grading/test_config.py`` 源码扫描兜底）。

无实证依据的阈值一律标注 ``# TODO: 待标定``，禁止编造文献或临床出处。
"""

from __future__ import annotations

# 阈值配置档案 / 规则版本
THRESHOLD_PROFILE = "default@v1"
RULE_VERSION = "grading@1.2"

# 数值 / 字符串阈值：规则函数只读此 dict，不写字面量。
THRESHOLDS: dict[str, float | str] = {
    # 单次红
    "SINGLE_RED_INTENT_FLAG": "suicide_intent",  # TODO: 待标定
    "SINGLE_RED_SELFHARM_INTENT_FLAG": "self_harm_mention",  # TODO: 待标定
    "SINGLE_RED_SELFHARM_SIGNAL": 80,  # TODO: 待标定
    # 单次橙
    "SINGLE_ORANGE_SIGNAL_MIN": 70,  # TODO: 待标定
    # 趋势偏移
    "TREND_BLUE_OFFSET_MIN": 0.8,  # TODO: 待标定
    "TREND_YELLOW_OFFSET_MIN": 1.5,  # TODO: 待标定
    # 基线 / 窗口
    "BASELINE_MIN_SAMPLES": 3,  # TODO: 待标定
    "BASELINE_MIN_STD": 1.0,  # TODO: 待标定
    "TREND_MIN_SESSIONS": 2,  # TODO: 待标定
    # 一致性
    "CONSISTENCY_MIN_CONFIDENCE": 0.6,  # TODO: 待标定
    "CONSISTENCY_CAP_COLOR": "orange",  # TODO: 待标定
    # map_risk_level 分段阈值（历史遗留，供 analysis 侧校准 overall.risk_level）
    "RISK_VALENCE_NONE_MIN": 0.0,  # TODO: 待标定
    "RISK_VALENCE_WATCH_MIN": -0.2,  # TODO: 待标定
    "RISK_VALENCE_ELEVATED_MIN": -0.5,  # TODO: 待标定
    "RISK_VALENCE_HIGH_MIN": -0.8,  # TODO: 待标定
}

# 标签集合（非数值阈值，仍集中管理，便于标定后单点调整）
ORANGE_AUX_FACE_EXPRESSIONS: tuple[str, ...] = ("sad", "anxious")
ORANGE_AUX_EMOTION_LABEL: str = "strong_negative"
RISK_INTENT_CRISIS_FLAGS: tuple[str, ...] = ("suicide_intent", "self_harm_mention")

# FinalGrading.review_reason 允许取值
REVIEW_REASON_VALUES: tuple[str, ...] = (
    "routine_check",
    "capture_degraded",
    "consistency_conflict",
    "analysis_degraded",
)

# 工单时限（小时）
DEADLINE_HOURS: dict[str, int] = {"P0": 24, "P1": 72, "P2": 168}

# 建议复核方式（按最终色）
SUGGESTED_METHOD: dict[str, str] = {
    "red": "urgent_escalation",
    "orange": "priority_interview",
    "yellow": "focused_interview",
    "blue": "routine_checkin",
}

# 颜色等级序：none=0，用于合成取大与封顶比较
COLOR_RANK: dict[str, int] = {
    "none": 0,
    "green": 1,
    "blue": 2,
    "yellow": 3,
    "orange": 4,
    "red": 5,
}

# 启动期必须存在的阈值键（缺失即 KeyError，不做默认兜底）
_REQUIRED_THRESHOLD_KEYS: tuple[str, ...] = (
    "SINGLE_RED_INTENT_FLAG",
    "SINGLE_RED_SELFHARM_INTENT_FLAG",
    "SINGLE_RED_SELFHARM_SIGNAL",
    "SINGLE_ORANGE_SIGNAL_MIN",
    "TREND_BLUE_OFFSET_MIN",
    "TREND_YELLOW_OFFSET_MIN",
    "BASELINE_MIN_SAMPLES",
    "BASELINE_MIN_STD",
    "TREND_MIN_SESSIONS",
    "CONSISTENCY_MIN_CONFIDENCE",
    "CONSISTENCY_CAP_COLOR",
    "RISK_VALENCE_NONE_MIN",
    "RISK_VALENCE_WATCH_MIN",
    "RISK_VALENCE_ELEVATED_MIN",
    "RISK_VALENCE_HIGH_MIN",
)


def color_rank(color: str) -> int:
    """返回色码的等级序；未知色码抛 KeyError。"""
    if color not in COLOR_RANK:
        raise KeyError(f"unknown_color: {color}")
    return COLOR_RANK[color]


def validate_config() -> None:
    """启动期校验所有必需阈值键存在；缺失即抛 KeyError，不做默认兜底。"""
    for key in _REQUIRED_THRESHOLD_KEYS:
        if key not in THRESHOLDS:
            raise KeyError(f"missing_threshold_key: {key}")


def map_risk_level(text_valence: float, intent_flag: str = "none") -> str:
    """把 ``text_valence`` + ``intent_flag`` 映射为 analysis 侧的五档
    ``overall.risk_level``。

    注意：grading 的五色规则**不消费** ``risk_level``；本函数是供 analysis 侧
    填充 ``overall.risk_level`` 的校准逻辑（历史遗留占位替换）。

    分段（全部未标定）::

        v >= 0              -> none
        -0.2 <= v < 0       -> watch
        -0.5 <= v < -0.2    -> elevated
        -0.8 <= v < -0.5    -> high
        v < -0.8            -> crisis

    若 ``intent_flag`` 指向明确意图，则强制覆写为 ``crisis``（最高档）。
    """
    if intent_flag in RISK_INTENT_CRISIS_FLAGS:
        return "crisis"
    v = text_valence
    if v >= THRESHOLDS["RISK_VALENCE_NONE_MIN"]:
        return "none"
    if v >= THRESHOLDS["RISK_VALENCE_WATCH_MIN"]:
        return "watch"
    if v >= THRESHOLDS["RISK_VALENCE_ELEVATED_MIN"]:
        return "elevated"
    if v >= THRESHOLDS["RISK_VALENCE_HIGH_MIN"]:
        return "high"
    return "crisis"


# 模块导入即校验，确保启动期缺失阈值立即失败
validate_config()
