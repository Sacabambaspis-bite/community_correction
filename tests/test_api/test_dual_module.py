"""刷脸签到 / 思想汇报双模块 API 与逾期任务测试。"""

from __future__ import annotations

import json
import threading
import time
import uuid
from datetime import datetime, timedelta

import pytest
from sqlalchemy import select

import app.api.deps as deps_module
import app.api.routers.sessions as sessions_router
from app.api import integration
from app.db.models import AuditLog, CaptureSession, ReviewTicket, Subject

_SUBJECT_ID = "3b1e7c90-2f4a-4d51-8c6b-7d9e0f1a2b3c"


def _iso(value: datetime) -> str:
    return value.isoformat(timespec="seconds")


def _add_subject(
    db_factory,
    *,
    subject_id: str = _SUBJECT_ID,
    created_at: datetime | None = None,
    checkin_interval_days: int = 1,
    report_interval_days: int = 3,
) -> None:
    now = datetime.now().astimezone()
    created = created_at or now
    with db_factory() as db:
        db.add(
            Subject(
                id=subject_id,
                code=f"S{subject_id[:8]}",
                name="测试对象",
                status="active",
                checkin_interval_days=checkin_interval_days,
                report_interval_days=report_interval_days,
                created_at=_iso(created),
                updated_at=_iso(now),
            )
        )
        db.commit()


def _grant_consent(db_factory, subject_id: str = _SUBJECT_ID) -> None:
    at = _iso(datetime.now().astimezone())
    consent = {
        "schema_version": "consent@1.0",
        "general": {"granted": True, "at": at},
        "face": {"granted": True, "at": at},
        "audio": {"granted": True, "at": at},
        "revoked_at": None,
        "retention_days": 180,
    }
    with db_factory() as db:
        subject = db.get(Subject, subject_id)
        subject.consent_json = json.dumps(consent)
        db.commit()


def _add_session(
    db_factory,
    session_id: str,
    *,
    subject_id: str = _SUBJECT_ID,
    kind: str = "report",
    status: str = "captured",
    capture_status: str | None = "ok",
    captured_at: datetime | None = None,
    face_path: str | None = None,
    audio_path: str | None = None,
) -> None:
    now = datetime.now().astimezone()
    with db_factory() as db:
        db.add(
            CaptureSession(
                id=session_id,
                subject_id=subject_id,
                kind=kind,
                status=status,
                capture_status=capture_status,
                captured_at=_iso(captured_at) if captured_at else None,
                face_path=face_path,
                audio_path=audio_path,
                analysis_status="pending",
                codes="[]",
                created_at=_iso(now),
                updated_at=_iso(now),
            )
        )
        db.commit()


def _write_face(tmp_path, session_id: str) -> str:
    directory = tmp_path / "subjects" / _SUBJECT_ID / "sessions" / session_id
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "face.jpg").write_bytes(b"placeholder-face")
    (directory / "meta.json").write_text(
        json.dumps({"audio": {"duration_sec": 0.0, "speech_ratio": 0.0}}),
        encoding="utf-8",
    )
    return f"subjects/{_SUBJECT_ID}/sessions/{session_id}/face.jpg"


