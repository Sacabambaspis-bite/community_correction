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
    require_user,
)
from app.api.integration import (
    compute_and_persist_review,
    now_iso,
    persist_analysis,
    run_analysis_for_session,
    window_bounds,
)
from app.api.routers.user import require_consent
from app.api.errors import (
    ANALYSIS_FAILED,
    CAPTURE_FAILED,
    INTERNAL_ERROR,
    NOT_FOUND,
    SESSION_NOT_CAPTURED,
    STATE_CONFLICT,
    BizError,
    current_request_id,
    envelope,
)
from app.api.schemas import (
    CreateSessionOut,
    CreateSessionRequest,
    SessionOut,
    degraded_flags,
)
from app.capture.config import STORAGE_ROOT
from app.db.models import AuditLog, CaptureSession, Subject

logger = logging.getLogger("app.api")

router = APIRouter(prefix="/api", tags=["sessions"])

#: 同一时刻只允许一个采集任务。
_CAPTURE_LOCK = threading.Lock()

#: 活动中的手动 report 会话；终态回写后由后台任务清理。
_MANUAL_STOP_EVENTS: dict[str, threading.Event] = {}
_MANUAL_STOP_EVENTS_LOCK = threading.Lock()


def _register_manual_stop_event(session_id: str) -> threading.Event:
    event = threading.Event()
    with _MANUAL_STOP_EVENTS_LOCK:
        _MANUAL_STOP_EVENTS[session_id] = event
    return event


def _get_manual_stop_event(session_id: str) -> Optional[threading.Event]:
    with _MANUAL_STOP_EVENTS_LOCK:
        return _MANUAL_STOP_EVENTS.get(session_id)


def _discard_manual_stop_event(session_id: str) -> None:
    with _MANUAL_STOP_EVENTS_LOCK:
        _MANUAL_STOP_EVENTS.pop(session_id, None)


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


def _session_payload(session: CaptureSession) -> dict:
    """会话摘要（api.md §7.3 的 data 字段）。"""
    return SessionOut(
        session_id=session.id,
        subject_id=session.subject_id,
        kind=session.kind,
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


def _capture_result(
    *,
    subject_id: str,
    session_id: str,
    kind: str,
    device_index: int,
    duration_sec: Optional[float],
    stop_event: Optional[threading.Event] = None,
):
    """采集入口；手动假采集由 capture 模块等待 stop_event 后生成产物。"""
    manual = kind == "report" and duration_sec is None
    if os.environ.get("CAPTURE_FAKE") == "1" and not manual:
        base = f"subjects/{subject_id}/sessions/{session_id}"
        return SimpleNamespace(
            capture_status="ok",
            face_path=f"{base}/face.jpg",
            audio_path=None if kind == "checkin" else f"{base}/audio.wav",
            codes=[],
            meta={
                "finished_at": _now(),
                "audio": {
                    "duration_sec": None if kind == "checkin" else duration_sec
                },
            },
        )

    from app.capture.session import run_capture_session

    capture_kwargs = {
        "subject_id": subject_id,
        "session_id": session_id,
        "storage_root": STORAGE_ROOT,
        "device_index": device_index,
        "duration_sec": duration_sec,
        "mode": "face_only" if kind == "checkin" else "both",
    }
    if manual:
        capture_kwargs["stop_event"] = stop_event
    return run_capture_session(**capture_kwargs)


def _run_capture_and_persist(
    *,
    session_id: str,
    subject_id: str,
    kind: str,
    device_index: int,
    duration_sec: Optional[float],
    stop_event: Optional[threading.Event] = None,
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
            kind=kind,
            device_index=device_index,
            duration_sec=duration_sec,
            stop_event=stop_event,
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
        if kind == "report" and duration_sec is None:
            _discard_manual_stop_event(session_id)
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
    stop_event: Optional[threading.Event] = None
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
                kind=payload.kind,
                status="created",
                capture_status=None,
                analysis_status="pending",
                created_at=now,
                updated_at=now,
            )
        )
        db.commit()
        if payload.kind == "report" and payload.duration_sec is None:
            stop_event = _register_manual_stop_event(session_id)

        task_kwargs = {
            "session_id": session_id,
            "subject_id": payload.subject_id,
            "kind": payload.kind,
            "device_index": payload.device_index,
            "duration_sec": payload.duration_sec,
            "stop_event": stop_event,
        }
        if stop_event is None:
            background_tasks.add_task(_run_capture_and_persist, **task_kwargs)
        else:
            # TestClient 会等待 BackgroundTasks 完成；手动采集需先返回响应，
            # 让后续 stop 请求能够置位事件。定时路径保持原有调度方式。
            threading.Thread(
                target=_run_capture_and_persist,
                kwargs=task_kwargs,
                daemon=True,
                name=f"capture-{session_id}",
            ).start()
    except Exception:
        if stop_event is not None:
            _discard_manual_stop_event(session_id)
        _release_capture_lock()
        raise
    return envelope(
        data=CreateSessionOut(
            session_id=session_id, status="created", kind=payload.kind
        ).model_dump()
    )


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
    data = _session_payload(session)

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


