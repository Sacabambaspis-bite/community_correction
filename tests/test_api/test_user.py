"""用户端接口测试：同意读写、撤回幂等与中性反馈（api@1.5 §5.3 / §7.1 / §7.8）。"""

from __future__ import annotations

import json
import uuid

from sqlalchemy import select

from app.db.models import AuditLog, CaptureSession, Subject

_SUBJECT_ID = "3b1e7c90-2f4a-4d51-8c6b-7d9e0f1a2b3c"
_OTHER_SUBJECT_ID = "9f1e2d3c-4b5a-4697-8877-665544332211"
_CREATED_AT = "2026-11-23T10:12:03+08:00"
_UPDATED_AT = "2026-11-23T10:12:36+08:00"

_SENSITIVE_KEYS = (
    "final_color",
    "risk_level",
    "evidence",
    "rules_fired",
    "transcript",
    "face_path",
    "audio_path",
)


def _add_subject(
    db_factory,
    subject_id: str = _SUBJECT_ID,
    *,
    consent_json: str | None = None,
    code: str | None = None,
) -> None:
    with db_factory() as db:
        db.add(
            Subject(
                id=subject_id,
                code=code or f"S{subject_id[:8]}",
                name="张某某",
                status="active",
                consent_json=consent_json,
                baseline_json=None,
                created_at=_CREATED_AT,
                updated_at=_UPDATED_AT,
            )
        )
        db.commit()


def _granted_consent(*, revoked_at: str | None = None) -> str:
    return json.dumps(
        {
            "schema_version": "consent@1.0",
            "general": {"granted": True, "at": _CREATED_AT},
            "face": {"granted": True, "at": _CREATED_AT},
            "audio": {"granted": True, "at": _CREATED_AT},
            "revoked_at": revoked_at,
            "retention_days": 180,
        }
    )


def _add_session(
    db_factory,
    session_id: str,
    *,
    subject_id: str = _SUBJECT_ID,
    status: str = "captured",
    capture_status: str | None = "ok",
    analysis_status: str = "pending",
    face_path: str | None = None,
    audio_path: str | None = None,
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
                codes="[]",
                captured_at=None if status == "created" else _UPDATED_AT,
                created_at=_CREATED_AT,
                updated_at=_UPDATED_AT,
            )
        )
        db.commit()


def test_get_consent_without_record(client, db_factory, user_headers):
    _add_subject(db_factory)

    body = client.get(
        "/api/user/consent",
        params={"subject_id": _SUBJECT_ID},
        headers=user_headers,
    ).json()

    assert body["code"] == 0
    data = body["data"]
    assert data["subject_id"] == _SUBJECT_ID
    for key in ("general", "face", "audio"):
        assert data[key] == {"granted": False, "at": None}
    assert data["revoked_at"] is None
    assert data["retention_days"] is None


def test_put_consent_grants_and_writes_audit(client, db_factory, user_headers):
    _add_subject(db_factory)

    body = client.put(
        "/api/user/consent",
        json={
            "subject_id": _SUBJECT_ID,
            "face": True,
            "audio": True,
            "retention_days": 180,
        },
        headers=user_headers,
    ).json()

    assert body["code"] == 0
    data = body["data"]
    assert data["general"]["granted"] is True
    assert data["face"]["granted"] is True
    assert data["audio"]["granted"] is True
    assert data["general"]["at"]
    assert data["face"]["at"]
    assert data["audio"]["at"]
    assert data["revoked_at"] is None
    assert data["retention_days"] == 180

    with db_factory() as db:
        subject = db.get(Subject, _SUBJECT_ID)
        stored = json.loads(subject.consent_json)
        assert stored["schema_version"] == "consent@1.0"
        assert stored["general"]["granted"] is True
        assert stored["face"]["granted"] is True
        assert stored["audio"]["granted"] is True
        assert stored["revoked_at"] is None
        assert stored["retention_days"] == 180

        logs = db.scalars(select(AuditLog)).all()
        assert len(logs) == 1
        log = logs[0]
        assert log.action == "consent.grant"
        assert log.actor_type == "subject"
        assert log.actor_id == _SUBJECT_ID
        assert log.target_type == "subject"
        assert log.target_id == _SUBJECT_ID
        assert json.loads(log.detail_json) == {"face": True, "audio": True}
        assert log.request_id