def test_checkin_fake_capture_end_to_end(
    client, db_factory, user_headers, admin_headers, monkeypatch
):
    monkeypatch.setattr(deps_module, "get_session_factory", lambda: db_factory)
    _add_subject(db_factory)
    _grant_consent(db_factory)

    created = client.post(
        "/api/sessions",
        json={"subject_id": _SUBJECT_ID, "kind": "checkin"},
        headers=user_headers,
    ).json()
    assert created["code"] == 0
    assert created["data"]["status"] == "created"
    assert created["data"]["kind"] == "checkin"
    session_id = created["data"]["session_id"]

    detail = client.get(
        f"/api/sessions/{session_id}",
        params={"subject_id": _SUBJECT_ID},
        headers=user_headers,
    ).json()
    assert detail["code"] == 0
    assert detail["data"]["kind"] == "checkin"
    assert detail["data"]["status"] == "captured"
    assert detail["data"]["capture_status"] == "ok"
    assert detail["data"]["coverage"] == "face_only"
    assert detail["data"]["face_available"] is True
    assert detail["data"]["audio_available"] is False

    admin_listing = client.get(
        "/api/admin/sessions",
        params={"subject_id": _SUBJECT_ID},
        headers=admin_headers,
    ).json()
    assert admin_listing["code"] == 0
    assert admin_listing["data"]["items"][0]["kind"] == "checkin"

    with db_factory() as db:
        session = db.get(CaptureSession, session_id)
        assert session.face_path
        assert session.audio_path is None
        assert session.duration_sec is None


def test_report_capture_defaults_kind_and_keeps_audio(
    client, db_factory, user_headers, monkeypatch
):
    monkeypatch.setattr(deps_module, "get_session_factory", lambda: db_factory)
    _add_subject(db_factory)
    _grant_consent(db_factory)

    created = client.post(
        "/api/sessions", json={"subject_id": _SUBJECT_ID, "duration_sec": 10}, headers=user_headers
    ).json()
    session_id = created["data"]["session_id"]
    assert created["data"]["kind"] == "report"

    detail = client.get(
        f"/api/sessions/{session_id}",
        params={"subject_id": _SUBJECT_ID},
        headers=user_headers,
    ).json()
    assert detail["data"]["kind"] == "report"
    assert detail["data"]["coverage"] == "both"
    assert detail["data"]["audio_available"] is True


def test_checkin_analyze_done_without_audio_recapture_override(
    client, db_factory, admin_headers, tmp_path, monkeypatch
):
    monkeypatch.setattr(integration, "STORAGE_ROOT", str(tmp_path))
    monkeypatch.setenv("MOCK_SCENARIO", "normal")
    _add_subject(db_factory)
    session_id = str(uuid.uuid4())
    face_path = _write_face(tmp_path, session_id)
    _add_session(
        db_factory,
        session_id,
        kind="checkin",
        captured_at=datetime.now().astimezone(),
        face_path=face_path,
    )

    body = client.post(
        f"/api/sessions/{session_id}/analyze", headers=admin_headers
    ).json()
    assert body["code"] == 0, body
    assert body["data"]["analysis_status"] == "done"
    assert body["degraded"] == []

    with db_factory() as db:
        session = db.get(CaptureSession, session_id)
        analysis = json.loads(session.analysis_json)
        assert analysis["needs_review"] is False
        assert analysis["degraded"] is False
        assert analysis["consistency"] == "medium"
        assert analysis["channels"]["asr"]["status"] == "skipped"
        tickets = db.scalars(select(ReviewTicket)).all()
        assert not any(
            ticket.priority == "P0" and ticket.suggested_method == "recapture"
            for ticket in tickets
        )


