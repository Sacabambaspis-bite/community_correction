"""分级模块的输入输出数据结构。

所有 dataclass 均为 ``frozen=True``，规则函数不得修改入参；时间只进入
``triggered_at``，不参与逻辑分支。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

Color = str  # "green" | "blue" | "yellow" | "orange" | "red"（运行期不做强校验）
Priority = str  # "P0" | "P1" | "P2"
Consistency = str  # "high" | "medium" | "low"


@dataclass(frozen=True)
class RuleHit:
    """单条规则命中的证据载体。

    ``offset_score`` / ``insufficient`` 为实现驱动的可选字段（契约 §2 字段表
    未列，但 §6 工单示例与 §2 约束要求在证据中标注），默认 ``None``，不破坏
    既有字段。
    """

    rule_id: str
    rule_version: str
    field_path: str
    observed_value: float | str | bool
    threshold_key: str
    threshold_value: float | str | list[str]
    severity: str
    session_id: Optional[str] = None
    window: Optional[tuple[str, str]] = None
    triggered_at: str = ""
    offset_score: Optional[float] = None
    insufficient: Optional[str] = None

    def to_evidence(self) -> dict:
        """序列化为与 ``db.md`` ``evidence_json`` 一致的 dict。"""
        evidence: dict = {
            "rule_id": self.rule_id,
            "rule_version": self.rule_version,
            "field_path": self.field_path,
            "observed_value": self.observed_value,
            "threshold_key": self.threshold_key,
            "threshold_value": self.threshold_value,
            "triggered_at": self.triggered_at,
        }
        if self.session_id is not None:
            evidence["session_id"] = self.session_id
        if self.window is not None:
            # JSON 序列化时 tuple 需转 list
            evidence["window"] = list(self.window)
        if self.offset_score is not None:
            evidence["offset_score"] = self.offset_score
        if self.insufficient is not None:
            evidence["insufficient"] = self.insufficient
        return evidence


@dataclass(frozen=True)
class SessionGrading:
    """单次风险规则结果。``single_session_risk`` 取值 red/orange/none。"""

    single_session_risk: str
    rule_hits: list[RuleHit] = field(default_factory=list)


@dataclass(frozen=True)
class PeriodGrading:
    """周期趋势规则结果。``trend_color`` 取值 green/blue/yellow。"""

    trend_color: str
    offset_score: float
    rule_hits: list[RuleHit] = field(default_factory=list)
    window: tuple[str, str] = ("", "")


@dataclass(frozen=True)
class FinalGrading:
    """合成结果。``review_reason`` 为实现驱动字段，供调用方在已知
    ``capture_status`` 时覆写为 ``capture_degraded``（backend 集成 handoff）。"""

    final_color: str
    manual_review: bool
    needs_review: bool
    rules_fired: list[str]
    evidence: list[dict]
    grading_version: str
    review_reason: str = "routine_check"
