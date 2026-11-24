"""analyze 正式接入、复盘生成、工单流转与看板测试（api@1.5 §7.4/§7.9-§7.14）。"""

from __future__ import annotations

import json
import uuid

from sqlalchemy import select

from app.api import integration
from app.db.models import AuditLog, CaptureSession, Review, ReviewTicket, Subject

_SUBJECT_ID = "3b1e7c90-2f4a-4d51-8c6b-7d9e0f1a2b3c"
_CREATED_AT = "2026-11-23T09:00:00+08:00"
_CAPTURED_AT = "2026-11-23T10:00:00+08:00"


def _add_subject(db_factory, subject_id: str = _SUBJECT_ID, name: str = "张某某") -> None:
    with db_factory() as db:
        db.add(
            Subject(
                id=subject_id,
                code=f"S{subject_id[:4]}",
                name=name,
                status="active",
                consent_json=None,
                baseline_json=None,
                created_at=_CREATED_AT,
                updated_at=_CAPTURED_AT,
            )
        )
        db.commit()


def _add_session(
    db_factory,
    session_id: str,
    *,
    subject_id: str = _SUBJECT_ID,
    status: str = "captured",
    capture_status: str | None = "ok",
    face_path: str | None = None,
    audio_path: str | None = None,
    analysis_status: str = "pending",
    analysis_json: str | None = None,
    captured_at: str | None = _CAPTURED_AT,
    duration_sec: float | None = 10.0,
) -> None:
    with db_factory() as db:
        db.add(
            CaptureSession(
                id=session_id,
                subject_id=subject_id,
                status=status,
                capture_status=capture_status,
                face_path=face_path,
                audio_path=audio_path,
                analysis_status=analysis_status,
                analysis_json=analysis_json,
                codes="[]",
                captured_at=captured_at,
                duration_sec=duration_sec,
                created_at=_CREATED_AT,
                updated_at=_CAPTURED_AT,
            )
        )
        db.commit()


def _write_media(tmp_path, subject_id: str, session_id: str) -> tuple[str, str]:
    base = tmp_path / "subjects" / subject_id / "sessions" / session_id
    base.mkdir(parents=True, exist_ok=True)
    (base / "face.jpg").write_bytes(b"placeholder-face")
    (base / "audio.wav").write_bytes(b"placeholder-audio")
    (base / "meta.json").write_text(
        json.dumps({"audio": {"duration_sec": 10.0, "speech_ratio": 0.5}}),
        encoding="utf-8",
    )
    prefix = f"subjects/{subject_id}/sessions/{session_id}"
    return f"{prefix}/face.jpg", f"{prefix}/audio.wav"


def _minimal_analysis(session_id: str) -> str:
    return json.dumps(
        {
            "schema_version": "1.0",
            "session_id": session_id,
            "subject_id": _SUBJECT_ID,
            "overall": {
                "text_valence": 0.0,
                "text_signal": 12.0,
                "risk_level": "none",
                "summary_signal": "中性占位",
            },
            "channels": {
                "asr": {"status": "skipped", "output": None},
                "emotion": {"status": "ok", "output": None},
                "face": {"status": "ok", "output": None},
                "psych": {
                    "status": "ok",
                    "output": {
                        "signal_strength": 12.0,
                        "intent_flag": "none",
                        "keywords": [],
                        "rationale_signal": "占位",
                    },
                },
            },
            "consistency": "high",
            "degraded": False,
        },
        ensure_ascii=False,
    )


def test_analyze_captured_ok_persists_and_creates_review(
    client, db_factory, admin_headers, tmp_path, monkeypatch
):
    monkeypatch.setattr(integration, "STORAGE_ROOT", str(tmp_path))
    monkeypatch.setenv("MOCK_SCENARIO", "normal")
    _add_subject(db_factory)
    session_id = str(uuid.uuid4())
    face_path, audio_path = _write_media(tmp_path, _SUBJECT_ID, session_id)
    _add_session(
        db_factory, session_id, face_path=face_path, audio_path=audio_path
    )

    body = client.post(
        f"/api/sessions/{session_id}/analyze", headers=admin_headers
    ).json()

    assert body["code"] == 0, body
    data = body["data"]
    assert data["session_id"] == session_id
    assert data["analysis_status"] == "done"
    assert data["review_id"]
    assert data["ticket_id"]
    assert data["review_created"] is True
    assert body["degraded"] == []

    with db_factory() as db:
        session = db.get(CaptureSession, session_id)
        assert session.analysis_status == "done"
        analysis = json.loads(session.analysis_json)
        assert analysis["overall"]["risk_level"] == "none"
        assert session.transcript_path.endswith("transcript.txt")
        assert len(db.scalars(select(Review)).all()) == 1
        assert len(db.scalars(select(ReviewTicket)).all()) == 1
        logs = db.scalars(
            select(AuditLog).where(AuditLog.action == "session.analyze")
        ).all()
        assert len(logs) == 1
        assert logs[0].target_type == "session"
        assert logs[0].target_id == session_id
        assert json.loads(logs[0].detail_json) == {}


