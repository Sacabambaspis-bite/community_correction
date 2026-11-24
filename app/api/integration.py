"""分析与分级服务层。

只读写数据库、调用 `app.analysis` / `app.grading` 的公开 API，不复制任何
阈值或颜色映射；路由层负责鉴权、错误码与事务提交。
"""

from __future__ import annotations

import json
import logging
from dataclasses import replace
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Optional
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.analysis.models import AnalysisInput, AnalysisRunResult
from app.analysis.paths import session_directory
from app.analysis.pipeline import run_analysis
from app.capture.config import STORAGE_ROOT
from app.db.models import CaptureSession, Review, ReviewTicket, Subject
from app.grading import build_ticket, compose, evaluate_period, evaluate_session

logger = logging.getLogger("app.api")

#: 需要按规则 8 覆写 `review_reason="capture_degraded"` 的采集状态。
CAPTURE_DEGRADED_STATUSES = frozenset({"partial", "no_face", "no_audio"})
#: 可进入复盘/趋势的可用分析状态。
USABLE_ANALYSIS_STATUSES = ("done", "degraded")
CONSISTENCY_VALUES = frozenset({"high", "medium", "low"})
DEFAULT_WINDOW_DAYS = 7


def now_iso() -> str:
    """当前时间（带时区、毫秒精度），grading 的 `now` 必须带时区。"""
    return datetime.now().astimezone().isoformat(timespec="milliseconds")


def _load_json(raw: Optional[str]) -> Any:
    if not raw:
        return None
    try:
        return json.loads(raw)
    except (TypeError, ValueError):
        return None


def _json_list(raw: Optional[str]) -> list:
    value = _load_json(raw)
    return value if isinstance(value, list) else []


def _as_number(value: Any) -> Optional[float]:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def _read_meta(storage_root: Path, subject_id: str, session_id: str) -> dict:
    """读取会话目录下 meta.json；缺失、非法或无权限一律回落空 dict。"""
    try:
        path = session_directory(storage_root, subject_id, session_id) / "meta.json"
        value = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return value if isinstance(value, dict) else {}


def run_analysis_for_session(
    session: CaptureSession, *, storage_root: Optional[Path | str] = None
) -> AnalysisRunResult:
    """按会话落库字段组装 `AnalysisInput` 并执行四路分析。"""
    root = Path(storage_root or STORAGE_ROOT)
    meta = _read_meta(root, session.subject_id, session.id)
    audio_meta = meta.get("audio")
    if not isinstance(audio_meta, dict):
        audio_meta = {}

    duration = _as_number(audio_meta.get("duration_sec"))
    if duration is None:
        duration = _as_number(session.duration_sec)
    if duration is None:
        duration = 0.0

    speech_ratio = _as_number(audio_meta.get("speech_ratio"))
    if speech_ratio is None:
        speech_ratio = 0.0

    analysis_input = AnalysisInput(
        session_id=session.id,
        subject_id=session.subject_id,
        capture_status=session.capture_status or "",
        coverage=session.coverage,
        storage_root=root,
        face_path=session.face_path,
        audio_path=session.audio_path,
        duration_sec=duration,
        speech_ratio=speech_ratio,
        session_status="captured",
    )
    return run_analysis(analysis_input)


def _transcript_path(result: dict) -> Optional[str]:
    channels = result.get("channels")
    if not isinstance(channels, dict):
        return None
    asr = channels.get("asr")
    if not isinstance(asr, dict) or asr.get("status") != "ok":
        return None
    output = asr.get("output")
    if not isinstance(output, dict):
        return None
    path = output.get("transcript_path")
    return path if isinstance(path, str) and path else None


def persist_analysis(
    db: Session, session: CaptureSession, run: AnalysisRunResult, now: str
) -> None:
    """写回分析结果；失败只改 `analysis_status`，不回写 `sessions.status`。"""
    session.updated_at = now
    if run.analysis_status in USABLE_ANALYSIS_STATUSES and run.result is not None:
        session.analysis_json = json.dumps(run.result, ensure_ascii=False)
        session.analysis_status = run.analysis_status
        session.transcript_path = _transcript_path(run.result)
    else:
        session.analysis_status = "failed"
        session.analysis_json = None
    db.flush()


def _date_of(value: Optional[str]) -> date:
    if isinstance(value, str) and value:
        try:
            return datetime.fromisoformat(value).date()
        except ValueError:
            pass
    return datetime.now().astimezone().date()


def _datetime_of(value: Optional[str]) -> datetime:
    if isinstance(value, str) and value:
        try:
            parsed = datetime.fromisoformat(value)
            if parsed.tzinfo is None:
                parsed = parsed.astimezone()
            return parsed
        except ValueError:
            pass
    return datetime.min.replace(tzinfo=datetime.now().astimezone().tzinfo)


def window_bounds(
    captured_at: Optional[str], days: int = DEFAULT_WINDOW_DAYS
) -> tuple[str, str]:
    """按捕获时间所在自然日计算含端点的窗口，返回 `YYYY-MM-DD`。"""
    end = _date_of(captured_at)
    start = end - timedelta(days=max(int(days), 1) - 1)
    return start.isoformat(), end.isoformat()


def load_usable_sessions(
    db: Session, subject_id: str, start: str, end: str
) -> list[CaptureSession]:
    """窗口内可用分析会话：captured + done/degraded + analysis_json 非空。"""
    start_date = date.fromisoformat(start)
    end_date = date.fromisoformat(end)
    stmt = select(CaptureSession).where(
        CaptureSession.subject_id == subject_id,
        CaptureSession.status == "captured",
        CaptureSession.analysis_status.in_(USABLE_ANALYSIS_STATUSES),
        CaptureSession.analysis_json.is_not(None),
    )
    sessions: list[CaptureSession] = []
    for session in db.scalars(stmt).all():
        if not (session.analysis_json or "").strip():
            continue
        if start_date <= _date_of(session.captured_at) <= end_date:
            sessions.append(session)
    sessions.sort(key=lambda item: (_datetime_of(item.captured_at), item.id))
    return sessions


