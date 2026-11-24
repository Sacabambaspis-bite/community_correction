"""复核工单草案生成。只返回 dict，不写库、不发通知、不做任何处置动作。"""

from __future__ import annotations

from datetime import datetime, timedelta

from .config import DEADLINE_HOURS, SUGGESTED_METHOD
from .models import FinalGrading

# 最终色 -> 优先级（未被 review_reason 覆写时使用）
_COLOR_PRIORITY: dict[str, str] = {
    "red": "P0",
    "orange": "P0",
    "yellow": "P1",
    "blue": "P2",
}


def _parse_now(now: str) -> datetime:
    """解析带时区 ISO 时间；无时区抛 ValueError，避免静默错误。"""
    dt = datetime.fromisoformat(now)
    if dt.tzinfo is None:
        raise ValueError("now_must_be_timezone_aware")
    return dt


def _due_at(now: str, priority: str) -> str:
    """now + DEADLINE_HOURS[priority]，保持时区，毫秒精度 ISO。"""
    hours = DEADLINE_HOURS[priority]
    dt = _parse_now(now) + timedelta(hours=hours)
    return dt.isoformat(timespec="milliseconds")


def build_ticket(final: FinalGrading, review_id: str, subject_id: str, now: str) -> dict:
    """生成工单草案，字段与 ``db.md`` 的 ``review_tickets`` 可写子集对齐。

    - 绿且 ``needs_review=False`` -> 抛 ``ValueError("ticket_not_allowed_for_green")``；
    - 「绿 + 降级」(``needs_review=True``) 允许建单；
    - ``review_reason=="capture_degraded"`` 覆写为 P0 + recapture（规则 8）；
    - ``manual_review=True``（低一致性，规则 5）覆写 ``priority`` 为 P0，``suggested_method``
      仍按最终色；
    - 幂等：相同输入 -> 相同输出，不含随机值。
    """
    reason = final.review_reason
    # 规则 8（capture_degraded）必建 P0 单，不受「绿 + 不复核」守卫拦截
    if final.final_color == "green" and not final.needs_review and reason != "capture_degraded":
        raise ValueError("ticket_not_allowed_for_green")

    if reason == "capture_degraded":
        priority = "P0"
        suggested_method = "recapture"
    elif final.final_color == "green" and final.needs_review:
        # 规则 6：降级补采
        priority = "P1"
        suggested_method = "recapture"
    elif final.manual_review:
        # 规则 5：低一致性强制人工复核，24 小时内处理；复核方式仍按最终色
        priority = "P0"
        suggested_method = SUGGESTED_METHOD[final.final_color]
    else:
        priority = _COLOR_PRIORITY[final.final_color]
        suggested_method = SUGGESTED_METHOD[final.final_color]

    return {
        "review_id": review_id,
        "subject_id": subject_id,
        "status": "pending",
        "priority": priority,
        "due_at": _due_at(now, priority),
        "triggered_rules": list(final.rules_fired),
        "evidence_json": list(final.evidence),
        "suggested_method": suggested_method,
        "opened_at": now,
    }
