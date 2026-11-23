"""字符串常量：仅供 api 层校验与写入使用，不映射为数据库 CHECK。

取值逐字取自 `docs/contracts/db.md`（db@1.4）§5.2 与 §6.1，保序不可增删；
新增取值必须先同步契约文档。
"""

from __future__ import annotations

#: `audit_logs.action` 的合法取值（db.md §6.1）。
AUDIT_ACTIONS: tuple[str, ...] = (
    "consent.grant",
    "consent.revoke",
    "sensitive.view",
    "session.analyze",
    "ticket.transition",
    "subject.update",
    "review.create",
)

#: `review_tickets.suggested_method` 的合法取值（db.md §5.2）。
SUGGESTED_METHODS: tuple[str, ...] = (
    "routine_checkin",
    "focused_interview",
    "priority_interview",
    "urgent_escalation",
    "recapture",
)