def test_analyze_partial_capture_opens_p0_recapture_ticket(
    client, db_factory, admin_headers, tmp_path, monkeypatch
):
    monkeypatch.setattr(integration, "STORAGE_ROOT", str(tmp_path))
    monkeypatch.setenv("MOCK_SCENARIO", "normal")
    _add_subject(db_factory)
    session_id = str(uuid.uuid4())
    face_path, audio_path = _write_media(tmp_path, _SUBJECT_ID, session_id)
    _add_session(
        db_factory,
        session_id,
        capture_status="partial",
        face_path=face_path,
        audio_path=audio_path,
    )

    body = client.post(
        f"/api/sessions/{session_id}/analyze", headers=admin_headers
    ).json()

    assert body["code"] == 0, body
    assert "capture" in body["degraded"]
    with db_factory() as db:
        ticket = db.scalars(select(ReviewTicket)).one()
        assert ticket.priority == "P0"
        assert ticket.suggested_method == "recapture"


def test_analyze_failure_returns_2003_and_keeps_capture_status(
    client, db_factory, admin_headers, tmp_path, monkeypatch
):
    monkeypatch.setattr(integration, "STORAGE_ROOT", str(tmp_path))
    _add_subject(db_factory)
    session_id = str(uuid.uuid4())
    prefix = f"subjects/{_SUBJECT_ID}/sessions/{session_id}"
    # 路径存在但文件缺失 -> run_analysis 返回 failed。
    _add_session(
        db_factory,
        session_id,
        face_path=f"{prefix}/face.jpg",
        audio_path=f"{prefix}/audio.wav",
    )

    body = client.post(
        f"/api/sessions/{session_id}/analyze", headers=admin_headers
    ).json()

    assert body["code"] == 2003
    assert body["message"] == "analysis_failed"
    assert body["degraded"] == []
    assert body["data"]["analysis_status"] == "failed"
    assert body["data"]["status"] == "captured"

    with db_factory() as db:
        session = db.get(CaptureSession, session_id)
        assert session.status == "captured"
        assert session.analysis_status == "failed"
        assert session.analysis_json is None
        assert len(db.scalars(select(Review)).all()) == 0
        assert len(db.scalars(select(ReviewTicket)).all()) == 0


def test_analyze_is_idempotent(
    client, db_factory, admin_headers, tmp_path, monkeypatch
):
    monkeypatch.setattr(integration, "STORAGE_ROOT", str(tmp_path))
    monkeypatch.setenv("MOCK_SCENARIO", "normal")
    _add_subject(db_factory)
    session_id = str(uuid.uuid4())
    face_path, audio_path = _write_media(tmp_path, _SUBJECT_ID, session_id)
    _add_session(
        db_factory, session_id, face_path=face_path, audio_path=audio_path
    )

    first = client.post(
        f"/api/sessions/{session_id}/analyze", headers=admin_headers
    ).json()["data"]
    second = client.post(
        f"/api/sessions/{session_id}/analyze", headers=admin_headers
    ).json()["data"]

    assert second["review_id"] == first["review_id"]
    assert second["ticket_id"] == first["ticket_id"]
    assert second["review_created"] is False

    with db_factory() as db:
        assert len(db.scalars(select(Review)).all()) == 1
        assert len(db.scalars(select(ReviewTicket)).all()) == 1


def test_admin_review_rejects_empty_window_without_persisting(
    client, db_factory, admin_headers
):
    _add_subject(db_factory)

    body = client.post(
        "/api/admin/reviews",
        json={"subject_id": _SUBJECT_ID},
        headers=admin_headers,
    ).json()

    assert body["code"] == 1005
    assert body["message"] == "no_session_in_window"
    with db_factory() as db:
        assert db.scalars(select(Review)).all() == []


def test_admin_review_invalid_window_end(client, db_factory, admin_headers):
    _add_subject(db_factory)

    body = client.post(
        "/api/admin/reviews",
        json={"subject_id": _SUBJECT_ID, "window_end": "2026/11/23"},
        headers=admin_headers,
    ).json()

    assert body["code"] == 1001


def test_admin_review_creates_and_is_idempotent(
    client, db_factory, admin_headers
):
    _add_subject(db_factory)
    session_id = str(uuid.uuid4())
    _add_session(
        db_factory,
        session_id,
        analysis_status="done",
        analysis_json=_minimal_analysis(session_id),
    )

    payload = {
        "subject_id": _SUBJECT_ID,
        "window_end": "2026-11-23",
        "window_days": 7,
    }
    first = client.post(
        "/api/admin/reviews", json=payload, headers=admin_headers
    ).json()
    assert first["code"] == 0, first
    data = first["data"]
    assert data["window_start"] == "2026-11-17"
    assert data["window_end"] == "2026-11-23"
    assert data["manual_review"] is False
    assert isinstance(data["evidence"], list)

    detail = client.get(
        f"/api/admin/reviews/{data['review_id']}", headers=admin_headers
    ).json()
    assert detail["code"] == 0
    assert detail["data"]["review_id"] == data["review_id"]

    second = client.post(
        "/api/admin/reviews", json=payload, headers=admin_headers
    ).json()
    assert second["code"] == 0
    assert second["data"]["review_id"] == data["review_id"]

    with db_factory() as db:
        assert len(db.scalars(select(Review)).all()) == 1
        assert len(db.scalars(select(ReviewTicket)).all()) == 1
        logs = db.scalars(
            select(AuditLog).where(AuditLog.action == "review.create")
        ).all()
        assert logs and logs[0].target_type == "review"


