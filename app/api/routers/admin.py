"""管理端路由：对象列表、会话列表、面部图查看（留痕）。"""

from __future__ import annotations

import json
import logging
import re
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import FileResponse
from sqlalchemy import desc, func, or_, select
from sqlalchemy.orm import Session

from app.analysis.errors import AnalysisInputError
from app.analysis.paths import resolve_session_file, transcript_relative_path
from app.api.aggregation import (
    TrendRangeError,
    build_trends,
    resolve_date_range,
    to_local_date,
)
from app.api.deps import get_db, require_admin
from app.api.errors import (
    INTERNAL_ERROR,
    INVALID_REQUEST,
    NOT_FOUND,
    STATE_CONFLICT,
    BizError,
    current_request_id,
    envelope,
)
from app.api.integration import (
    compute_and_persist_review,
    load_usable_sessions,
    now_iso,
    scan_subject_overdue,
    serialize_review,
    serialize_ticket_detail,
    serialize_ticket_list_item,
)
from app.api.schemas import (
    DashboardOut,
    ReviewCreateRequest,
    SessionListItem,
    SessionListOut,
    SubjectFrequencyOut,
    SubjectFrequencyRequest,
    SubjectListItem,
    SubjectListOut,
    SubjectTrendsOut,
    TicketDetailOut,
    TicketListItemOut,
    TicketListOut,
    TicketTransitionOut,
    TicketTransitionRequest,
    TrendPointOut,
)
from app.capture.config import STORAGE_ROOT
from app.db.models import (
    AuditLog,
    CaptureSession,
    Review,
    ReviewTicket,
    Subject,
)

logger = logging.getLogger("app.api")

router = APIRouter(prefix="/api/admin", tags=["admin"])

_SUBJECT_STATUSES = frozenset({"active", "suspended", "closed"})
_SESSION_STATUSES = frozenset({"created", "captured", "failed"})
_TICKET_STATUSES = frozenset({"pending", "confirmed", "corrected", "closed"})
_PRIORITIES = frozenset({"P0", "P1", "P2"})
_COLORS = ("green", "blue", "yellow", "orange", "red")
_WINDOW_END_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _load_rules(raw: Optional[str]) -> list[str]:
    try:
        value = json.loads(raw or "[]")
    except (TypeError, ValueError):
        return []
    return value if isinstance(value, list) else []


def _subject_summary(
    db: Session, subject: Subject, states: dict[str, dict]
) -> SubjectListItem:
    """对象列表与详情共用的摘要序列化。"""
    review = db.scalars(
        select(Review)
        .where(Review.subject_id == subject.id)
        .order_by(desc(Review.created_at))
        .limit(1)
    ).first()
    pending_tickets = db.scalar(
        select(func.count())
        .select_from(ReviewTicket)
        .where(
            ReviewTicket.subject_id == subject.id,
            ReviewTicket.status == "pending",
        )
    ) or 0
    latest_session_at = db.scalar(
        select(func.max(CaptureSession.captured_at)).where(
            CaptureSession.subject_id == subject.id
        )
    )
    return SubjectListItem(
        subject_id=subject.id,
        code=subject.code,
        name=subject.name,
        status=subject.status,
        checkin_interval_days=subject.checkin_interval_days,
        report_interval_days=subject.report_interval_days,
        latest_color=review.final_color if review else None,
        latest_color_at=review.created_at if review else None,
        latest_rules=_load_rules(review.rules_fired) if review else [],
        pending_tickets=pending_tickets,
        latest_session_at=latest_session_at,
        overdue={kind: state["overdue"] for kind, state in states.items()},
    )