def test_user_tasks_normal_overdue_and_never_completed(
    client, db_factory, user_headers
):
    now = datetime.now().astimezone()
    recent = now - timedelta(hours=1)
    _add_subject(db_factory, created_at=now - timedelta(days=10))
    _add_session(db_factory, str(uuid.uuid4()), kind="checkin", captured_at=recent)
    _add_session(db_factory, str(uuid.uuid4()), kind="report", captured_at=recent)

    normal = client.get(
        "/api/user/tasks",
        params={"subject_id": _SUBJECT_ID},
        headers=user_headers,
    ).json()
    assert normal["code"] == 0
    assert set(normal["data"]) == {"checkin", "report"}
    for kind in ("checkin", "report"):
        assert normal["data"][kind] == {
            "interval_days": 1 if kind == "checkin" else 3,
            "last_completed_at": _iso(recent),
            "overdue": False,
        }
        assert "final_color" not in normal["data"][kind]
        assert "risk_level" not in normal["data"][kind]

    overdue_id = "11111111-1111-4111-8111-111111111111"
    _add_subject(db_factory, subject_id=overdue_id, created_at=now - timedelta(days=10))
    old_checkin = now - timedelta(days=3)
    recent_report = now - timedelta(days=1)
    _add_session(
        db_factory,
        str(uuid.uuid4()),
        subject_id=overdue_id,
        kind="checkin",
        captured_at=old_checkin,
    )
    _add_session(
        db_factory,
        str(uuid.uuid4()),
        subject_id=overdue_id,
        kind="report",
        captured_at=recent_report,
    )
    overdue = client.get(
        "/api/user/tasks", params={"subject_id": overdue_id}, headers=user_headers
    ).json()["data"]
    assert overdue["checkin"]["last_completed_at"] == _iso(old_checkin)
    assert overdue["checkin"]["overdue"] is True
    assert overdue["report"]["last_completed_at"] == _iso(recent_report)
    assert overdue["report"]["overdue"] is False

    never_id = "22222222-2222-4222-8222-222222222222"
    _add_subject(db_factory, subject_id=never_id, created_at=now - timedelta(days=4))
    never = client.get(
        "/api/user/tasks", params={"subject_id": never_id}, headers=user_headers
    ).json()["data"]
    for kind in ("checkin", "report"):
        assert never[kind]["last_completed_at"] is None
        assert never[kind]["overdue"] is True


def test_user_tasks_rejects_admin_role(client, db_factory, admin_headers):
    _add_subject(db_factory)
    body = client.get(
        "/api/user/tasks",
        params={"subject_id": _SUBJECT_ID},
        headers=admin_headers,
    ).json()
    assert body["code"] == 1003


def test_frequency_update_and_audit(client, db_factory, admin_headers):
    _add_subject(db_factory)
    body = client.patch(
        f"/api/admin/subjects/{_SUBJECT_ID}/frequency",
        json={"checkin_interval_days": 2, "report_interval_days": 5},
        headers=admin_headers,
    ).json()
    assert body["code"] == 0, body
    assert body["data"] == {
        "subject_id": _SUBJECT_ID,
        "checkin_interval_days": 2,
        "report_interval_days": 5,
    }

    listing = client.get("/api/admin/subjects", headers=admin_headers).json()
    list_item = listing["data"]["items"][0]
    assert list_item["checkin_interval_days"] == 2
    assert list_item["report_interval_days"] == 5
    subject_detail = client.get(
        f"/api/admin/subjects/{_SUBJECT_ID}", headers=admin_headers
    ).json()
    assert subject_detail["data"]["checkin_interval_days"] == 2
    assert subject_detail["data"]["report_interval_days"] == 5

    with db_factory() as db:
        subject = db.get(Subject, _SUBJECT_ID)
        assert subject.checkin_interval_days == 2
        assert subject.report_interval_days == 5
        log = db.scalars(
            select(AuditLog).where(AuditLog.action == "frequency.update")
        ).one()
        assert log.actor_type == "staff"
        assert log.target_type == "subject"
        assert log.target_id == _SUBJECT_ID
        assert json.loads(log.detail_json) == {
            "checkin_interval_days": 2,
            "report_interval_days": 5,
        }
        assert log.request_id


@pytest.mark.parametrize(
    "payload",
    [
        {"checkin_interval_days": 0},
        {"report_interval_days": -1},
        {},
    ],
)
def test_frequency_update_validation(
    client, db_factory, admin_headers, payload
):
    _add_subject(db_factory)
    body = client.patch(
        f"/api/admin/subjects/{_SUBJECT_ID}/frequency",
        json=payload,
        headers=admin_headers,
    ).json()
    assert body["code"] == 1001
    with db_factory() as db:
        assert db.scalars(select(AuditLog)).all() == []


