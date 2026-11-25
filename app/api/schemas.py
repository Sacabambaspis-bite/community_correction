"""pydantic v2 请求与响应模型，字段与 api@1.5 示例逐字对齐。"""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field

#: 需要标记 `degraded=["capture"]` 的采集状态。
CAPTURE_DEGRADED_STATUSES = frozenset({"partial", "no_face", "no_audio"})


def degraded_flags(
    capture_status: Optional[str] = None,
    analysis_status: Optional[str] = None,
) -> list[str]:
    """按契约顺序组装 degraded：capture 在前，analysis 在后，其余接口返回 []。"""
    flags: list[str] = []
    if capture_status in CAPTURE_DEGRADED_STATUSES:
        flags.append("capture")
    if analysis_status == "degraded":
        flags.append("analysis")
    return flags


class HealthOut(BaseModel):
    db: bool


class CreateSessionRequest(BaseModel):
    subject_id: str = Field(..., min_length=1, max_length=64)
    kind: Literal["checkin", "report"] = "report"
    device_index: int = Field(default=0, ge=0)
    duration_sec: Optional[float] = Field(default=None, gt=0)


class CreateSessionOut(BaseModel):
    session_id: str
    status: str
    kind: Literal["checkin", "report"]


class SessionOut(BaseModel):
    session_id: str
    subject_id: str
    kind: Literal["checkin", "report"]
    status: str
    capture_status: Optional[str] = None
    coverage: Optional[str] = None
    face_available: bool
    audio_available: bool
    duration_sec: Optional[float] = None
    captured_at: Optional[str] = None
    analysis_status: str
    codes: list[str] = Field(default_factory=list)
    created_at: str
    updated_at: str


class SubjectListItem(BaseModel):
    subject_id: str
    code: str
    name: str
    status: str
    checkin_interval_days: int
    report_interval_days: int
    latest_color: Optional[str] = None
    latest_color_at: Optional[str] = None
    latest_rules: list[str] = Field(default_factory=list)
    pending_tickets: int
    latest_session_at: Optional[str] = None
    overdue: dict[str, bool]


class SubjectListOut(BaseModel):
    items: list[SubjectListItem]
    page: int
    page_size: int
    total: int


class SessionListItem(BaseModel):
    session_id: str
    subject_id: str
    kind: Literal["checkin", "report"]
    status: str
    capture_status: Optional[str] = None
    coverage: Optional[str] = None
    analysis_status: str
    captured_at: Optional[str] = None


class SessionListOut(BaseModel):
    items: list[SessionListItem]
    page: int
    page_size: int
    total: int


# ---- 用户端同意与反馈（api@1.5 §5.3 / §7.1 / §7.8）----


class ConsentScope(BaseModel):
    granted: bool
    at: Optional[str] = None


class ConsentOut(BaseModel):
    subject_id: str
    general: ConsentScope
    face: ConsentScope
    audio: ConsentScope
    revoked_at: Optional[str] = None
    retention_days: Optional[int] = None


class ConsentGrantRequest(BaseModel):
    subject_id: str = Field(..., min_length=1, max_length=64)
    face: bool
    audio: bool
    retention_days: int = Field(default=180, ge=1)


class ConsentRevokeRequest(BaseModel):
    subject_id: str = Field(..., min_length=1, max_length=64)


class FeedbackOut(BaseModel):
    session_id: str
    status: str
    summary_text: str
    suggestion: Literal["keep_routine", "talk_to_staff", "recapture"]
    next_action: str


class TaskKindOut(BaseModel):
    interval_days: int
    last_completed_at: Optional[str] = None
    overdue: bool


class UserTasksOut(BaseModel):
    checkin: TaskKindOut
    report: TaskKindOut


# ---- 管理端复盘 / 工单 / 看板（api@1.5 §7.9-§7.14）----

Color = Literal["green", "blue", "yellow", "orange", "red"]


class SubjectFrequencyRequest(BaseModel):
    checkin_interval_days: Optional[int] = Field(default=None, ge=1, strict=True)
    report_interval_days: Optional[int] = Field(default=None, ge=1, strict=True)


class SubjectFrequencyOut(BaseModel):
    subject_id: str
    checkin_interval_days: int
    report_interval_days: int


class ReviewCreateRequest(BaseModel):
    subject_id: str = Field(..., min_length=1, max_length=64)
    window_end: Optional[str] = None
    window_days: int = Field(default=7, ge=1)


class ReviewDetailOut(BaseModel):
    review_id: str
    subject_id: str
    window_start: str
    window_end: str
    window_days: int
    single_session_risk: str
    trend_color: str
    final_color: str
    consistency: str
    manual_review: bool
    rules_fired: list[str] = Field(default_factory=list)
    grading_version: str
    evidence: list[dict] = Field(default_factory=list)
    created_at: str


class TicketListItemOut(BaseModel):
    ticket_id: str
    subject_id: str
    subject_name: Optional[str] = None
    priority: str
    final_color: Optional[str] = None
    triggered_rules: list[str] = Field(default_factory=list)
    opened_at: str
    due_at: Optional[str] = None
    status: str
    detail_json: Optional[dict] = None