def test_tickets_list_detail_transition_and_closed_guard(
    client, db_factory, admin_headers
):
    _add_subject(db_factory)
    session_id = str(uuid.uuid4())
    _add_session(
        db_factory,
        session_id,
        analysis_status="done",
        analysis_json=_minimal_analysis(session_id),
    )
    review = client.post(
        "/api/admin/reviews",
        json={"subject_id": _SUBJECT_ID, "window_end": "2026-11-23"},
        headers=admin_headers,
    ).json()["data"]

    listing = client.get("/api/admin/tickets", headers=admin_headers).json()
    assert listing["code"] == 0
    assert listing["data"]["total"] == 1
    item = listing["data"]["items"][0]
    assert item["subject_name"] == "张某某"
    assert item["final_color"] == review["final_color"]
    assert set(item) == {
        "ticket_id",
        "subject_id",
        "subject_name",
        "priority",
        "final_color",
        "triggered_rules",
        "opened_at",
        "due_at",
        "status",
    }

    invalid = client.get(
        "/api/admin/tickets?status=unknown", headers=admin_headers
    ).json()
    assert invalid["code"] == 1001
    invalid_priority = client.get(
        "/api/admin/tickets?priority=P9", headers=admin_headers
    ).json()
    assert invalid_priority["code"] == 1001

    ticket_id = item["ticket_id"]
    missing = client.post(
        f"/api/admin/tickets/{ticket_id}/transition",
        json={"action": "correct", "note": "缺色"},
        headers=admin_headers,
    ).json()
    assert missing["code"] == 1001

    transitioned = client.post(
        f"/api/admin/tickets/{ticket_id}/transition",
        json={
            "action": "correct",
            "conclusion_color": "green",
            "note": "面谈确认无需升级",
            "assignee": "E1024",
        },
        headers=admin_headers,
    ).json()
    assert transitioned["code"] == 0, transitioned
    outcome = transitioned["data"]
    assert outcome["status"] == "closed"
    assert outcome["previous_status"] == "pending"
    assert outcome["conclusion_color"] == "green"
    assert outcome["assignee"] == "E1024"
    assert outcome["closed_at"]

    detail = client.get(
        f"/api/admin/tickets/{ticket_id}", headers=admin_headers
    ).json()
    assert detail["code"] == 0
    assert detail["data"]["rules_fired"] == review["rules_fired"]
    assert detail["data"]["suggested_method"]
    assert [entry["action"] for entry in detail["data"]["history"]] == [
        "opened",
        "correct",
    ]
    assert detail["data"]["history"][1]["note"] == "面谈确认无需升级"

    with db_factory() as db:
        logs = db.scalars(
            select(AuditLog).where(
                AuditLog.action == "sensitive.view",
                AuditLog.target_type == "ticket",
                AuditLog.target_id == ticket_id,
            )
        ).all()
        assert len(logs) == 1
        assert json.loads(logs[0].detail_json) == {"field": "ticket"}

    again = client.post(
        f"/api/admin/tickets/{ticket_id}/transition",
        json={"action": "confirm"},
        headers=admin_headers,
    ).json()
    assert again["code"] == 1005
    assert again["message"] == "ticket_closed"


def test_dashboard_defaults_to_latest_captured_subject(
    client, db_factory, admin_headers
):
    _add_subject(db_factory)
    session_id = str(uuid.uuid4())
    _add_session(
        db_factory,
        session_id,
        analysis_status="done",
        analysis_json=_minimal_analysis(session_id),
    )
    client.post(
        "/api/admin/reviews",
        json={"subject_id": _SUBJECT_ID, "window_end": "2026-11-23"},
        headers=admin_headers,
    )

    body = client.get("/api/admin/dashboard", headers=admin_headers).json()
    assert body["code"] == 0, body
    data = body["data"]
    assert data["subject_id"] == _SUBJECT_ID
    assert set(data["color_distribution"]) == {
        "green",
        "blue",
        "yellow",
        "orange",
        "red",
    }
    assert sum(data["color_distribution"].values()) == 1
    assert data["pending_tickets"] == 1
    assert data["last_session_at"] == _CAPTURED_AT


def test_dashboard_without_any_data_returns_1004(client, admin_headers):
    body = client.get("/api/admin/dashboard", headers=admin_headers).json()
    assert body["code"] == 1004
