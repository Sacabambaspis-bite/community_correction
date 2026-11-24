"""用户端路由：同意状态读写与中性结果反馈（api.md §5.3 / §7.1 / §7.8）。"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import enforce_session_owner, get_db, require_user
from app.api.integration import subject_task_states
from app.api.errors import (
    INTERNAL_ERROR,
    INVALID_REQUEST,
    NOT_FOUND,
    STATE_CONFLICT,
    BizError,
    current_request_id,
    envelope,
)
from app.api.schemas import (
    ConsentGrantRequest,
    ConsentOut,
    ConsentRevokeRequest,
    ConsentScope,
    FeedbackOut,
    TaskKindOut,
    UserTasksOut,
    degraded_flags,
)
from app.db.models import AuditLog, CaptureSession, Subject

logger = logging.getLogger("app.api")

router = APIRouter(prefix="/api/user", tags=["user"])

CONSENT_SCHEMA_VERSION = "consent@1.0"


def _now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


# ---- consent_json 读写工具 ----


def _empty_consent() -> dict:
    """未同意形态：三项均未授权，无撤回时间与留存期。"""
    return {
        "general": {"granted": False, "at": None},
        "face": {"granted": False, "at": None},
        "audio": {"granted": False, "at": None},
        "revoked_at": None,
        "retention_days": None,
    }


def _parse_consent(raw: Optional[str]) -> Optional[dict]:
    """解析 consent_json；`None`、空串或非法 JSON 返回 `None`。"""
    if not raw:
        return None
    try:
        value = json.loads(raw)
    except (TypeError, ValueError):
        return None
    if not isinstance(value, dict) or not value:
        return None
    return value


def _normalize_consent(value: Optional[dict]) -> dict:
    """把任意 consent 结构归一为 `ConsentOut` 所需形态，缺失项一律视为未同意。"""
    result = _empty_consent()
    if not isinstance(value, dict):
        return result

    for key in ("general", "face", "audio"):
        item = value.get(key)
        if isinstance(item, dict):
            at = item.get("at")
            result[key] = {
                "granted": item.get("granted") is True,
                "at": at if isinstance(at, str) else None,
            }

    revoked_at = value.get("revoked_at")
    result["revoked_at"] = revoked_at if isinstance(revoked_at, str) else None
    retention_days = value.get("retention_days")
    result["retention_days"] = (
        retention_days if isinstance(retention_days, int) else None
    )
    return result


def _load_consent(raw: Optional[str]) -> dict:
    """读取同意状态；不存在或解析失败一律返回"未同意"形态。"""
    return _normalize_consent(_parse_consent(raw))


def require_consent(subject: Subject) -> None:
    """发起采集前的三道闸（顺序固定：revoked → general → face/audio）。"""
    consent = _load_consent(subject.consent_json)
    if consent.get("revoked_at"):
        raise BizError(STATE_CONFLICT, "consent_revoked")
    general = consent.get("general") or {}
    if general.get("granted") is not True:
        raise BizError(STATE_CONFLICT, "consent_required")
    face = consent.get("face") or {}
    audio = consent.get("audio") or {}
    if face.get("granted") is not True or audio.get("granted") is not True:
        raise BizError(STATE_CONFLICT, "consent_incomplete")


def _build_consent(face: bool, audio: bool, retention_days: int, at: str) -> dict:
    """按 db.md §2.1 生成待落库的 consent 结构。"""
    return {
        "schema_version": CONSENT_SCHEMA_VERSION,
        "general": {"granted": face or audio, "at": at},
        "face": {"granted": face, "at": at},
        "audio": {"granted": audio, "at": at},
        "revoked_at": None,
        "retention_days": retention_days,
    }


def _consent_out(subject_id: str, raw: Optional[str]) -> dict:
    view = _load_consent(raw)
    return ConsentOut(
        subject_id=subject_id,
        general=ConsentScope(**view["general"]),
        face=ConsentScope(**view["face"]),
        audio=ConsentScope(**view["audio"]),
        revoked_at=view["revoked_at"],
        retention_days=view["retention_days"],
    ).model_dump()


def _get_subject(db: Session, subject_id: str) -> Subject:
    subject = db.get(Subject, subject_id)
    if subject is None:
        raise BizError(NOT_FOUND, "not_found")
    return subject


# ---- 端点 ----


@router.get("/tasks")
def get_tasks(
    subject_id: str = Query(...),
    _role: str = Depends(require_user),
    db: Session = Depends(get_db),
) -> dict:
    """返回签到与汇报任务提示，不暴露色码、规则或分值。"""
    subject = _get_subject(db, subject_id)
    states = subject_task_states(db, subject)
    data = UserTasksOut(
        checkin=TaskKindOut(**states["checkin"]),
        report=TaskKindOut(**states["report"]),
    )
    return envelope(data=data.model_dump())


@router.get("/consent")
def get_consent(
    subject_id: str = Query(...),
    _role: str = Depends(require_user),
    db: Session = Depends(get_db),
) -> dict:
    subject = _get_subject(db, subject_id)
    return envelope(data=_consent_out(subject.id, subject.consent_json))


@router.put("/consent")
def grant_consent(
    payload: ConsentGrantRequest,
    _role: str = Depends(require_user),
    db: Session = Depends(get_db),
) -> dict:
    subject = _get_subject(db, payload.subject_id)
    if not payload.face and not payload.audio:
        raise BizError(INVALID_REQUEST, "invalid_request")

    consent = _build_consent(
        face=payload.face,
        audio=payload.audio,
        retention_days=payload.retention_days,
        at=_now(),
    )
    subject.consent_json = json.dumps(consent)
    subject.updated_at = _now()
    db.add(
        AuditLog(
            actor_type="subject",
            actor_id=subject.id,
            action="consent.grant",
            target_type="subject",
            target_id=subject.id,
            detail_json=json.dumps(
                {"face": payload.face, "audio": payload.audio}
            ),
            request_id=current_request_id(),
            created_at=_now(),
        )
    )
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise BizError(INTERNAL_ERROR, "audit_write_failed")

    return envelope(data=_consent_out(subject.id, subject.consent_json))


@router.post("/consent/revoke")
def revoke_consent(
    payload: ConsentRevokeRequest,
    _role: str = Depends(require_user),
    db: Session = Depends(get_db),
) -> dict:
    subject = _get_subject(db, payload.subject_id)
    stored = _parse_consent(subject.consent_json)
    if stored is None:
        raise BizError(STATE_CONFLICT, "consent_not_granted")

    # 已撤回：幂等返回当前状态，不改 revoked_at、不再留痕。
    if stored.get("revoked_at"):
        return envelope(data=_consent_out(subject.id, subject.consent_json))

    stored["revoked_at"] = _now()
    subject.consent_json = json.dumps(stored)
    subject.updated_at = _now()
    db.add(
        AuditLog(
            actor_type="subject",
            actor_id=subject.id,
            action="consent.revoke",
            target_type="subject",
            target_id=subject.id,
            detail_json=json.dumps({}),
            request_id=current_request_id(),
            created_at=_now(),
        )
    )
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise BizError(INTERNAL_ERROR, "audit_write_failed")

    return envelope(data=_consent_out(subject.id, subject.consent_json))


_FEEDBACK_CAPTURE_DEGRADED = frozenset({"no_face", "no_audio", "no_face_no_audio"})


def _feedback_text(status: str, capture_status: Optional[str]) -> tuple[str, str, str]:
    """按 api.md §7.8 中性映射表返回 (suggestion, summary_text, next_action)。"""
    if status == "created":
        return ("keep_routine", "本次记录仍在进行中。", "请稍候，完成后可查看结果")

    if status == "failed":
        if capture_status == "error":
            return (
                "talk_to_staff",
                "本次记录未完成。",
                "设备暂时不可用，请联系工作人员",
            )
        return ("recapture", "本次记录未完成。", "建议稍后重新采集一次")

    # captured / analyzed 等已完成态。
    if capture_status in _FEEDBACK_CAPTURE_DEGRADED:
        return ("recapture", "本次记录已完成。", "建议稍后重新采集一次")
    if capture_status == "partial":
        return (
            "keep_routine",
            "本次记录已完成。",
            "结果已转工作人员复核，按约定时间再来即可",
        )
    return ("keep_routine", "本次记录已完成。", "下次按约定时间再来即可")


@router.get("/sessions/{session_id}/feedback")
def get_session_feedback(
    session_id: str,
    subject_id: str = Query(...),
    _role: str = Depends(require_user),
    db: Session = Depends(get_db),
) -> dict:
    session = db.get(CaptureSession, session_id)
    if session is None:
        raise BizError(NOT_FOUND, "not_found")
    enforce_session_owner(session, _role, subject_id)

    suggestion, summary_text, next_action = _feedback_text(
        session.status, session.capture_status
    )
    data = FeedbackOut(
        session_id=session.id,
        status=session.status,
        summary_text=summary_text,
        suggestion=suggestion,
        next_action=next_action,
    ).model_dump()
    return envelope(
        data=data,
        degraded=degraded_flags(session.capture_status, session.analysis_status),
    )