def test_lazy_overdue_scan_is_idempotent_and_reopens_after_close(
    client, db_factory, admin_headers
):
    now = datetime.now().astimezone()
    _add_subject(db_factory, created_at=now - timedelta(days=8))
    session_id = str(uuid.uuid4())
    _add_session(
        db_factory,
        session_id,
        kind="report",
        captured_at=now - timedelta(days=5),
    )

    listing = client.get("/api/admin/subjects", headers=admin_headers).json()
    assert listing["code"] == 0
    assert listing["data"]["items"][0]["overdue"] == {
        "checkin": True,
        "report": True,
    }
    with db_factory() as db:
        tickets = db.scalars(select(ReviewTicket)).all()
        assert len(tickets) == 2
        assert {ticket.review_id for ticket in tickets} == {None}
        for ticket in tickets:
            assert ticket.status == "pending"
            assert ticket.priority == "P0"
            assert ticket.suggested_method == "talk_to_staff"
            detail = json.loads(ticket.detail_json)
            assert detail["overdue_kind"] in {"checkin", "report"}
            assert detail["overdue_days"] >= 1

    detail_response = client.get(
        f"/api/admin/subjects/{_SUBJECT_ID}", headers=admin_headers
    ).json()
    assert detail_response["data"]["overdue"] == {
        "checkin": True,
        "report": True,
    }
    dashboard = client.get(
        "/api/admin/dashboard",
        params={"subject_id": _SUBJECT_ID},
        headers=admin_headers,
    ).json()
    assert dashboard["code"] == 0
    assert dashboard["data"]["overdue"] == {"checkin": True, "report": True}

    tickets_response = client.get(
        "/api/admin/tickets", headers=admin_headers
    ).json()
    assert tickets_response["code"] == 0
    assert tickets_response["data"]["total"] == 2
    ticket_items = tickets_response["data"]["items"]
    assert all(item["final_color"] is None for item in ticket_items)
    assert {
        item["detail_json"]["overdue_kind"] for item in ticket_items
    } == {"checkin", "report"}
    assert all(item["detail_json"]["overdue_days"] >= 1 for item in ticket_items)
    listed_checkin = next(
        item
        for item in ticket_items
        if item["detail_json"]["overdue_kind"] == "checkin"
    )
    with db_factory() as db:
        assert db.scalars(select(ReviewTicket)).all()
        assert len(db.scalars(select(ReviewTicket)).all()) == 2
        session = db.get(CaptureSession, session_id)
        assert session.status == "captured"
        assert session.analysis_status == "pending"

    with db_factory() as db:
        checkin_ticket = db.scalars(select(ReviewTicket)).all()
        checkin_ticket = next(
            ticket
            for ticket in checkin_ticket
            if json.loads(ticket.detail_json)["overdue_kind"] == "checkin"
        )
        checkin_ticket_id = checkin_ticket.id
    ticket_detail = client.get(
        f"/api/admin/tickets/{checkin_ticket_id}", headers=admin_headers
    ).json()
    assert ticket_detail["code"] == 0
    assert ticket_detail["data"]["detail_json"] == listed_checkin["detail_json"]

    closed = client.post(
        f"/api/admin/tickets/{checkin_ticket_id}/transition",
        json={"action": "close", "note": "已完成人工联系"},
        headers=admin_headers,
    ).json()
    assert closed["code"] == 0

    rescanned = client.get(
        f"/api/admin/subjects/{_SUBJECT_ID}", headers=admin_headers
    ).json()
    assert rescanned["code"] == 0
    with db_factory() as db:
        tickets = db.scalars(select(ReviewTicket)).all()
        assert len(tickets) == 3
        pending_kinds = [
            json.loads(ticket.detail_json)["overdue_kind"]
            for ticket in tickets
            if ticket.status == "pending"
        ]
        assert sorted(pending_kinds) == ["checkin", "report"]