@router.get("/subjects")
def list_subjects(
    keyword: Optional[str] = None,
    status: Optional[str] = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    _role: str = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    if status is not None and status not in _SUBJECT_STATUSES:
        raise BizError(INVALID_REQUEST, "invalid_request")

    conditions = []
    if keyword:
        like = f"%{keyword}%"
        conditions.append(or_(Subject.code.like(like), Subject.name.like(like)))
    if status is not None:
        conditions.append(Subject.status == status)

    count_stmt = select(func.count()).select_from(Subject)
    list_stmt = select(Subject)
    for condition in conditions:
        count_stmt = count_stmt.where(condition)
        list_stmt = list_stmt.where(condition)

    total = db.scalar(count_stmt) or 0
    subjects = db.scalars(
        list_stmt.order_by(desc(Subject.created_at))
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()

    states_by_subject = {
        subject.id: scan_subject_overdue(db, subject) for subject in subjects
    }
    db.commit()
    items = [
        _subject_summary(db, subject, states_by_subject[subject.id])
        for subject in subjects
    ]

    return envelope(
        data=SubjectListOut(
            items=items, page=page, page_size=page_size, total=total
        ).model_dump()
    )


@router.get("/subjects/{subject_id}")
def get_subject(
    subject_id: str,
    _role: str = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    subject = db.get(Subject, subject_id)
    if subject is None:
        raise BizError(NOT_FOUND, "not_found")
    states = scan_subject_overdue(db, subject)
    db.commit()
    return envelope(data=_subject_summary(db, subject, states).model_dump())


@router.patch("/subjects/{subject_id}/frequency")
def update_subject_frequency(
    subject_id: str,
    payload: SubjectFrequencyRequest,
    _role: str = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    if (
        payload.checkin_interval_days is None
        and payload.report_interval_days is None
    ):
        raise BizError(INVALID_REQUEST, "invalid_request")
    subject = db.get(Subject, subject_id)
    if subject is None:
        raise BizError(NOT_FOUND, "not_found")

    changes: dict[str, int] = {}
    if payload.checkin_interval_days is not None:
        subject.checkin_interval_days = payload.checkin_interval_days
        changes["checkin_interval_days"] = payload.checkin_interval_days
    if payload.report_interval_days is not None:
        subject.report_interval_days = payload.report_interval_days
        changes["report_interval_days"] = payload.report_interval_days

    now = _now()
    subject.updated_at = now
    db.add(
        AuditLog(
            actor_type="staff",
            actor_id=None,
            action="frequency.update",
            target_type="subject",
            target_id=subject.id,
            detail_json=json.dumps(changes),
            request_id=current_request_id(),
            created_at=now,
        )
    )
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise

    return envelope(
        data=SubjectFrequencyOut(
            subject_id=subject.id,
            checkin_interval_days=subject.checkin_interval_days,
            report_interval_days=subject.report_interval_days,
        ).model_dump()
    )


@router.get("/sessions")
def list_sessions(
    subject_id: Optional[str] = None,
    status: Optional[str] = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    _role: str = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    if status is not None and status not in _SESSION_STATUSES:
        raise BizError(INVALID_REQUEST, "invalid_request")

    conditions = []
    if subject_id is not None:
        conditions.append(CaptureSession.subject_id == subject_id)
    if status is not None:
        conditions.append(CaptureSession.status == status)

    count_stmt = select(func.count()).select_from(CaptureSession)
    list_stmt = select(CaptureSession)
    for condition in conditions:
        count_stmt = count_stmt.where(condition)
        list_stmt = list_stmt.where(condition)

    total = db.scalar(count_stmt) or 0
    sessions = db.scalars(
        list_stmt.order_by(desc(CaptureSession.created_at))
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()

    items = [
        SessionListItem(
            session_id=session.id,
            subject_id=session.subject_id,
            kind=session.kind,
            status=session.status,
            capture_status=session.capture_status,
            coverage=session.coverage,
            analysis_status=session.analysis_status,
            captured_at=session.captured_at,
        )
        for session in sessions
    ]

    return envelope(
        data=SessionListOut(
            items=items, page=page, page_size=page_size, total=total
        ).model_dump()
    )


@router.get("/sessions/{session_id}/face")
def get_session_face(
    session_id: str,
    _role: str = Depends(require_admin),
    db: Session = Depends(get_db),
):
    session = db.get(CaptureSession, session_id)
    if session is None or not session.face_path:
        raise BizError(NOT_FOUND, "not_found")

    root = Path(STORAGE_ROOT).resolve()
    target = (root / session.face_path).resolve()
    if not target.is_relative_to(root) or not target.is_file():
        raise BizError(NOT_FOUND, "not_found")

    db.add(
        AuditLog(
            actor_type="staff",
            actor_id=None,
            action="sensitive.view",
            target_type="session",
            target_id=session_id,
            detail_json=json.dumps({"field": "face"}),
            request_id=current_request_id(),
            created_at=_now(),
        )
    )
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise BizError(INTERNAL_ERROR, "audit_write_failed")

    return FileResponse(target, media_type="image/jpeg")


# ---- 媒体读取（api.md §7.21 / §7.22）----

#: 管理端展示用转写文本上限，避免把超长原文整段返回。
_TRANSCRIPT_MAX_CHARS = 2000


def _parse_media_date(value: Optional[str]) -> Optional[date]:
    """严格校验 `YYYY-MM-DD`；格式非法统一返回 `1001 invalid_date`。"""
    if value is None:
        return None
    if not _WINDOW_END_PATTERN.match(value):
        raise BizError(INVALID_REQUEST, "invalid_date")
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        raise BizError(INVALID_REQUEST, "invalid_date") from None


def _read_transcript(session: CaptureSession) -> Optional[str]:
    """读取会话目录下的转写文本；越界、缺失或空白一律返回 None。"""
    relative = transcript_relative_path(session.subject_id, session.id)
    try:
        target = resolve_session_file(
            STORAGE_ROOT, session.subject_id, session.id, relative
        )
    except AnalysisInputError:
        return None
    if not target.is_file():
        return None
    try:
        text = target.read_text(encoding="utf-8", errors="replace").strip()
    except OSError:
        return None
    return text[:_TRANSCRIPT_MAX_CHARS] if text else None


def _analysis_channels(session: CaptureSession) -> dict:
    """解析 `analysis_json.channels`；未分析或结构异常时返回空 dict。"""
    raw = getattr(session, "analysis_json", None)
    if not raw:
        return {}
    try:
        payload = json.loads(raw)
    except (TypeError, ValueError):
        return {}
    if not isinstance(payload, dict):
        return {}
    channels = payload.get("channels")
    return channels if isinstance(channels, dict) else {}


def _channel_parts(channels: dict, name: str) -> tuple[dict, dict]:
    """取通道外层（status/model_version）与 output；类型不符一律视为空。"""
    channel = channels.get(name)
    channel = channel if isinstance(channel, dict) else {}
    output = channel.get("output")
    output = output if isinstance(output, dict) else {}
    return channel, output


def _media_analysis(session: CaptureSession) -> dict:
    """提取人脸、语音情感、心理文本三路只读结果；无输出时对应项为 None。"""
    channels = _analysis_channels(session)

    face_channel, face_output = _channel_parts(channels, "face")
    face = None
    if face_output:
        face = {
            "status": face_channel.get("status"),
            "model_version": face_channel.get("model_version"),
            "expression_label": face_output.get("expression_label"),
            "intensity": face_output.get("intensity"),
            "face_confidence": face_output.get("face_confidence"),
            "frame_count": face_output.get("frame_count"),
            "valid_frames": face_output.get("valid_frames"),
        }

    emotion_channel, emotion_output = _channel_parts(channels, "emotion")
    emotion = None
    if emotion_output:
        emotion = {
            "status": emotion_channel.get("status"),
            "model_version": emotion_channel.get("model_version"),
            "valence": emotion_output.get("valence"),
            "arousal": emotion_output.get("arousal"),
            "label": emotion_output.get("label"),
        }

    psych_channel, psych_output = _channel_parts(channels, "psych")
    psych = None
    if psych_output:
        raw_keywords = psych_output.get("keywords")
        keywords = (
            [item for item in raw_keywords if isinstance(item, str)]
            if isinstance(raw_keywords, list)
            else []
        )
        psych = {
            "status": psych_channel.get("status"),
            "model_version": psych_channel.get("model_version"),
            "signal_strength": psych_output.get("signal_strength"),
            "intent_flag": psych_output.get("intent_flag"),
            "keywords": keywords,
            "rationale_signal": psych_output.get("rationale_signal"),
        }

    return {"face": face, "emotion": emotion, "psych": psych}


def _load_evidence(raw: Optional[str]) -> list[dict]:
    """解析 `evidence_json`；仅保留对象行，结构异常时返回空列表。"""
    try:
        value = json.loads(raw or "[]")
    except (TypeError, ValueError):
        return []
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _media_review_index(db: Session, subject_id: str) -> dict[str, dict]:
    """按 session_id 取最新一条包含该会话证据的复盘。

    同一会话可能被多次复盘覆盖，`reviews` 按创建时间倒序，先到先得；
    规则名只取该会话证据行涉及的 `rule_id`，确保「规则名称与证据」一一对应。
    """
    reviews = db.scalars(
        select(Review)
        .where(Review.subject_id == subject_id)
        .order_by(desc(Review.created_at))
    ).all()

    index: dict[str, dict] = {}
    for review in reviews:
        grouped: dict[str, list[dict]] = {}
        for row in _load_evidence(review.evidence_json):
            session_id = row.get("session_id")
            if not isinstance(session_id, str) or session_id in index:
                continue
            grouped.setdefault(session_id, []).append(row)
        for session_id, rows in grouped.items():
            rules: list[str] = []
            for row in rows:
                rule_id = row.get("rule_id")
                if isinstance(rule_id, str) and rule_id not in rules:
                    rules.append(rule_id)
            index[session_id] = {
                "review_color": review.final_color,
                "rules_fired": rules,
                "evidence": rows,
            }
    return index


def _media_record(
    session: CaptureSession,
    transcript: Optional[str],
    analysis: dict,
    review_info: Optional[dict],
) -> dict:
    """单条采集记录：媒体 URL、转写、三路分析与五色证据一并只读透出。"""
    info = review_info or {}
    return {
        "session_id": session.id,
        "kind": session.kind,
        "captured_at": session.captured_at,
        "capture_status": session.capture_status,
        "analysis_status": session.analysis_status,
        "duration_sec": session.duration_sec,
        "image_url": (
            f"/api/admin/sessions/{session.id}/face" if session.face_path else None
        ),
        "audio_url": (
            f"/api/admin/sessions/{session.id}/audio" if session.audio_path else None
        ),
        "transcript_text": transcript,
        "emotion": analysis["emotion"],
        "analysis": analysis,
        "rules_fired": info.get("rules_fired", []),
        "evidence": info.get("evidence", []),
        "review_color": info.get("review_color"),
    }


@router.get("/subjects/{subject_id}/media")
def get_subject_media(
    subject_id: str,
    date_str: Optional[str] = Query(default=None, alias="date"),
    _role: str = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    subject = db.get(Subject, subject_id)
    if subject is None:
        raise BizError(NOT_FOUND, "not_found")
    requested = _parse_media_date(date_str)

    sessions = (
        db.execute(
            select(CaptureSession)
            .where(CaptureSession.subject_id == subject_id)
            .where(CaptureSession.status == "captured")
            .order_by(desc(CaptureSession.captured_at))
        )
        .scalars()
        .all()
    )

    by_day: dict[date, list[CaptureSession]] = {}
    for session in sessions:
        day = to_local_date(session.captured_at)
        if day is None:
            continue
        by_day.setdefault(day, []).append(session)

    available = sorted(by_day, reverse=True)
    chosen = requested if requested is not None else (available[0] if available else None)
    selected = by_day.get(chosen, []) if chosen is not None else []

    # 查询结果按 captured_at 降序；反转为升序（最早在前、最新在后），
    # 前端默认选中最后一条即「该日最近更新的记录」。
    review_index = _media_review_index(db, subject_id)
    records: list[dict] = []
    transcript_count = 0
    for session in reversed(selected):
        transcript = _read_transcript(session)
        if transcript is not None:
            transcript_count += 1
        records.append(
            _media_record(
                session,
                transcript,
                _media_analysis(session),
                review_index.get(session.id),
            )
        )

    if transcript_count:
        db.add(
            AuditLog(
                actor_type="staff",
                actor_id=None,
                action="sensitive.view",
                target_type="subject",
                target_id=subject_id,
                detail_json=json.dumps(
                    {
                        "field": "transcript",
                        "date": chosen.isoformat(),
                        "count": transcript_count,
                    }
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

    resolved = chosen or requested or date.today()
    return envelope(
        data={
            "subject_id": subject_id,
            "date": resolved.isoformat(),
            "available_dates": [day.isoformat() for day in available],
            "items": records,
        }
    )


@router.get("/sessions/{session_id}/audio")
def get_session_audio(
    session_id: str,
    _role: str = Depends(require_admin),
    db: Session = Depends(get_db),
):
    session = db.get(CaptureSession, session_id)
    if session is None or not session.audio_path:
        raise BizError(NOT_FOUND, "not_found")

    root = Path(STORAGE_ROOT).resolve()
    target = (root / session.audio_path).resolve()
    if not target.is_relative_to(root) or not target.is_file():
        raise BizError(NOT_FOUND, "not_found")

    db.add(
        AuditLog(
            actor_type="staff",
            actor_id=None,
            action="sensitive.view",
            target_type="session",
            target_id=session_id,
            detail_json=json.dumps({"field": "audio"}),
            request_id=current_request_id(),
            created_at=_now(),
        )
    )
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise BizError(INTERNAL_ERROR, "audit_write_failed")

    return FileResponse(target, media_type="audio/wav")


# ---- 复盘（api.md §7.9 / §7.14）----


def _parse_window_end(value: Optional[str]) -> date:
    """`window_end` 必须是严格 `YYYY-MM-DD`；缺省取本地今天。"""
    if value is None:
        return datetime.now().astimezone().date()
    if not _WINDOW_END_PATTERN.match(value):
        raise BizError(INVALID_REQUEST, "invalid_request")
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise BizError(INVALID_REQUEST, "invalid_request") from None


@router.post("/reviews")
def create_review(
    payload: ReviewCreateRequest,
    _role: str = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    subject = db.get(Subject, payload.subject_id)
    if subject is None:
        raise BizError(NOT_FOUND, "not_found")

    end_date = _parse_window_end(payload.window_end)
    start_date = end_date - timedelta(days=payload.window_days - 1)
    window_start = start_date.isoformat()
    window_end = end_date.isoformat()

    usable = load_usable_sessions(db, subject.id, window_start, window_end)
    if not usable:
        raise BizError(STATE_CONFLICT, "no_session_in_window")

    source = usable[-1]
    now = now_iso()
    review, _ticket, _created = compute_and_persist_review(
        db,
        subject,
        source,
        window_start,
        window_end,
        payload.window_days,
        now,
    )
    db.add(
        AuditLog(
            actor_type="staff",
            actor_id=None,
            action="review.create",
            target_type="review",
            target_id=review.id,
            detail_json=json.dumps({}),
            request_id=current_request_id(),
            created_at=now,
        )
    )
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise

    return envelope(data=serialize_review(review))


@router.get("/reviews/{review_id}")
def get_review(
    review_id: str,
    _role: str = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    review = db.get(Review, review_id)
    if review is None:
        raise BizError(NOT_FOUND, "not_found")
    return envelope(data=serialize_review(review))


# ---- 工单（api.md §7.10 / §7.12 / §7.13）----


def _load_json_obj(raw: Optional[str]) -> dict:
    try:
        value = json.loads(raw or "{}")
    except (TypeError, ValueError):
        return {}
    return value if isinstance(value, dict) else {}


@router.get("/tickets")
def list_tickets(
    status: Optional[str] = None,
    priority: Optional[str] = None,
    subject_id: Optional[str] = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    _role: str = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    if status is not None and status not in _TICKET_STATUSES:
        raise BizError(INVALID_REQUEST, "invalid_request")
    if priority is not None and priority not in _PRIORITIES:
        raise BizError(INVALID_REQUEST, "invalid_request")

    conditions = []
    if status is not None:
        conditions.append(ReviewTicket.status == status)
    if priority is not None:
        conditions.append(ReviewTicket.priority == priority)
    if subject_id is not None:
        conditions.append(ReviewTicket.subject_id == subject_id)

    count_stmt = select(func.count()).select_from(ReviewTicket)
    list_stmt = (
        select(ReviewTicket, Review, Subject)
        .outerjoin(Review, ReviewTicket.review_id == Review.id)
        .join(Subject, ReviewTicket.subject_id == Subject.id)
    )
    for condition in conditions:
        count_stmt = count_stmt.where(condition)
        list_stmt = list_stmt.where(condition)

    total = db.scalar(count_stmt) or 0
    rows = db.execute(
        list_stmt.order_by(
            ReviewTicket.priority.asc(), ReviewTicket.opened_at.desc()
        )
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()

    items = [
        TicketListItemOut(
            **serialize_ticket_list_item(ticket, review, subject)
        )
        for ticket, review, subject in rows
    ]
    return envelope(
        data=TicketListOut(
            items=items, page=page, page_size=page_size, total=total
        ).model_dump()
    )


def _ticket_history(db: Session, ticket: ReviewTicket) -> list[dict]:
    """建单记录 + 流转留痕，按时间升序。"""
    history = [
        {
            "action": "opened",
            "actor": "system",
            "note": None,
            "at": ticket.opened_at,
        }
    ]
    logs = db.scalars(
        select(AuditLog)
        .where(
            AuditLog.action == "ticket.transition",
            AuditLog.target_type == "ticket",
            AuditLog.target_id == ticket.id,
        )
        .order_by(AuditLog.created_at.asc(), AuditLog.id.asc())
    ).all()
    for log in logs:
        detail = _load_json_obj(log.detail_json)
        history.append(
            {
                "action": detail.get("action") or "unknown",
                "actor": log.actor_id or "staff",
                "note": detail.get("note"),
                "at": log.created_at,
            }
        )
    return history


@router.get("/tickets/{ticket_id}")
def get_ticket(
    ticket_id: str,
    _role: str = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    ticket = db.get(ReviewTicket, ticket_id)
    if ticket is None:
        raise BizError(NOT_FOUND, "not_found")

    review = db.get(Review, ticket.review_id)
    subject = db.get(Subject, ticket.subject_id)

    now = now_iso()
    db.add(
        AuditLog(
            actor_type="staff",
            actor_id=None,
            action="sensitive.view",
            target_type="ticket",
            target_id=ticket.id,
            detail_json=json.dumps({"field": "ticket"}),
            request_id=current_request_id(),
            created_at=now,
        )
    )
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise BizError(INTERNAL_ERROR, "audit_write_failed")

    history = _ticket_history(db, ticket)
    return envelope(
        data=TicketDetailOut(
            **serialize_ticket_detail(ticket, review, subject, history)
        ).model_dump()
    )


@router.post("/tickets/{ticket_id}/transition")
def transition_ticket(
    ticket_id: str,
    payload: TicketTransitionRequest,
    _role: str = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    ticket = db.get(ReviewTicket, ticket_id)
    if ticket is None:
        raise BizError(NOT_FOUND, "not_found")
    if ticket.status == "closed":
        raise BizError(STATE_CONFLICT, "ticket_closed")

    note = payload.note.strip() if isinstance(payload.note, str) else ""
    note = note or None

    if payload.action == "correct":
        if payload.conclusion_color not in _COLORS or note is None:
            raise BizError(INVALID_REQUEST, "invalid_request")
    elif payload.action == "close":
        if note is None:
            raise BizError(INVALID_REQUEST, "invalid_request")

    previous_status = ticket.status
    now = now_iso()
    ticket.status = "closed"
    ticket.closed_at = now
    if payload.conclusion_color is not None:
        ticket.conclusion_color = payload.conclusion_color
    if note is not None:
        ticket.conclusion_note = note
    if payload.assignee is not None:
        ticket.assignee = payload.assignee

    db.add(
        AuditLog(
            actor_type="staff",
            actor_id=payload.assignee,
            action="ticket.transition",
            target_type="ticket",
            target_id=ticket.id,
            detail_json=json.dumps(
                {
                    "action": payload.action,
                    "previous_status": previous_status,
                    "conclusion_color": ticket.conclusion_color,
                    "note": ticket.conclusion_note,
                },
                ensure_ascii=False,
            ),
            request_id=current_request_id(),
            created_at=now,
        )
    )
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise

    return envelope(
        data=TicketTransitionOut(
            ticket_id=ticket.id,
            status=ticket.status,
            previous_status=previous_status,
            action=payload.action,
            conclusion_color=ticket.conclusion_color,
            conclusion_note=ticket.conclusion_note,
            assignee=ticket.assignee,
            closed_at=ticket.closed_at,
        ).model_dump()
    )


# ---- 看板（api.md §7.11）----


def _review_date(review: Review) -> Optional[date]:
    try:
        return datetime.fromisoformat(review.created_at).date()
    except (TypeError, ValueError):
        return None


@router.get("/dashboard")
def dashboard(
    subject_id: Optional[str] = None,
    _role: str = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    if subject_id is None:
        latest = db.scalars(
            select(CaptureSession)
            .where(CaptureSession.status == "captured")
            .order_by(desc(CaptureSession.captured_at))
            .limit(1)
        ).first()
        if latest is None:
            raise BizError(NOT_FOUND, "not_found")
        subject = db.get(Subject, latest.subject_id)
    else:
        subject = db.get(Subject, subject_id)
    if subject is None:
        raise BizError(NOT_FOUND, "not_found")

    states = scan_subject_overdue(db, subject)
    db.commit()
    reviews = db.scalars(
        select(Review).where(Review.subject_id == subject.id)
    ).all()

    distribution = {color: 0 for color in _COLORS}
    for review in reviews:
        if review.final_color in distribution:
            distribution[review.final_color] += 1

    today = datetime.now().astimezone().date()
    cutoff = today - timedelta(days=6)
    latest_by_date: dict[date, Review] = {}
    for review in reviews:
        review_date = _review_date(review)
        if review_date is None or review_date < cutoff or review_date > today:
            continue
        current = latest_by_date.get(review_date)
        if current is None or review.created_at > current.created_at:
            latest_by_date[review_date] = review

    trend = [
        TrendPointOut(date=day.isoformat(), color=latest_by_date[day].final_color)
        for day in sorted(latest_by_date)
    ]

    pending_tickets = db.scalar(
        select(func.count())
        .select_from(ReviewTicket)
        .where(
            ReviewTicket.subject_id == subject.id,
            ReviewTicket.status == "pending",
        )
    ) or 0
    last_session_at = db.scalar(
        select(func.max(CaptureSession.captured_at)).where(
            CaptureSession.subject_id == subject.id,
            CaptureSession.status == "captured",
        )
    )

    return envelope(
        data=DashboardOut(
            subject_id=subject.id,
            color_distribution=distribution,
            trend_7d=trend,
            pending_tickets=pending_tickets,
            last_session_at=last_session_at,
            overdue={kind: state["overdue"] for kind, state in states.items()},
        ).model_dump()
    )


# ---- 对象心理状态趋势（api.md §7.18）----


def _trend_review_records(reviews: list[Review]) -> list[dict]:
    """把复盘 ORM 行转成聚合所需的只读快照（不含证据原文）。"""
    return [
        {
            "review_id": review.id,
            "window_end": review.window_end,
            "created_at": review.created_at,
            "color": review.final_color,
            "rules_fired": _load_rules(review.rules_fired),
            "consistency": review.consistency,
            "manual_review": bool(review.manual_review),
            "evidence_available": bool(_load_rules(review.evidence_json)),
        }
        for review in reviews
    ]


@router.get("/subjects/{subject_id}/trends")
def get_subject_trends(
    subject_id: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    _role: str = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    today = datetime.now().astimezone().date()
    try:
        start, end = resolve_date_range(start_date, end_date, today)
    except TrendRangeError as exc:
        raise BizError(INVALID_REQUEST, exc.reason) from None

    subject = db.get(Subject, subject_id)
    if subject is None:
        raise BizError(NOT_FOUND, "not_found")

    # 一次取该对象全部带捕获时间的会话：区间聚合与行为锚点都在 Python 内完成，避免 N+1。
    sessions = db.scalars(
        select(CaptureSession).where(
            CaptureSession.subject_id == subject_id,
            CaptureSession.captured_at.is_not(None),
        )
    ).all()
    anchors: dict[str, Optional[date]] = {"checkin": None, "report": None}
    session_records = []
    for session in sessions:
        captured_day = to_local_date(session.captured_at)
        if session.status == "captured" and captured_day is not None:
            if captured_day <= end:
                current = anchors.get(session.kind)
                if current is None or captured_day > current:
                    anchors[session.kind] = captured_day
        session_records.append(
            {
                "session_id": session.id,
                "kind": session.kind,
                "status": session.status,
                "analysis_status": session.analysis_status,
                "captured_at": session.captured_at,
                "analysis_json": session.analysis_json,
            }
        )

    reviews = db.scalars(
        select(Review).where(Review.subject_id == subject_id)
    ).all()

    data = build_trends(
        subject_id=subject.id,
        start=start,
        end=end,
        interval_days={
            "checkin": subject.checkin_interval_days,
            "report": subject.report_interval_days,
        },
        sessions=session_records,
        reviews=_trend_review_records(list(reviews)),
        behavior_anchors=anchors,
    )
    return envelope(data=SubjectTrendsOut(**data).model_dump())
