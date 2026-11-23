"""管理端路由：对象列表、会话列表、面部图查看（留痕）。"""

from __future__ import annotations

import json
import logging
from datetime import datetime
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
    BizError,
    current_request_id,
    envelope,
)
from app.api.schemas import (
    SessionListItem,
    SessionListOut,
    SubjectListItem,
    SubjectListOut,
)
from app.capture.config import STORAGE_ROOT
from app.db.models import AuditLog, CaptureSession, Review, ReviewTicket, Subject

logger = logging.getLogger("app.api")

router = APIRouter(prefix="/api/admin", tags=["admin"])

_SUBJECT_STATUSES = frozenset({"active", "suspended", "closed"})
_SESSION_STATUSES = frozenset({"created", "captured", "failed"})


def _now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _load_rules(raw: Optional[str]) -> list[str]:
    try:
        value = json.loads(raw or "[]")
    except (TypeError, ValueError):
        return []
    return value if isinstance(value, list) else []


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

    items: list[SubjectListItem] = []
    for subject in subjects:
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
        items.append(
            SubjectListItem(
                subject_id=subject.id,
                code=subject.code,
                name=subject.name,
                status=subject.status,
                latest_color=review.final_color if review else None,
                latest_color_at=review.created_at if review else None,
                latest_rules=_load_rules(review.rules_fired) if review else [],
                pending_tickets=pending_tickets,
                latest_session_at=latest_session_at,
            )
        )

    return envelope(
        data=SubjectListOut(
            items=items, page=page, page_size=page_size, total=total
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
