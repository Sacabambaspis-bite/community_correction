"""API 骨架契约测试（api@1.4）。"""

from __future__ import annotations

import logging
import uuid

from fastapi.testclient import TestClient
from sqlalchemy import select

import app.api.deps as deps_module
import app.api.routers.admin as admin_router
import app.api.routers.sessions as sessions_router
from app.api.main import app
from app.db.models import AuditLog, CaptureSession, Subject

_SUBJECT_ID = "3b1e7c90-2f4a-4d51-8c6b-7d9e0f1a2b3c"
_CREATED_AT = "2026-11-23T10:12:03+08:00"
_UPDATED_AT = "2026-11-23T10:12:36+08:00"


def _add_subject(db_factory, subject_id: str = _SUBJECT_ID) -> None:
    with db_factory() as db:
        db.add(
            Subject(
                id=subject_id,
                code="S001",
                name="张某某",
                status="active",
                consent_json=None,
                baseline_json=None,
                created_at=_CREATED_AT,
                updated_at=_UPDATED_AT,
            )
        )
        db.commit()


def _add_session(
    db_factory,
    session_id: str,
    *,
    status: str = "captured",
    capture_status: str | None = "ok",
    face_path: str | None = None,
    audio_path: str | None = None,
    analysis_status: str = "pending",
    analysis_json: str | None = None,
    codes: str = "[]",
    captured_at: str | None = _UPDATED_AT,
) -> None:
    with db_factory() as db:
        db.add(
            CaptureSession(
                id=session_id,
                subject_id=_SUBJECT_ID,
                status=status,
                capture_status=capture_status,
                face_path=face_path,
                audio_path=audio_path,
                analysis_status=analysis_status,
                analysis_json=analysis_json,
                codes=codes,
                captured_at=captured_at,
                created_at=_CREATED_AT,
                updated_at=_UPDATED_AT,
            )
        )
        db.commit()