def _baseline_of(subject: Subject) -> dict:
    value = _load_json(subject.baseline_json)
    return value if isinstance(value, dict) else {}


def _consistency_of(analysis: dict) -> str:
    value = analysis.get("consistency")
    return value if value in CONSISTENCY_VALUES else "medium"


def compute_and_persist_review(
    db: Session,
    subject: Subject,
    source_session: CaptureSession,
    window_start: str,
    window_end: str,
    window_days: int,
    now: str,
) -> tuple[Review, Optional[ReviewTicket], bool]:
    """计算并落库复盘与工单；按 `(subject_id, window_end)` 幂等。"""
    existing = db.scalars(
        select(Review).where(
            Review.subject_id == subject.id,
            Review.window_end == window_end,
        )
    ).first()
    if existing is not None:
        ticket = db.scalars(
            select(ReviewTicket).where(ReviewTicket.review_id == existing.id)
        ).first()
        return existing, ticket, False

    source_analysis = _load_json(source_session.analysis_json)
    if not isinstance(source_analysis, dict):
        source_analysis = {}

    analyses: list[dict] = []
    for session in load_usable_sessions(db, subject.id, window_start, window_end):
        analysis = _load_json(session.analysis_json)
        if isinstance(analysis, dict):
            analyses.append(analysis)
    if not analyses:
        analyses = [source_analysis]

    consistency = _consistency_of(source_analysis)
    degraded = bool(source_analysis.get("degraded"))

    session_grading = evaluate_session(source_analysis, now)
    period_grading = evaluate_period(
        analyses, _baseline_of(subject), (window_start, window_end), now
    )
    final = compose(session_grading, period_grading, consistency, degraded, now)

    # 规则 8：AnalysisResult 不含 capture_status，由调用方覆写建单原因。
    if source_session.capture_status in CAPTURE_DEGRADED_STATUSES:
        final = replace(final, review_reason="capture_degraded")

    review = Review(
        id=str(uuid4()),
        subject_id=subject.id,
        source_session_id=source_session.id,
        window_start=window_start,
        window_end=window_end,
        window_days=window_days,
        single_session_risk=session_grading.single_session_risk,
        trend_color=period_grading.trend_color,
        final_color=final.final_color,
        consistency=consistency,
        manual_review=int(final.manual_review),
        rules_fired=json.dumps(final.rules_fired),
        evidence_json=json.dumps(final.evidence, ensure_ascii=False),
        grading_version=final.grading_version,
        created_at=now,
    )

    ticket: Optional[ReviewTicket] = None
    should_open = (
        final.final_color != "green"
        or final.needs_review
        or final.review_reason == "capture_degraded"
    )
    if should_open:
        draft = build_ticket(final, review.id, subject.id, now)
        ticket = ReviewTicket(
            id=str(uuid4()),
            review_id=review.id,
            subject_id=subject.id,
            status=draft["status"],
            priority=draft["priority"],
            due_at=draft["due_at"],
            triggered_rules=json.dumps(draft["triggered_rules"]),
            evidence_json=json.dumps(draft["evidence_json"], ensure_ascii=False),
            suggested_method=draft["suggested_method"],
            opened_at=draft["opened_at"],
            assignee=None,
            conclusion_color=None,
            conclusion_note=None,
            closed_at=None,
        )

    try:
        db.add(review)
        if ticket is not None:
            db.add(ticket)
        db.flush()
    except Exception:
        db.rollback()
        raise

    return review, ticket, True


def serialize_review(review: Review) -> dict:
    """api.md §7.9 ReviewDetail。"""
    return {
        "review_id": review.id,
        "subject_id": review.subject_id,
        "window_start": review.window_start,
        "window_end": review.window_end,
        "window_days": review.window_days,
        "single_session_risk": review.single_session_risk,
        "trend_color": review.trend_color,
        "final_color": review.final_color,
        "consistency": review.consistency,
        "manual_review": bool(review.manual_review),
        "rules_fired": _json_list(review.rules_fired),
        "grading_version": review.grading_version,
        "evidence": _json_list(review.evidence_json),
        "created_at": review.created_at,
    }


def serialize_ticket_list_item(
    ticket: ReviewTicket, review: Optional[Review], subject: Optional[Subject]
) -> dict:
    """api.md §7.12 列表项。"""
    return {
        "ticket_id": ticket.id,
        "subject_id": ticket.subject_id,
        "subject_name": subject.name if subject is not None else None,
        "priority": ticket.priority,
        "final_color": review.final_color if review is not None else None,
        "triggered_rules": _json_list(ticket.triggered_rules),
        "opened_at": ticket.opened_at,
        "due_at": ticket.due_at,
        "status": ticket.status,
    }


def serialize_ticket_detail(
    ticket: ReviewTicket,
    review: Optional[Review],
    subject: Optional[Subject],
    history: list[dict],
) -> dict:
    """api.md §7.13 工单详情。"""
    data = serialize_ticket_list_item(ticket, review, subject)
    data.update(
        {
            "rules_fired": _json_list(review.rules_fired) if review else [],
            "suggested_method": ticket.suggested_method,
            "evidence": _json_list(ticket.evidence_json),
            "history": history,
        }
    )
    return data
