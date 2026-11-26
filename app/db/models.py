"""ORM 模型。

字段、约束与索引与 `docs/contracts/db.md`（db@1.5）第 2-6 节逐字对齐：
业务主键为 TEXT（UUID v4 字符串），时间为 TEXT（ISO 8601 字符串），
布尔为 INTEGER 0/1，JSON 列为 TEXT + `json_valid` CHECK，可空列允许 NULL。

注意：只有契约中明确标注 `CHECK in (...)` 的列才加枚举 CHECK。
"""

from __future__ import annotations

from typing import Optional

from sqlalchemy import (
    REAL,
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    Text,
    UniqueConstraint,
    desc,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class Subject(Base):
    """矫正对象（db.md §2）。"""

    __tablename__ = "subjects"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    code: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    gender: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, default="unknown", server_default="unknown"
    )
    birth_year: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(
        Text, nullable=False, default="active", server_default="active"
    )
    consent_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    baseline_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    checkin_interval_days: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default="1"
    )
    report_interval_days: Mapped[int] = mapped_column(
        Integer, nullable=False, default=3, server_default="3"
    )
    created_at: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[str] = mapped_column(Text, nullable=False)

    __table_args__ = (
        CheckConstraint(
            "gender IN ('male','female','unknown')",
            name="ck_subjects_gender",
        ),
        CheckConstraint(
            "status IN ('active','suspended','closed')",
            name="ck_subjects_status",
        ),
        CheckConstraint(
            "consent_json IS NULL OR json_valid(consent_json)",
            name="ck_subjects_consent_json",
        ),
        CheckConstraint(
            "baseline_json IS NULL OR json_valid(baseline_json)",
            name="ck_subjects_baseline_json",
        ),
        CheckConstraint(
            "checkin_interval_days >= 1", name="ck_subjects_checkin_interval_days"
        ),
        CheckConstraint(
            "report_interval_days >= 1", name="ck_subjects_report_interval_days"
        ),
        Index("ix_subjects_status", "status"),
    )


class CaptureSession(Base):
    """单次采集会话（db.md §3）。

    类名避免与 `sqlalchemy.orm.Session` 重名，表名严格为 `sessions`。
    会话表只允许存裁剪后的面部图路径，禁止原始帧字段。
    """

    __tablename__ = "sessions"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    subject_id: Mapped[str] = mapped_column(
        Text, ForeignKey("subjects.id"), nullable=False
    )
    kind: Mapped[str] = mapped_column(
        Text, nullable=False, default="report", server_default="report"
    )
    status: Mapped[str] = mapped_column(Text, nullable=False)
    capture_status: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    face_path: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    audio_path: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    transcript_path: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    duration_sec: Mapped[Optional[float]] = mapped_column(REAL, nullable=True)
    captured_at: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # db@1.3：NOT NULL DEFAULT 'pending'。
    analysis_status: Mapped[str] = mapped_column(
        Text, nullable=False, default="pending", server_default="pending"
    )
    analysis_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # db@1.4：状态类列，NOT NULL DEFAULT '[]'。
    codes: Mapped[str] = mapped_column(Text, nullable=False, server_default="[]")
    created_at: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[str] = mapped_column(Text, nullable=False)

    __table_args__ = (
        CheckConstraint(
            "kind IN ('checkin','report')",
            name="ck_sessions_kind",
        ),
        CheckConstraint(
            "status IN ('created','captured','failed')",
            name="ck_sessions_status",
        ),
        CheckConstraint(
            "capture_status IN "
            "('ok','partial','no_face','no_audio','no_face_no_audio','error')",
            name="ck_sessions_capture_status",
        ),
        CheckConstraint(
            "analysis_status IN ('pending','done','degraded','failed')",
            name="ck_sessions_analysis_status",
        ),
        CheckConstraint(
            "analysis_json IS NULL OR json_valid(analysis_json)",
            name="ck_sessions_analysis_json",
        ),
        CheckConstraint("json_valid(codes)", name="ck_sessions_codes"),
        Index(
            "ix_sessions_subject_captured_at",
            "subject_id",
            desc("captured_at"),
        ),
        Index(
            "ix_sessions_subject_kind_captured_at",
            "subject_id",
            "kind",
            desc("captured_at"),
        ),
        Index("ix_sessions_status", "status"),
    )

    #: 不构建覆盖产物（零产物 / 无采集结果）的 capture_status 集合。
    _NO_COVERAGE_STATUSES = frozenset({None, "no_face_no_audio", "error"})

    @property
    def coverage(self) -> Optional[str]:
        """由 `capture_status` + `face_path` + `audio_path` 推导的产物覆盖。

        **这是 coverage 的唯一实现**，api 层与前端禁止各自手推。
        契约（db.md）没有 `coverage` 列，因此这里是只读属性，不落库。
        """
        if self.capture_status in self._NO_COVERAGE_STATUSES:
            return None
        has_face = bool(self.face_path)
        has_audio = bool(self.audio_path)
        if has_face and has_audio:
            return "both"
        if has_face:
            return "face_only"
        if has_audio:
            return "audio_only"
        return None