def test_health_returns_db_true(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    body = response.json()
    assert body["code"] == 0
    assert body["data"] == {"db": True}
    assert body["degraded"] == []


def test_partial_session_marks_capture_degraded(client, db_factory, user_headers):
    _add_subject(db_factory)
    session_id = "8f3c1b2e-4a5d-4c6e-9f10-1a2b3c4d5e6f"
    _add_session(
        db_factory,
        session_id,
        capture_status="partial",
        face_path="subjects/s/sessions/x/face.jpg",
        audio_path=None,
        codes='["no_face"]',
    )

    response = client.get(f"/api/sessions/{session_id}", headers=user_headers)
    body = response.json()
    assert response.status_code == 200
    assert body["code"] == 0
    assert body["degraded"] == ["capture"]
    assert body["data"]["coverage"] == "face_only"
    assert body["data"]["face_available"] is True
    assert body["data"]["audio_available"] is False
    assert body["data"]["codes"] == ["no_face"]
    assert "face_path" not in body["data"]
    assert "audio_path" not in body["data"]

    with db_factory() as db:
        model = db.get(CaptureSession, session_id)
        assert model.coverage == "face_only"


def test_failed_session_returns_2001(client, db_factory, user_headers):
    _add_subject(db_factory)
    session_id = "0f9d6a1b-2c3d-4e5f-8a90-b1c2d3e4f5a6"
    _add_session(
        db_factory,
        session_id,
        status="failed",
        capture_status="error",
        analysis_status="failed",
        codes='["camera_unavailable"]',
        captured_at=None,
    )

    response = client.get(f"/api/sessions/{session_id}", headers=user_headers)
    body = response.json()
    assert response.status_code == 200
    assert body["code"] == 2001
    assert body["message"] == "capture_failed"
    assert body["data"]["status"] == "failed"
    assert body["data"]["coverage"] is None
    assert body["data"]["codes"] == ["camera_unavailable"]
    assert body["degraded"] == []


def test_analysis_failed_returns_2003(client, db_factory, user_headers):
    _add_subject(db_factory)
    session_id = "4b5c6d7e-8f90-4a1b-9c2d-3e4f5a6b7c8d"
    _add_session(
        db_factory,
        session_id,
        status="captured",
        capture_status="ok",
        analysis_status="failed",
        codes="[]",
    )

    response = client.get(f"/api/sessions/{session_id}", headers=user_headers)
    body = response.json()
    assert response.status_code == 200
    assert body["code"] == 2003
    assert body["message"] == "analysis_failed"
    assert body["data"]["status"] == "captured"
    assert body["data"]["analysis_status"] == "failed"
    assert body["degraded"] == []


def test_admin_subjects_requires_admin_token(client, user_headers):
    no_token = client.get("/api/admin/subjects")
    assert no_token.status_code == 200
    assert no_token.json()["code"] == 1002

    user_token = client.get("/api/admin/subjects", headers=user_headers)
    assert user_token.status_code == 200
    assert user_token.json()["code"] == 1003


def test_analyze_endpoint_state_mapping(client, db_factory, admin_headers):
    _add_subject(db_factory)
    created_id = "11111111-1111-4111-8111-111111111111"
    failed_id = "22222222-2222-4222-8222-222222222222"
    captured_id = "33333333-3333-4333-8333-333333333333"
    _add_session(
        db_factory,
        created_id,
        status="created",
        capture_status=None,
        captured_at=None,
    )
    _add_session(
        db_factory,
        failed_id,
        status="failed",
        capture_status="error",
        captured_at=None,
    )
    _add_session(db_factory, captured_id, capture_status="ok")

    created = client.post(f"/api/sessions/{created_id}/analyze", headers=admin_headers)
    assert created.json()["code"] == 4000
    assert created.json()["message"] == "session_not_captured"

    failed = client.post(f"/api/sessions/{failed_id}/analyze", headers=admin_headers)
    assert failed.json()["code"] == 2001
    assert failed.json()["message"] == "capture_failed"

    captured = client.post(
        f"/api/sessions/{captured_id}/analyze", headers=admin_headers
    )
    assert captured.json()["code"] == 5000
    assert captured.json()["message"] == "analysis_pipeline_not_ready"


def test_docs_available(client):
    assert client.get("/docs").status_code == 200


def test_request_id_in_envelope_and_header(client):
    ok = client.get("/api/health")
    ok_rid = ok.headers["X-Request-Id"]
    assert ok.json()["request_id"] == ok_rid
    assert str(uuid.UUID(ok_rid)) == ok_rid

    err = client.get("/api/admin/subjects")
    assert err.json()["code"] == 1002
    err_rid = err.headers["X-Request-Id"]
    assert err.json()["request_id"] == err_rid
    assert str(uuid.UUID(err_rid)) == err_rid
    assert ok_rid != err_rid


def test_face_view_writes_audit_with_request_id(
    client, db_factory, admin_headers, tmp_path, monkeypatch
):
    _add_subject(db_factory)
    session_id = "5a6b7c8d-9e0f-4a1b-b2c3-d4e5f6a7b8c9"
    rel_path = f"subjects/{_SUBJECT_ID}/sessions/{session_id}/face.jpg"
    face_file = tmp_path / rel_path
    face_file.parent.mkdir(parents=True, exist_ok=True)
    face_file.write_bytes(b"\xff\xd8\xff\xd9")
    _add_session(db_factory, session_id, capture_status="ok", face_path=rel_path)
    monkeypatch.setattr(admin_router, "STORAGE_ROOT", str(tmp_path))

    response = client.get(
        f"/api/admin/sessions/{session_id}/face", headers=admin_headers
    )
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/jpeg"
    rid = response.headers["X-Request-Id"]
    assert rid

    with db_factory() as db:
        logs = db.scalars(select(AuditLog)).all()
        assert len(logs) == 1
        log = logs[0]
        assert log.request_id == rid
        assert log.action == "sensitive.view"
        assert log.target_type == "session"
        assert log.target_id == session_id
        assert "face.jpg" not in (log.detail_json or "")
        assert "subjects/" not in (log.detail_json or "")


def test_unhandled_exception_returns_500_with_request_id(client):
    def boom():
        raise RuntimeError("boom")

    app.add_api_route("/__boom", boom, methods=["GET"])
    try:
        with TestClient(app, raise_server_exceptions=False) as boom_client:
            response = boom_client.get("/__boom")
    finally:
        app.router.routes[:] = [
            route
            for route in app.router.routes
            if getattr(route, "path", None) != "/__boom"
        ]

    assert response.status_code == 500
    body = response.json()
    assert body["code"] == 5000
    assert body["message"] == "internal_error"
    assert body["request_id"]
    assert str(uuid.UUID(body["request_id"])) == body["request_id"]
    assert body["request_id"] == response.headers["X-Request-Id"]


def test_create_session_fake_capture_success(
    client, db_factory, user_headers, monkeypatch
):
    monkeypatch.setattr(deps_module, "get_session_factory", lambda: db_factory)
    _add_subject(db_factory)

    created = client.post(
        "/api/sessions", json={"subject_id": _SUBJECT_ID}, headers=user_headers
    )
    body = created.json()
    assert body["code"] == 0
    assert body["data"]["status"] == "created"
    session_id = body["data"]["session_id"]

    detail = client.get(f"/api/sessions/{session_id}", headers=user_headers)
    payload = detail.json()
    assert payload["code"] == 0
    assert payload["degraded"] == []
    assert payload["data"]["status"] == "captured"
    assert payload["data"]["capture_status"] == "ok"
    assert payload["data"]["analysis_status"] == "pending"
    assert payload["data"]["codes"] == []
    assert payload["data"]["coverage"] == "both"
    assert payload["data"]["face_available"] is True
    assert payload["data"]["audio_available"] is True


def test_capture_failure_persists_and_does_not_leak_path(
    client, db_factory, user_headers, monkeypatch, caplog
):
    monkeypatch.setattr(deps_module, "get_session_factory", lambda: db_factory)

    def boom(**_kwargs):
        raise RuntimeError("failed reading D:/secret/audio.wav")

    monkeypatch.setattr(sessions_router, "_capture_result", boom)
    _add_subject(db_factory)
    caplog.set_level(logging.INFO, logger="app.api")

    created = client.post(
        "/api/sessions", json={"subject_id": _SUBJECT_ID}, headers=user_headers
    )
    session_id = created.json()["data"]["session_id"]

    payload = client.get(
        f"/api/sessions/{session_id}", headers=user_headers
    ).json()
    assert payload["code"] == 2001
    assert payload["data"]["status"] == "failed"
    assert payload["data"]["capture_status"] == "error"
    assert payload["data"]["codes"] == ["unknown"]
    assert "D:/secret" not in caplog.text


def test_create_session_returns_capture_busy_when_lock_held(
    client, db_factory, user_headers
):
    _add_subject(db_factory)
    acquired = sessions_router._CAPTURE_LOCK.acquire(blocking=False)
    assert acquired
    try:
        response = client.post(
            "/api/sessions", json={"subject_id": _SUBJECT_ID}, headers=user_headers
        )
    finally:
        sessions_router._CAPTURE_LOCK.release()

    body = response.json()
    assert response.status_code == 200
    assert body["code"] == 5000
    assert body["message"] == "capture_busy"
