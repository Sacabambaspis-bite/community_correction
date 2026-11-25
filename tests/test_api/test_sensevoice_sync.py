"""管理端思想汇报同步契约测试（api@1.5 §7.15/§7.16/§7.17、db@1.5 §7）。

全部用例禁止真实网络与真实模型：成功与失败路径均 monkeypatch
``app.api.routers.admin.sync_report``，``sync_configured`` 所需的三个环境变量
只在需要时由 monkeypatch 注入，并由 autouse fixture 在每个用例前后清理。
"""

from __future__ import annotations

import json
from typing import Optional

import pytest
from sqlalchemy import select

import app.api.routers.admin as admin_router
from app.analysis.sensevoice_sync import SensevoiceSyncError, SensevoiceSyncResult
from app.db.models import AuditLog, CaptureSession, SensevoiceSync, Subject

_SUBJECT_ID = "3b1e7c90-2f4a-4d51-8c6b-7d9e0f1a2b3c"
_OTHER_SUBJECT_ID = "1a0d27be-9bab-55b7-82b2-bd33bae2d2fc"
_CREATED_AT = "2026-11-23T09:00:00+08:00"
_CAPTURED_AT = "2026-11-23T10:00:00+08:00"

_TRANSCRIPT = "最近工作压力比较大，晚上总是睡不好……"
_EMOTION = {
    "schema_version": "emotion@1.0",
    "primary": "焦虑",
    "confidence": 0.87,
    "scores": {"焦虑": 0.87, "平静": 0.13},
    "triggers": [
        {
            "text": "最近总是睡不好，心里很慌",
            "label": "焦虑",
            "start_sec": 3.2,
            "end_sec": 5.1,
        }
    ],
}
_DATA_VERSION = "sensevoice@1.0+20261125T101203"

_ENV_NAMES = (
    "SENSEVOICE_SYNC_ENABLED",
    "SENSEVOICE_API_URL",
    "SENSEVOICE_API_KEY",
    "SENSEVOICE_EMOTION_API_URL",
)


@pytest.fixture(autouse=True)
def _isolate_sensevoice_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """每个用例从「开关关闭、未配置」的干净状态开始，结束后自动还原。"""
    for name in _ENV_NAMES:
        monkeypatch.delenv(name, raising=False)