@router.post("/sessions/{session_id}/stop")
def stop_session(
    session_id: str,
    subject_id: Optional[str] = Query(default=None),
    _role: str = Depends(require_user),
    db: Session = Depends(get_db),
) -> dict:
    """仅置位活动手动会话的停止事件，不写库、不直接推进状态。"""
    session = db.get(CaptureSession, session_id)
    if session is None:
        raise BizError(NOT_FOUND, "not_found")
    enforce_session_owner(session, _role, subject_id)

    if session.kind != "report" or session.status != "created":
        raise BizError(STATE_CONFLICT, "session_not_stoppable")
    stop_event = _get_manual_stop_event(session_id)
    if stop_event is None:
        # 定时 created、checkin，或进程内已无活动手动任务均不可停止。
        raise BizError(STATE_CONFLICT, "session_not_stoppable")

    stop_event.set()
    return envelope(data={"session_id": session.id})


def _write_analyze_audit(db: Session, session_id: str, now: str) -> None:
    """分析触发留痕；detail 为空对象，禁止写入路径、转写或异常原文。"""
    db.add(
        AuditLog(
            actor_type="staff",
            actor_id=None,
            action="session.analyze",
            target_type="session",
            target_id=session_id,
            detail_json=json.dumps({}),
            request_id=current_request_id(),
            created_at=now,
        )
    )


@router.post("/sessions/{session_id}/analyze")
def analyze_session(
    session_id: str,
    _role: str = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    session = db.get(CaptureSession, session_id)
    if session is None:
        raise BizError(NOT_FOUND, "not_found")

    now = now_iso()
    if session.status == "created":
        _write_analyze_audit(db, session.id, now)
        db.commit()
        raise BizError(SESSION_NOT_CAPTURED, "session_not_captured")
    if session.status == "failed":
        _write_analyze_audit(db, session.id, now)
        db.commit()
        raise BizError(CAPTURE_FAILED, "capture_failed")

    degraded = degraded_flags(session.capture_status, session.analysis_status)
    if session.analysis_status == "failed":
        _write_analyze_audit(db, session.id, now)
        db.commit()
        return envelope(
            code=ANALYSIS_FAILED,
            message="analysis_failed",
            data=_session_payload(session),
            degraded=degraded,
        )

    reused = session.analysis_status in ("done", "degraded") and bool(
        session.analysis_json
    )
    if not reused:
        run = run_analysis_for_session(session)
        if run.analysis_status == "failed":
            persist_analysis(db, session, run, now)
            _write_analyze_audit(db, session.id, now)
            db.commit()
            return envelope(
                code=ANALYSIS_FAILED,
                message="analysis_failed",
                data=_session_payload(session),
                degraded=degraded_flags(
                    session.capture_status, session.analysis_status
                ),
            )
        persist_analysis(db, session, run, now)

    subject = db.get(Subject, session.subject_id)
    if subject is None:
        raise BizError(NOT_FOUND, "not_found")

    window_start, window_end = window_bounds(session.captured_at, 7)
    review, ticket, review_created = compute_and_persist_review(
        db, subject, session, window_start, window_end, 7, now
    )
    _write_analyze_audit(db, session.id, now)
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise

    data = {
        "session_id": session.id,
        "analysis_status": session.analysis_status,
        "review_id": review.id,
        "review_created": review_created,
        "ticket_id": ticket.id if ticket is not None else None,
    }
    return envelope(
        data=data,
        degraded=degraded_flags(session.capture_status, session.analysis_status),
    )