def _wait_for_terminal_session(client, session_id: str, user_headers) -> dict:
    deadline = time.monotonic() + 3.0
    while time.monotonic() < deadline:
        payload = client.get(
            f"/api/sessions/{session_id}",
            params={"subject_id": _SUBJECT_ID},
            headers=user_headers,
        ).json()
        if payload["data"]["status"] != "created":
            return payload
        time.sleep(0.02)
    pytest.fail(f"session {session_id} did not reach a terminal capture state")


@pytest.mark.parametrize(
    "duration_payload",
    [{}, {"duration_sec": None}],
    ids=["omitted", "null"],
)
def test_manual_report_stop_capture_and_analyze(
    client,
    db_factory,
    user_headers,
    admin_headers,
    tmp_path,
    monkeypatch,
    duration_payload,
):
    monkeypatch.setattr(deps_module, "get_session_factory", lambda: db_factory)
    monkeypatch.setattr(sessions_router, "STORAGE_ROOT", str(tmp_path))
    monkeypatch.setattr(integration, "STORAGE_ROOT", str(tmp_path))
    monkeypatch.setenv("MOCK_SCENARIO", "normal")
    _add_subject(db_factory)
    _grant_consent(db_factory)

    created = client.post(
        "/api/sessions",
        json={
            "subject_id": _SUBJECT_ID,
            "kind": "report",
            **duration_payload,
        },
        headers=user_headers,
    ).json()
    assert created["code"] == 0
    assert created["data"]["status"] == "created"
    session_id = created["data"]["session_id"]

    # 假采集先初始化人脸依赖，再开始录音计时；等待 face.jpg 确保 stop
    # 发生在计时开始之后，同时验证等待期间不会自动完成。
    face_file = (
        tmp_path
        / "subjects"
        / _SUBJECT_ID
        / "sessions"
        / session_id
        / "face.jpg"
    )
    recording_deadline = time.monotonic() + 3.0
    while not face_file.is_file() and time.monotonic() < recording_deadline:
        time.sleep(0.01)
    assert face_file.is_file()
    time.sleep(0.15)
    recording = client.get(
        f"/api/sessions/{session_id}",
        params={"subject_id": _SUBJECT_ID},
        headers=user_headers,
    ).json()
    assert recording["code"] == 0
    assert recording["data"]["status"] == "created"
    assert recording["data"]["audio_available"] is False
    assert recording["data"]["duration_sec"] is None

    stopped = client.post(
        f"/api/sessions/{session_id}/stop",
        params={"subject_id": _SUBJECT_ID},
        headers=user_headers,
    ).json()
    assert stopped["code"] == 0
    assert stopped["data"] == {"session_id": session_id}

    captured = _wait_for_terminal_session(client, session_id, user_headers)
    assert captured["code"] == 0, captured
    assert captured["data"]["status"] == "captured"
    assert captured["data"]["capture_status"] == "ok"
    assert captured["data"]["audio_available"] is True
    assert captured["data"]["duration_sec"] >= 0.1

    with db_factory() as db:
        session = db.get(CaptureSession, session_id)
        assert session.audio_path
        assert session.duration_sec == pytest.approx(
            captured["data"]["duration_sec"]
        )
        audio_path = session.audio_path
    assert (tmp_path / audio_path).is_file()

    cleanup_deadline = time.monotonic() + 1.0
    while (
        sessions_router._get_manual_stop_event(session_id) is not None
        and time.monotonic() < cleanup_deadline
    ):
        time.sleep(0.01)
    assert sessions_router._get_manual_stop_event(session_id) is None

    analyzed = client.post(
        f"/api/sessions/{session_id}/analyze", headers=admin_headers
    ).json()
    assert analyzed["code"] == 0, analyzed
    assert analyzed["data"]["analysis_status"] == "done"