class Review(Base):
    """周期复盘（db.md §4）。"""

    __tablename__ = "reviews"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    subject_id: Mapped[str] = mapped_column(
        Text, ForeignKey("subjects.id"), nullable=False
    )
    source_session_id: Mapped[Optional[str]] = mapped_column(
        Text, ForeignKey("sessions.id"), nullable=True
    )
    window_start: Mapped[str] = mapped_column(Text, nullable=False)
    window_end: Mapped[str] = mapped_column(Text, nullable=False)
    window_days: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="7"
    )
    single_session_risk: Mapped[str] = mapped_column(Text, nullable=False)
    trend_color: Mapped[str] = mapped_column(Text, nullable=False)
    final_color: Mapped[str] = mapped_column(Text, nullable=False)
    consistency: Mapped[str] = mapped_column(Text, nullable=False)
    manual_review: Mapped[int] = mapped_column(Integer, nullable=False)
    rules_fired: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_json: Mapped[str] = mapped_column(Text, nullable=False)
    grading_version: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[str] = mapped_column(Text, nullable=False)

    __table_args__ = (
        CheckConstraint(
            "single_session_risk IN ('red','orange','none')",
            name="ck_reviews_single_session_risk",
        ),
        CheckConstraint(
            "trend_color IN ('green','blue','yellow')",
            name="ck_reviews_trend_color",
        ),
        CheckConstraint(
            "final_color IN ('green','blue','yellow','orange','red')",
            name="ck_reviews_final_color",
        ),
        CheckConstraint(
            "consistency IN ('high','medium','low')",
            name="ck_reviews_consistency",
        ),
        CheckConstraint("manual_review IN (0, 1)", name="ck_reviews_manual_review"),
        CheckConstraint("json_valid(rules_fired)", name="ck_reviews_rules_fired"),
        CheckConstraint("json_valid(evidence_json)", name="ck_reviews_evidence_json"),
        UniqueConstraint(
            "subject_id", "window_end", name="uq_reviews_subject_window_end"
        ),
        Index(
            "ix_reviews_subject_created_at",
            "subject_id",
            desc("created_at"),
        ),
        Index("ix_reviews_final_color", "final_color"),
    )


class ReviewTicket(Base):
    """复核工单（db.md §5）。"""

    __tablename__ = "review_tickets"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    review_id: Mapped[Optional[str]] = mapped_column(
        Text, ForeignKey("reviews.id"), nullable=True, unique=True
    )
    subject_id: Mapped[str] = mapped_column(
        Text, ForeignKey("subjects.id"), nullable=False
    )
    status: Mapped[str] = mapped_column(Text, nullable=False)
    priority: Mapped[str] = mapped_column(Text, nullable=False)
    due_at: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    triggered_rules: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_json: Mapped[str] = mapped_column(Text, nullable=False)
    # 无复盘关联的逾期工单在此记录 overdue_kind / overdue_days。
    detail_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # db.md §5.2 列出取值但未标 CHECK，因此不加 CHECK。
    suggested_method: Mapped[str] = mapped_column(Text, nullable=False)
    assignee: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    conclusion_color: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    conclusion_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    opened_at: Mapped[str] = mapped_column(Text, nullable=False)
    closed_at: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    __table_args__ = (
        CheckConstraint(
            "status IN ('pending','confirmed','corrected','closed')",
            name="ck_review_tickets_status",
        ),
        CheckConstraint(
            "priority IN ('P0','P1','P2')",
            name="ck_review_tickets_priority",
        ),
        CheckConstraint(
            "conclusion_color IN ('green','blue','yellow','orange','red')",
            name="ck_review_tickets_conclusion_color",
        ),
        CheckConstraint(
            "json_valid(triggered_rules)", name="ck_review_tickets_triggered_rules"
        ),
        CheckConstraint(
            "json_valid(evidence_json)", name="ck_review_tickets_evidence_json"
        ),
        CheckConstraint(
            "detail_json IS NULL OR json_valid(detail_json)",
            name="ck_review_tickets_detail_json",
        ),
        Index(
            "ix_review_tickets_status_priority_opened_at",
            "status",
            "priority",
            desc("opened_at"),
        ),
        Index("ix_review_tickets_subject_id", "subject_id"),
    )


class AuditLog(Base):
    """访问与操作留痕（db.md §6）。"""

    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    actor_type: Mapped[str] = mapped_column(Text, nullable=False)
    actor_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # db.md §6.1 列出取值但未标 CHECK，因此不加 CHECK。
    action: Mapped[str] = mapped_column(Text, nullable=False)
    target_type: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    target_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    detail_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    request_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[str] = mapped_column(Text, nullable=False)

    __table_args__ = (
        CheckConstraint(
            "actor_type IN ('subject','staff','system')",
            name="ck_audit_logs_actor_type",
        ),
        CheckConstraint(
            "detail_json IS NULL OR json_valid(detail_json)",
            name="ck_audit_logs_detail_json",
        ),
        Index(
            "ix_audit_logs_target",
            "target_type",
            "target_id",
            desc("created_at"),
        ),
        Index(
            "ix_audit_logs_actor",
            "actor_id",
            desc("created_at"),
        ),
        {"sqlite_autoincrement": True},
    )