def test_put_consent_defaults_retention_days(client, db_factory, user_headers):
    _add_subject(db_factory)

    response = client.put(
        "/api/user/consent",
        json={"subject_id": _SUBJECT_ID, "face": True, "audio": True},
        headers=user_headers,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["code"] == 0
    assert body["data"]["retention_days"] == 180

    with db_factory() as db:
        subject = db.get(Subject, _SUBJECT_ID)
        stored = json.loads(subject.consent_json)
        assert stored["retention_days"] == 180


def test_put_consent_rejects_invalid_retention(client, db_factory, user_headers):
    _add_subject(db_factory)

    body = client.put(
        "/api/user/consent",
        json={
            "subject_id": _SUBJECT_ID,
            "face": True,
            "audio": True,
            "retention_days": 0,
        },
        headers=user_headers,
    ).json()

    assert body["code"] == 1001
    assert body["message"] == "invalid_request"


def test_put_consent_requires_subject_id(client, db_factory, user_headers):
    _add_subject(db_factory)

    body = client.put(
        "/api/user/consent",
        json={"face": True, "audio": True, "retention_days": 180},
        headers=user_headers,
    ).json()

    assert body["code"] == 1001
    assert body["message"] == "invalid_request"


def test_put_consent_rejects_both_channels_off(client, db_factory, user_headers):
    _add_subject(db_factory)

    body = client.put(
        "/api/user/consent",
        json={
            "subject_id": _SUBJECT_ID,
            "face": False,
            "audio": False,
            "retention_days": 180,
        },
        headers=user_headers,
    ).json()

    assert body["code"] == 1001
    assert body["message"] == "invalid_request"


def test_revoke_consent_and_idempotent(client, db_factory, user_headers):
    _add_subject(db_factory, consent_json=_granted_consent())

    first = client.post(
        "/api/user/consent/revoke",
        json={"subject_id": _SUBJECT_ID},
        headers=user_headers,
    ).json()
    assert first["code"] == 0
    revoked_at = first["data"]["revoked_at"]
    assert revoked_at
    # 撤回保留原有授权与留存期。
    assert first["data"]["general"]["granted"] is True
    assert first["data"]["face"]["granted"] is True
    assert first["data"]["audio"]["granted"] is True
    assert first["data"]["retention_days"] == 180

    with db_factory() as db:
        logs = db.scalars(select(AuditLog)).all()
        assert len(logs) == 1
        assert logs[0].action == "consent.revoke"
        assert logs[0].actor_type == "subject"
        assert logs[0].actor_id == _SUBJECT_ID
        assert logs[0].target_type == "subject"
        assert logs[0].target_id == _SUBJECT_ID

    second = client.post(
        "/api/user/consent/revoke",
        json={"subject_id": _SUBJECT_ID},
        headers=user_headers,
    ).json()
    assert second["code"] == 0
    assert second["data"]["revoked_at"] == revoked_at

    with db_factory() as db:
        assert len(db.scalars(select(AuditLog)).all()) == 1


def test_revoke_without_consent_conflicts(client, db_factory, user_headers):
    _add_subject(db_factory)

    body = client.post(
        "/api/user/consent/revoke",
        json={"subject_id": _SUBJECT_ID},
        headers=user_headers,
    ).json()

    assert body["code"] == 1005
    assert body["message"] == "consent_not_granted"

    with db_factory() as db:
        assert db.scalars(select(AuditLog)).all() == []


def test_get_consent_unknown_subject_returns_1004(client, user_headers):
    body = client.get(
        "/api/user/consent",
        params={"subject_id": _SUBJECT_ID},
        headers=user_headers,
    ).json()

    assert body["code"] == 1004
    assert body["message"] == "not_found"


def test_user_consent_requires_subject_role(client, db_factory, admin_headers):
    _add_subject(db_factory)

    body = client.get(
        "/api/user/consent",
        params={"subject_id": _SUBJECT_ID},
        headers=admin_headers,
    ).json()

    assert body["code"] == 1003
    assert body["message"] == "forbidden"


def test_feedback_shape_and_redaction(client, db_factory, user_headers):
    _add_subject(db_factory)
    session_id = "8f3c1b2e-4a5d-4c6e-9f10-1a2b3c4d5e6f"
    _add_session(
        db_factory,
        session_id,
        capture_status="ok",
        face_path="subjects/s/sessions/x/face.jpg",
        audio_path="subjects/s/sessions/x/audio.wav",
    )

    body = client.get(
        f"/api/user/sessions/{session_id}/feedback",
        params={"subject_id": _SUBJECT_ID},
        headers=user_headers,
    ).json()

    assert body["code"] == 0
    assert body["degraded"] == []
    data = body["data"]
    assert set(data) == {
        "session_id",
        "status",
        "summary_text",
        "suggestion",
        "next_action",
    }
    assert data["session_id"] == session_id
    assert data["status"] == "captured"
    assert data["suggestion"] == "keep_routine"
    assert data["summary_text"] == "本次记录已完成。"
    assert data["next_action"] == "下次按约定时间再来即可"
    for key in _SENSITIVE_KEYS:
        assert key not in data


def test_feedback_neutral_mapping(client, db_factory, user_headers):
    _add_subject(db_factory)
    cases = [
        ("created", None, "pending", "keep_routine", "本次记录仍在进行中。"),
        ("captured", "partial", "pending", "keep_routine", "本次记录已完成。"),
        ("captured", "no_face", "pending", "recapture", "本次记录已完成。"),
        ("failed", "error", "failed", "talk_to_staff", "本次记录未完成。"),
        ("failed", "partial", "failed", "recapture", "本次记录未完成。"),
    ]

    for status, capture_status, analysis_status, suggestion, summary in cases:
        session_id = str(uuid.uuid4())
        _add_session(
            db_factory,
            session_id,
            status=status,
            capture_status=capture_status,
            analysis_status=analysis_status,
        )
        body = client.get(
            f"/api/user/sessions/{session_id}/feedback",
            params={"subject_id": _SUBJECT_ID},
            headers=user_headers,
        ).json()
        assert body["code"] == 0, (status, capture_status, body)
        data = body["data"]
        assert data["suggestion"] == suggestion, (status, capture_status)
        assert data["summary_text"] == summary, (status, capture_status)
        for key in _SENSITIVE_KEYS:
            assert key not in data


def test_feedback_ownership(client, db_factory, user_headers):
    _add_subject(db_factory)
    session_id = "0a1b2c3d-4e5f-4071-8293-a4b5c6d7e8f9"
    _add_session(db_factory, session_id, capture_status="ok")

    forbidden = client.get(
        f"/api/user/sessions/{session_id}/feedback",
        params={"subject_id": _OTHER_SUBJECT_ID},
        headers=user_headers,
    ).json()
    assert forbidden["code"] == 1003
    assert forbidden["message"] == "forbidden"

    missing = client.get(
        f"/api/user/sessions/{session_id}/feedback",
        headers=user_headers,
    ).json()
    assert missing["code"] == 1001
    assert missing["message"] == "invalid_request"


def test_feedback_session_not_found(client, db_factory, user_headers):
    _add_subject(db_factory)

    body = client.get(
        f"/api/user/sessions/{uuid.uuid4()}/feedback",
        params={"subject_id": _SUBJECT_ID},
        headers=user_headers,
    ).json()

    assert body["code"] == 1004
    assert body["message"] == "not_found"