def test_manual_stop_is_idempotent_and_does_not_write_session(
    client, db_factory, user_headers, tmp_path, monkeypatch
):
    monkeypatch.setattr(deps_module, "get_session_factory", lambda: db_factory)
    monkeypatch.setattr(sessions_router, "STORAGE_ROOT", str(tmp_path))
    _add_subject(db_factory)
    _grant_consent(db_factory)

    original_capture_result = sessions_router._capture_result
    capture_started = threading.Event()
    release_capture = threading.Event()

    def paused_capture(**kwargs):
        capture_started.set()
        if not release_capture.wait(timeout=2.0):
            raise RuntimeError("test capture release timeout")
        return original_capture_result(**kwargs)

    monkeypatch.setattr(sessions_router, "_capture_result", paused_capture)
    created = client.post(
        "/api/sessions",
        json={"subject_id": _SUBJECT_ID, "kind": "report"},
        headers=user_headers,
    ).json()
    session_id = created["data"]["session_id"]
    assert capture_started.wait(timeout=1.0)
    with db_factory() as db:
        original_updated_at = db.get(CaptureSession, session_id).updated_at

    try:
        first = client.post(
            f"/api/sessions/{session_id}/stop",
            params={"subject_id": _SUBJECT_ID},
            headers=user_headers,
        ).json()
        second = client.post(
            f"/api/sessions/{session_id}/stop",
            params={"subject_id": _SUBJECT_ID},
            headers=user_headers,
        ).json()
        with db_factory() as db:
            session = db.get(CaptureSession, session_id)
            assert session.status == "created"
            assert session.updated_at == original_updated_at
    finally:
        release_capture.set()

    terminal = _wait_for_terminal_session(client, session_id, user_headers)
    assert terminal["data"]["status"] == "captured"
    assert first["code"] == 0
    assert first["data"] == {"session_id": session_id}
    assert second["code"] == 0
    assert second["data"] == {"session_id": session_id}


@pytest.mark.parametrize(
    ("status", "capture_status"),
    [("captured", "ok"), ("failed", "error")],
)
def test_stop_rejects_terminal_sessions(
    client, db_factory, user_headers, status, capture_status
):
    _add_subject(db_factory)
    session_id = str(uuid.uuid4())
    _add_session(
        db_factory,
        session_id,
        status=status,
        capture_status=capture_status,
    )

    body = client.post(
        f"/api/sessions/{session_id}/stop",
        params={"subject_id": _SUBJECT_ID},
        headers=user_headers,
    ).json()
    assert body["code"] == 1005
    assert body["data"] is None


@pytest.mark.parametrize("kind", ["report", "checkin"])
def test_stop_rejects_timed_created_and_checkin_sessions(
    client, db_factory, user_headers, kind
):
    _add_subject(db_factory)
    session_id = str(uuid.uuid4())
    _add_session(
        db_factory,
        session_id,
        kind=kind,
        status="created",
        capture_status=None,
    )

    body = client.post(
        f"/api/sessions/{session_id}/stop",
        params={"subject_id": _SUBJECT_ID},
        headers=user_headers,
    ).json()
    assert body["code"] == 1005


def test_stop_enforces_user_role_ownership_and_not_found(
    client, db_factory, user_headers, admin_headers
):
    _add_subject(db_factory)
    session_id = str(uuid.uuid4())
    _add_session(
        db_factory,
        session_id,
        status="created",
        capture_status=None,
    )

    forbidden = client.post(
        f"/api/sessions/{session_id}/stop",
        params={"subject_id": str(uuid.uuid4())},
        headers=user_headers,
    ).json()
    assert forbidden["code"] == 1003

    admin = client.post(
        f"/api/sessions/{session_id}/stop",
        params={"subject_id": _SUBJECT_ID},
        headers=admin_headers,
    ).json()
    assert admin["code"] == 1003

    missing = client.post(
        f"/api/sessions/{uuid.uuid4()}/stop",
        params={"subject_id": _SUBJECT_ID},
        headers=user_headers,
    ).json()
    assert missing["code"] == 1004
