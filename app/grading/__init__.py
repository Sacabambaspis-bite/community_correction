"""五色分级模块（纯函数）。

公开 API：
- ``evaluate_session`` / ``evaluate_period`` / ``compose`` / ``build_ticket``
- dataclasses：``RuleHit`` / ``SessionGrading`` / ``PeriodGrading`` / ``FinalGrading``
- 规则函数：``R_SINGLE_RED`` / ``R_SINGLE_ORANGE`` / ``R_TREND_GREEN`` /
  ``R_TREND_BLUE`` / ``R_TREND_YELLOW`` / ``R_BASELINE_INSUFFICIENT`` /
  ``R_CONSISTENCY_CAP`` / ``R_DEGRADED_REVIEW``
- ``map_risk_level``（供 analysis 侧校准 overall.risk_level）
- config 常量与 ``validate_config`` / ``color_rank``

注意（backend 集成 handoff）：``AnalysisResult`` 不含 ``capture_status``，grading
无法自行判定规则 8。调用方在已知 ``capture_status in (partial, no_face, no_audio)``
时，需用 ``dataclasses.replace(final, review_reason="capture_degraded")`` 覆盖后
再 ``build_ticket``，以触发规则 8 的 P0 + recapture。
"""

from __future__ import annotations

from .compose import R_CONSISTENCY_CAP, R_DEGRADED_REVIEW, compose
from .config import (
    COLOR_RANK,
    DEADLINE_HOURS,
    ORANGE_AUX_EMOTION_LABEL,
    ORANGE_AUX_FACE_EXPRESSIONS,
    REVIEW_REASON_VALUES,
    RULE_VERSION,
    SUGGESTED_METHOD,
    THRESHOLDS,
    THRESHOLD_PROFILE,
    color_rank,
    map_risk_level,
    validate_config,
)
from .models import FinalGrading, PeriodGrading, RuleHit, SessionGrading
from .single import R_SINGLE_ORANGE, R_SINGLE_RED, evaluate_session
from .ticket import build_ticket
from .trend import (
    R_BASELINE_INSUFFICIENT,
    R_TREND_BLUE,
    R_TREND_GREEN,
    R_TREND_YELLOW,
    evaluate_period,
)

__all__ = [
    # 编排
    "evaluate_session",
    "evaluate_period",
    "compose",
    "build_ticket",
    # 规则函数
    "R_SINGLE_RED",
    "R_SINGLE_ORANGE",
    "R_TREND_GREEN",
    "R_TREND_BLUE",
    "R_TREND_YELLOW",
    "R_BASELINE_INSUFFICIENT",
    "R_CONSISTENCY_CAP",
    "R_DEGRADED_REVIEW",
    # 数据结构
    "RuleHit",
    "SessionGrading",
    "PeriodGrading",
    "FinalGrading",
    # 工具
    "map_risk_level",
    "color_rank",
    "validate_config",
    # 常量
    "THRESHOLDS",
    "THRESHOLD_PROFILE",
    "RULE_VERSION",
    "COLOR_RANK",
    "DEADLINE_HOURS",
    "SUGGESTED_METHOD",
    "REVIEW_REASON_VALUES",
    "ORANGE_AUX_FACE_EXPRESSIONS",
    "ORANGE_AUX_EMOTION_LABEL",
]
