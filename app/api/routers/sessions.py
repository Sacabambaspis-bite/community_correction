"""会话相关路由：异步采集、会话查询、分析占位。"""

from __future__ import annotations

import json
import logging
import os
import threading
import uuid
from datetime import datetime
from types import SimpleNamespace
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, Query
from sqlalchemy.orm import Session

from app.api import deps
from app.api.deps import (
    enforce_session_owner,
    get_db,
    require_admin,
    require_any_subject_or_staff,
)
from app.api.routers.user import require_consent
from app.api.errors import (
    ANALYSIS_FAILED,
    CAPTURE_FAILED,
    INTERNAL_ERROR,
    NOT_FOUND,
    SESSION_NOT_CAPTURED,
    BizError,
    envelope,
)
from app.api.schemas import (
    CreateSessionOut,
    CreateSessionRequest,
    SessionOut,
    degraded_flags,
)
from app.capture.config import STORAGE_ROOT
from app.db.models import CaptureSession, Subject

logger = logging.getLogger("app.api")

router = APIRouter(prefix="/api", tags=["sessions"])

#: 同一时刻只允许一个采集任务。
_CAPTURE_LOCK = threading.Lock()


def _now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _release_capture_lock() -> None:
    try:
        _CAPTURE_LOCK.release()
    except RuntimeError:
        # 未持有时释放会抛 RuntimeError，忽略即可。
        pass


def _load_json_list(raw: Optional[str]) -> list[str]:
    try:
        value = json.loads(raw or "[]")
    except (TypeError, ValueError):
        return []
    return value if isinstance(value, list) else []


def _capture_result(
    *,
    subject_id: str,
    session_id: str,
    device_index: int,
    duration_sec: float,
):
    """采集入口：`CAPTURE_FAKE=1` 时返回假结果，测试不触达真实摄像头。"""
    if os.environ.get("CAPTURE_FAKE") == "1":
        base = f"subjects/{subject_id}/sessions/{session_id}"
        return SimpleNamespace(
            capture_status="ok",
            face_path=f"{base}/face.jpg",
            audio_path=f"{base}/audio.wav",
            codes=[],
            meta={
                "finished_at": _now(),
                "audio": {"duration_sec": duration_sec},
            },
        )

    from app.capture.session import run_capture_session

    return run_capture_session(
        subject_id=subject_id,
        session_id=session_id,
        storage_root=STORAGE_ROOT,
        device_index=device_index,
        duration_sec=duration_sec,
    )


def _run_capture_and_persist(
    *,
    session_id: str,
    subject_id: str,
    device_index: int,
    duration_sec: float,
) -> None:
    """后台采集：独立会话、独立事务，结束后必定释放并发闸。

    必须保持同步 `def`：FastAPI 会把它放到线程池执行，`threading.Lock` 才能生效。
    """
    factory = deps.get_session_factory()
    db = factory()
    try:
        result = _capture_result(
            subject_id=subject_id,
            session_id=session_id,
            device_index=device_index,
            duration_sec=duration_sec,
        )
        session = db.get(CaptureSession, session_id)
        if session is None:
            logger.warning("capture.session_missing session_id=%s", session_id)
            return
        status = "captured" if (result.face_path or result.audio_path) else "failed"
        audio_meta = result.meta.get("audio") or {}
        session.status = status
        session.capture_status = result.capture_status
        session.face_path = result.face_path
        session.audio_path = result.audio_path
        session.codes = json.dumps(result.codes)
        session.duration_sec = audio_meta.get("duration_sec")
        session.captured_at = result.meta.get("finished_at")
        session.updated_at = _now()
        db.commit()
        logger.info(
            "capture.done session_id=%s status=%s codes=%s",
            session_id,
            status,
            result.codes,
        )
    except Exception as exc:
        logger.error(
            "capture.error session_id=%s type=%s", session_id, type(exc).__name__
        )
        try:
            db.rollback()
            session = db.get(CaptureSession, session_id)
            if session is not None:
                session.status = "failed"
                session.capture_status = "error"
                session.codes = '["unknown"]'
                session.updated_at = _now()
                db.commit()
        except Exception:
            db.rollback()
            logger.error("capture.persist_failed session_id=%s", session_id)
    finally:
        db.close()
        _release_capture_lock()


@router.post("/sessions")
def create_session(
    payload: CreateSessionRequest,
    background_tasks: BackgroundTasks,
    _role: str = Depends(require_any_subject_or_staff),
    db: Session = Depends(get_db),
) -> dict:
    if not _CAPTURE_LOCK.acquire(blocking=False):
        raise BizError(INTERNAL_ERROR, "capture_busy")
    try:
        subject = db.get(Subject, payload.subject_id)
        if subject is None:
            raise BizError(NOT_FOUND, "subject_not_found")
        # 并发闸 → subject 存在 → consent 三道闸（api.md §7.2）。
        require_consent(subject)

        session_id = str(uuid.uuid4())
        now = _now()
        db.add(
            CaptureSession(
                id=session_id,
                subject_id=payload.subject_id,
                status="created",
                capture_status=None,
                analysis_status="pending",
                created_at=now,
                updated_at=now,
            )
        )
        db.commit()
        background_tasks.add_task(
            _run_capture_and_persist,
            session_id=session_id,
            subject_id=payload.subject_id,
            device_index=payload.device_index,
            duration_sec=payload.duration_sec,
        )
    except Exception:
        _release_capture_lock()
        raise
    return envelope(data=CreateSessionOut(session_id=session_id, status="created").model_dump())


@router.get("/sessions/{session_id}")
def get_session(
    session_id: str,
    subject_id: Optional[str] = Query(default=None),
    _role: str = Depends(require_any_subject_or_staff),
    db: Session = Depends(get_db),
) -> dict:
    session = db.get(CaptureSession, session_id)
    if session is None:
        raise BizError(NOT_FOUND, "not_found")
    enforce_session_owner(session, _role, subject_id)

    degraded = degraded_flags(session.capture_status, session.analysis_status)
    data = SessionOut(
        session_id=session.id,
        subject_id=session.subject_id,
        status=session.status,
        capture_status=session.capture_status,
        coverage=session.coverage,
        face_available=bool(session.face_path),
        audio_available=bool(session.audio_path),
        duration_sec=session.duration_sec,
        captured_at=session.captured_at,
        analysis_status=session.analysis_status,
        codes=_load_json_list(session.codes),
        created_at=session.created_at,
        updated_at=session.updated_at,
    ).model_dump()

    if session.status == "failed":
        return envelope(
            code=CAPTURE_FAILED,
            message="capture_failed",
            data=data,
            degraded=degraded,
        )
    if session.analysis_status == "failed":
        return envelope(
            code=ANALYSIS_FAILED,
            message="analysis_failed",
            data=data,
            degraded=degraded,
        )
    return envelope(data=data, degraded=degraded)


@router.post("/sessions/{session_id}/analyze")
def analyze_session(
    session_id: str,
    _role: str = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    session = db.get(CaptureSession, session_id)
    if session is None:
        raise BizError(NOT_FOUND, "not_found")
    if session.status == "created":
        raise BizError(SESSION_NOT_CAPTURED, "session_not_captured")
    if session.status == "failed":
        raise BizError(CAPTURE_FAILED, "capture_failed")
    raise BizError(INTERNAL_ERROR, "analysis_pipeline_not_ready")