class TicketListOut(BaseModel):
    items: list[TicketListItemOut]
    page: int
    page_size: int
    total: int


class TicketHistoryItemOut(BaseModel):
    action: str
    actor: str
    note: Optional[str] = None
    at: str


class TicketDetailOut(TicketListItemOut):
    rules_fired: list[str] = Field(default_factory=list)
    suggested_method: str
    evidence: list[dict] = Field(default_factory=list)
    history: list[TicketHistoryItemOut] = Field(default_factory=list)


class TicketTransitionRequest(BaseModel):
    action: Literal["confirm", "correct", "close"]
    conclusion_color: Optional[Color] = None
    note: Optional[str] = None
    assignee: Optional[str] = None


class TicketTransitionOut(BaseModel):
    ticket_id: str
    status: str
    previous_status: str
    action: str
    conclusion_color: Optional[str] = None
    conclusion_note: Optional[str] = None
    assignee: Optional[str] = None
    closed_at: Optional[str] = None


class TrendPointOut(BaseModel):
    date: str
    color: str


class DashboardOut(BaseModel):
    subject_id: str
    color_distribution: dict[str, int]
    trend_7d: list[TrendPointOut] = Field(default_factory=list)
    pending_tickets: int
    last_session_at: Optional[str] = None
    overdue: dict[str, bool]


# ---- 对象心理状态趋势（api@1.5 §7.18）----


class TrendIntervalDaysOut(BaseModel):
    checkin: int
    report: int


class TrendReviewOut(BaseModel):
    color: str
    review_id: str
    rules_fired: list[str] = Field(default_factory=list)
    consistency: str
    manual_review: bool
    evidence_available: bool


class TrendSessionCountsOut(BaseModel):
    total: int
    checkin: int
    report: int
    analyzed: int
    failed: int


class TrendStatOut(BaseModel):
    mean: Optional[float] = None
    std: Optional[float] = None
    count: int


class TrendConsistencyOut(BaseModel):
    degraded: int
    low: int
    conflict: int


class TrendBehaviorKindOut(BaseModel):
    expected: bool
    completed: bool
    overdue: bool


class TrendBehaviorOut(BaseModel):
    checkin: TrendBehaviorKindOut
    report: TrendBehaviorKindOut


class TrendDayOut(BaseModel):
    date: str
    review: Optional[TrendReviewOut] = None
    analysis_risk_level: Optional[str] = None
    sessions: TrendSessionCountsOut
    text_valence: TrendStatOut
    text_signal: TrendStatOut
    consistency: TrendConsistencyOut
    behavior: TrendBehaviorOut


class TrendScatterPointOut(BaseModel):
    date: str
    session_id: str
    captured_at: str
    kind: str
    valence: float
    signal: float
    arousal: Optional[float] = None
    emotion_label: Optional[str] = None
    review_color: Optional[str] = None
    review_rules: list[str] = Field(default_factory=list)
    review_id: Optional[str] = None


class TrendQuadrantsOut(BaseModel):
    q1: int
    q2: int
    q3: int
    q4: int


class TrendSummaryOut(BaseModel):
    analyzed_count: int
    avg_valence: Optional[float] = None
    avg_signal: Optional[float] = None
    valence_std: Optional[float] = None
    signal_std: Optional[float] = None
    coverage_rate: float
    quadrants: TrendQuadrantsOut
    signals: list[str] = Field(default_factory=list)


class SubjectTrendsOut(BaseModel):
    subject_id: str
    start_date: str
    end_date: str
    interval_days: TrendIntervalDaysOut
    days: list[TrendDayOut] = Field(default_factory=list)
    scatter_points: list[TrendScatterPointOut] = Field(default_factory=list)
    summary: TrendSummaryOut
    degraded: list[str] = Field(default_factory=list)


# ---- 思想汇报同步（api@1.5 §7.15-§7.17 / db@1.5 §7）----


class SensevoiceSyncRequest(BaseModel):
    session_id: Optional[str] = None


class SensevoiceSyncItemOut(BaseModel):
    sync_id: str
    subject_id: str
    session_id: str
    status: str
    provider: str
    emotion_primary: Optional[str] = None
    emotion_confidence: Optional[float] = None
    data_version: str
    operator: str
    created_at: str


class SensevoiceSyncListOut(BaseModel):
    items: list[SensevoiceSyncItemOut]
    page: int
    page_size: int
    total: int


class SensevoiceSyncOut(SensevoiceSyncItemOut):
    """POST 成功返回的同步摘要（字段同列表项）。"""


class SensevoiceSyncDetailOut(SensevoiceSyncItemOut):
    transcript_text: str
    transcript_language: Optional[str] = None
    emotion: dict = Field(default_factory=dict)
    updated_at: str


# ---- AI 援助（api@1.5 §7.19-§7.20）----


class AiAssistStatusOut(BaseModel):
    enabled: bool
    web_search: bool
    model: Optional[str] = None
    notice: Optional[str] = None


class AiChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(..., min_length=1, max_length=2000)


class AiChatRequest(BaseModel):
    subject_id: str = Field(..., min_length=1, max_length=64)
    messages: list[AiChatMessage] = Field(..., min_length=1, max_length=12)
