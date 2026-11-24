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
    device_index: int = Field(default=0, ge=0)
    duration_sec: float = Field(default=10, gt=0)


class CreateSessionOut(BaseModel):
    session_id: str
    status: str


class SessionOut(BaseModel):
    session_id: str
    subject_id: str
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
    latest_color: Optional[str] = None
    latest_color_at: Optional[str] = None
    latest_rules: list[str] = Field(default_factory=list)
    pending_tickets: int
    latest_session_at: Optional[str] = None


class SubjectListOut(BaseModel):
    items: list[SubjectListItem]
    page: int
    page_size: int
    total: int


class SessionListItem(BaseModel):
    session_id: str
    subject_id: str
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
    retention_days: int = Field(..., ge=1)


class ConsentRevokeRequest(BaseModel):
    subject_id: str = Field(..., min_length=1, max_length=64)


class FeedbackOut(BaseModel):
    session_id: str
    status: str
    summary_text: str
    suggestion: Literal["keep_routine", "talk_to_staff", "recapture"]
    next_action: str