def _enable_sync(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SENSEVOICE_SYNC_ENABLED", "1")
    monkeypatch.setenv("SENSEVOICE_API_URL", "http://sensevoice.invalid/asr")
    monkeypatch.setenv("SENSEVOICE_API_KEY", "test-key")
    monkeypatch.setenv("SENSEVOICE_EMOTION_API_URL", "http://sensevoice.invalid/emotion")


def _forbid_sync_call(monkeypatch: pytest.MonkeyPatch) -> None:
    """未到调用点的用例也要保证绝不触达 sync_report。"""

    def _boom(*_args, **_kwargs):
        raise AssertionError("sync_report must not be called")

    monkeypatch.setattr(admin_router, "sync_report", _boom)


def _add_subject(
    db_factory,
    subject_id: str = _SUBJECT_ID,
    *,
    code: str = "S001",
    name: str = "张某某",
) -> None:
    with db_factory() as db:
        db.add(
            Subject(
                id=subject_id,
                code=code,
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
    kind: str = "report",
    status: str = "captured",
    audio_path: Optional[str] = None,
    captured_at: Optional[str] = _CAPTURED_AT,
    duration_sec: Optional[float] = 12.5,
) -> None:
    with db_factory() as db:
        db.add(
            CaptureSession(
                id=session_id,
                subject_id=subject_id,
                kind=kind,
                status=status,
                capture_status="ok",
                face_path=None,
                audio_path=audio_path,
                analysis_status="pending",
                analysis_json=None,
                codes="[]",
                captured_at=captured_at,
                duration_sec=duration_sec,
                created_at=_CREATED_AT,
                updated_at=_CAPTURED_AT,
            )
        )
        db.commit()


def _write_audio(tmp_path, subject_id: str, session_id: str) -> str:
    """在临时存储根下写入非空音频，返回库内存放的相对路径。"""
    relative = f"subjects/{subject_id}/sessions/{session_id}/audio.wav"
    target = tmp_path / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(b"RIFF-fake-audio-bytes")
    return relative


def _row_counts(db_factory) -> tuple[int, int]:
    with db_factory() as db:
        syncs = len(db.scalars(select(SensevoiceSync)).all())
        logs = len(db.scalars(select(AuditLog)).all())
    return syncs, logs


def _assert_no_rows(db_factory) -> None:
    assert _row_counts(db_factory) == (0, 0)


# ---- §7.15 POST /api/admin/subjects/{subject_id}/sensevoice-sync ----


def test_sync_subject_not_found(client, admin_headers):
    body = client.post(
        "/api/admin/subjects/not-a-subject/sensevoice-sync", headers=admin_headers
    ).json()

    assert body["code"] == 1004, body
    assert body["message"] == "not_found"


@pytest.mark.parametrize("switch_value", [None, "0"])
def test_sync_disabled_returns_5001_without_rows(
    client, db_factory, admin_headers, monkeypatch, switch_value
):
    if switch_value is not None:
        monkeypatch.setenv("SENSEVOICE_SYNC_ENABLED", switch_value)
    _forbid_sync_call(monkeypatch)
    _add_subject(db_factory)
    session_id = "8f3c1b2e-4a5d-4c6e-9f10-1a2b3c4d5e6f"
    _add_session(db_factory, session_id, audio_path="subjects/x/audio.wav")

    body = client.post(
        f"/api/admin/subjects/{_SUBJECT_ID}/sensevoice-sync", headers=admin_headers
    ).json()

    assert body["code"] == 5001, body
    assert body["message"] == "sensevoice_sync_disabled"
    _assert_no_rows(db_factory)


def test_sync_enabled_but_unconfigured_returns_5001_without_rows(
    client, db_factory, admin_headers, tmp_path, monkeypatch
):
    monkeypatch.setenv("SENSEVOICE_SYNC_ENABLED", "1")
    _forbid_sync_call(monkeypatch)
    _add_subject(db_factory)
    session_id = "8f3c1b2e-4a5d-4c6e-9f10-1a2b3c4d5e6f"
    audio_path = _write_audio(tmp_path, _SUBJECT_ID, session_id)
    _add_session(db_factory, session_id, audio_path=audio_path)

    body = client.post(
        f"/api/admin/subjects/{_SUBJECT_ID}/sensevoice-sync", headers=admin_headers
    ).json()

    assert body["code"] == 5001, body
    assert body["message"] == "sensevoice_unavailable"
    _assert_no_rows(db_factory)


def test_sync_no_report_session_returns_1005_without_rows(
    client, db_factory, admin_headers, tmp_path, monkeypatch
):
    monkeypatch.setenv("SENSEVOICE_SYNC_ENABLED", "1")
    _forbid_sync_call(monkeypatch)
    _add_subject(db_factory)

    body = client.post(
        f"/api/admin/subjects/{_SUBJECT_ID}/sensevoice-sync", headers=admin_headers
    ).json()
    assert body["code"] == 1005, body
    assert body["message"] == "no_report_audio"

    # 只有签到会话（kind=checkin）也不算可用汇报会话。
    checkin_id = "5a6b7c8d-9e0f-4a1b-b2c3-d4e5f6a7b8c9"
    audio_path = _write_audio(tmp_path, _SUBJECT_ID, checkin_id)
    _add_session(
        db_factory, checkin_id, kind="checkin", audio_path=audio_path
    )

    again = client.post(
        f"/api/admin/subjects/{_SUBJECT_ID}/sensevoice-sync", headers=admin_headers
    ).json()
    assert again["code"] == 1005, again
    assert again["message"] == "no_report_audio"
    _assert_no_rows(db_factory)


def test_sync_session_owned_by_other_subject_returns_1004(
    client, db_factory, admin_headers, monkeypatch
):
    _enable_sync(monkeypatch)
    _forbid_sync_call(monkeypatch)
    _add_subject(db_factory)
    _add_subject(db_factory, _OTHER_SUBJECT_ID, code="S002", name="李某某")
    foreign_session = "b1c67812-dbad-5718-8b1a-410464f42b20"
    _add_session(
        db_factory,
        foreign_session,
        subject_id=_OTHER_SUBJECT_ID,
        audio_path="subjects/foreign/audio.wav",
    )

    body = client.post(
        f"/api/admin/subjects/{_SUBJECT_ID}/sensevoice-sync",
        json={"session_id": foreign_session},
        headers=admin_headers,
    ).json()

    assert body["code"] == 1004, body
    assert body["message"] == "not_found"
    _assert_no_rows(db_factory)


def test_sync_success_persists_summary_audit_and_sensitive_detail(
    client, db_factory, admin_headers, tmp_path, monkeypatch
):
    _enable_sync(monkeypatch)
    monkeypatch.setattr(admin_router, "STORAGE_ROOT", str(tmp_path))
    calls: list[str] = []

    def _fake_sync(audio_file, *, duration_sec=None):
        calls.append(str(audio_file))
        return SensevoiceSyncResult(
            provider="sensevoice",
            transcript_text=_TRANSCRIPT,
            transcript_language="zh",
            emotion=_EMOTION,
            data_version=_DATA_VERSION,
        )

    monkeypatch.setattr(admin_router, "sync_report", _fake_sync)

    _add_subject(db_factory)
    session_id = "8f3c1b2e-4a5d-4c6e-9f10-1a2b3c4d5e6f"
    audio_path = _write_audio(tmp_path, _SUBJECT_ID, session_id)
    _add_session(db_factory, session_id, audio_path=audio_path)

    body = client.post(
        f"/api/admin/subjects/{_SUBJECT_ID}/sensevoice-sync", headers=admin_headers
    ).json()

    assert body["code"] == 0, body
    assert body["degraded"] == []
    data = body["data"]
    assert data["subject_id"] == _SUBJECT_ID
    assert data["session_id"] == session_id
    assert data["status"] == "succeeded"
    assert data["provider"] == "sensevoice"
    assert data["emotion_primary"] == "焦虑"
    assert data["emotion_confidence"] == pytest.approx(0.87)
    assert data["data_version"] == _DATA_VERSION
    assert data["operator"] == "staff"
    assert data["sync_id"]
    assert "transcript_text" not in data
    assert _TRANSCRIPT not in json.dumps(body, ensure_ascii=False)
    assert calls and calls[0].endswith("audio.wav")

    # 落库字段与同步结果一致。
    with db_factory() as db:
        sync = db.get(SensevoiceSync, data["sync_id"])
        assert sync is not None
        assert sync.subject_id == _SUBJECT_ID
        assert sync.session_id == session_id
        assert sync.status == "succeeded"
        assert sync.provider == "sensevoice"
        assert sync.transcript_text == _TRANSCRIPT
        assert sync.transcript_language == "zh"
        assert json.loads(sync.emotion_json) == _EMOTION
        assert sync.emotion_primary == "焦虑"
        assert sync.emotion_confidence == pytest.approx(0.87)
        assert sync.data_version == _DATA_VERSION
        assert sync.operator == "staff"
        assert sync.error_code is None
        assert sync.error_message is None
        assert sync.created_at
        assert sync.updated_at

        logs = db.scalars(
            select(AuditLog).where(AuditLog.action == "sensevoice.sync")
        ).all()
        assert len(logs) == 1
        assert logs[0].target_type == "sensevoice_sync"
        assert logs[0].target_id == data["sync_id"]
        detail = logs[0].detail_json or ""
        assert set(json.loads(detail)) == {"session_id", "data_version", "operator"}
        assert _TRANSCRIPT not in detail
        assert "睡不好" not in detail

    # 列表不返回转写原文 / 情绪片段。
    listed = client.get(
        f"/api/admin/subjects/{_SUBJECT_ID}/sensevoice-syncs", headers=admin_headers
    )
    assert listed.status_code == 200
    list_body = listed.json()
    assert list_body["code"] == 0, list_body
    assert list_body["data"]["total"] == 1
    item = list_body["data"]["items"][0]
    assert item["sync_id"] == data["sync_id"]
    assert "transcript_text" not in item
    assert "emotion" not in item
    assert '"transcript_text"' not in listed.text
    assert '"emotion"' not in listed.text

    # 详情返回全文与结构化情绪，并写 sensitive.view 留痕。
    detail_response = client.get(
        f"/api/admin/sensevoice-syncs/{data['sync_id']}", headers=admin_headers
    )
    assert detail_response.status_code == 200
    detail_body = detail_response.json()
    assert detail_body["code"] == 0, detail_body
    detail_data = detail_body["data"]
    assert detail_data["transcript_text"] == _TRANSCRIPT
    assert detail_data["transcript_language"] == "zh"
    assert detail_data["emotion"] == _EMOTION
    assert detail_data["updated_at"]

    with db_factory() as db:
        view_logs = db.scalars(
            select(AuditLog).where(AuditLog.action == "sensitive.view")
        ).all()
        assert len(view_logs) == 1
        assert view_logs[0].target_type == "sensevoice_sync"
        assert view_logs[0].target_id == data["sync_id"]
        assert len(db.scalars(select(AuditLog)).all()) == 2


@pytest.mark.parametrize("error_code", ["emotion_failed", "transcription_failed"])
def test_sync_failure_rolls_back_without_rows(
    client, db_factory, admin_headers, tmp_path, monkeypatch, error_code
):
    _enable_sync(monkeypatch)
    monkeypatch.setattr(admin_router, "STORAGE_ROOT", str(tmp_path))

    def _failing_sync(*_args, **_kwargs):
        raise SensevoiceSyncError(error_code, "boom")

    monkeypatch.setattr(admin_router, "sync_report", _failing_sync)

    _add_subject(db_factory)
    session_id = "426a55e9-f4e7-5e20-95e3-ba28694f74b6"
    audio_path = _write_audio(tmp_path, _SUBJECT_ID, session_id)
    _add_session(db_factory, session_id, audio_path=audio_path)

    body = client.post(
        f"/api/admin/subjects/{_SUBJECT_ID}/sensevoice-sync", headers=admin_headers
    ).json()

    assert body["code"] == 2004, body
    assert body["message"] == error_code
    _assert_no_rows(db_factory)


# ---- §7.17 GET /api/admin/sensevoice-syncs/{sync_id} ----


def test_sync_detail_not_found_returns_1004(client, admin_headers):
    body = client.get(
        "/api/admin/sensevoice-syncs/not-a-sync", headers=admin_headers
    ).json()

    assert body["code"] == 1004, body
    assert body["message"] == "not_found"


# ---- §7.16 GET /api/admin/subjects/{subject_id}/sensevoice-syncs ----


def test_sync_list_subject_not_found_returns_1004(client, admin_headers):
    body = client.get(
        "/api/admin/subjects/not-a-subject/sensevoice-syncs", headers=admin_headers
    ).json()

    assert body["code"] == 1004, body
    assert body["message"] == "not_found"


@pytest.mark.parametrize(
    "query",
    ["page=0", "page_size=101"],
    ids=["page-zero", "page-size-over-max"],
)
def test_sync_list_rejects_out_of_range_paging(
    client, db_factory, admin_headers, query
):
    _add_subject(db_factory)

    body = client.get(
        f"/api/admin/subjects/{_SUBJECT_ID}/sensevoice-syncs?{query}",
        headers=admin_headers,
    ).json()

    assert body["code"] == 1001, body
    assert body["message"] == "invalid_request"
