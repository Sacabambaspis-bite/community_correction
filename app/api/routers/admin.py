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
    TicketDetailOut,
    TicketListItemOut,
    TicketListOut,
    TicketTransitionOut,
    TicketTransitionRequest,
    TrendPointOut,
)
from app.capture.config import STORAGE_ROOT
from app.db.models import AuditLog, CaptureSession, Review, ReviewTicket, Subject

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
