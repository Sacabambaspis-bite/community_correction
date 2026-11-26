"""管理端媒体读取：按日影像/录音/转写与音频端点（api.md §7.21 / §7.22）。"""

from __future__ import annotations

import json
from datetime import datetime

import pytest
from sqlalchemy import select

import app.api.routers.admin as admin_router
from app.db.models import AuditLog, CaptureSession, Review, Subject

_SUBJECT_ID = "3b1e7c90-2f4a-4d51-8c6b-7d9e0f1a2b3c"
_AUDIO_BYTES = b"RIFF\x00\x00\x00\x00WAVEfmt "


def _iso(value: datetime) -> str:
    return value.isoformat(timespec="seconds")


def _add_subject(db_factory) -> None:
    now = datetime.now().astimezone()
    with db_factory() as db:
        db.add(
            Subject(
                id=_SUBJECT_ID,
                code="S001",
                name="测试对象",
                status="active",
                checkin_interval_days=1,
                report_interval_days=3,
                created_at=_iso(now),
                updated_at=_iso(now),
            )
        )
        db.commit()


def _add_session(
    db_factory,
    session_id: str,
    *,
    kind: str = "report",
    status: str = "captured",
    captured_at: datetime | None = None,
    face_path: str | None = None,
    audio_path: str | None = None,
    duration_sec: float | None = 12.5,
    analysis_json: str | None = None,
) -> None:
    now = datetime.now().astimezone()
    with db_factory() as db:
        db.add(
            CaptureSession(
                id=session_id,
                subject_id=_SUBJECT_ID,
                kind=kind,
                status=status,
                capture_status="ok",
                captured_at=_iso(captured_at) if captured_at else None,
                face_path=face_path,
                audio_path=audio_path,
                duration_sec=duration_sec,
                analysis_status="pending",
                analysis_json=analysis_json,
                codes="[]",
                created_at=_iso(now),
                updated_at=_iso(now),
            )
        )
        db.commit()


def _write_media(tmp_path, session_id: str, *, transcript: str | None = None) -> dict:
    directory = tmp_path / "subjects" / _SUBJECT_ID / "sessions" / session_id
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "face.jpg").write_bytes(b"placeholder-face")
    (directory / "audio.wav").write_bytes(_AUDIO_BYTES)
    if transcript is not None:
        (directory / "transcript.txt").write_text(transcript, encoding="utf-8")
    base = f"subjects/{_SUBJECT_ID}/sessions/{session_id}"
    return {"face_path": f"{base}/face.jpg", "audio_path": f"{base}/audio.wav"}


def _local(*args) -> datetime:
    return datetime(*args, tzinfo=datetime.now().astimezone().tzinfo)


def test_media_returns_latest_day_with_urls_and_transcript(
    client, db_factory, admin_headers, tmp_path, monkeypatch
):
    monkeypatch.setattr(admin_router, "STORAGE_ROOT", str(tmp_path))
    _add_subject(db_factory)
    checkin_id, report_id = "c0000000-0000-4000-8000-000000000001", "r0000000-0000-4000-8000-000000000001"
    _add_session(
        db_factory,
        checkin_id,
        kind="checkin",
        captured_at=_local(2026, 11, 25, 8, 12),
        face_path=f"subjects/{_SUBJECT_ID}/sessions/{checkin_id}/face.jpg",
        audio_path=None,
    )
    paths = _write_media(tmp_path, report_id, transcript="今天按时完成了思想汇报")
    _add_session(
        db_factory,
        report_id,
        captured_at=_local(2026, 11, 25, 22, 29),
        **paths,
    )

    body = client.get(f"/api/admin/subjects/{_SUBJECT_ID}/media", headers=admin_headers).json()

    assert body["code"] == 0
    data = body["data"]
    assert data["date"] == "2026-11-25"
    assert data["available_dates"] == ["2026-11-25"]
    items = data["items"]
    assert [entry["session_id"] for entry in items] == [checkin_id, report_id]
    assert items[0]["image_url"].endswith(f"/{checkin_id}/face")
    assert items[0]["audio_url"] is None
    assert items[1]["audio_url"].endswith(f"/{report_id}/audio")
    assert items[1]["transcript_text"] == "今天按时完成了思想汇报"
    assert items[1]["duration_sec"] == 12.5


def test_media_filters_by_requested_date(
    client, db_factory, admin_headers, tmp_path, monkeypatch
):
    monkeypatch.setattr(admin_router, "STORAGE_ROOT", str(tmp_path))
    _add_subject(db_factory)
    old_id, new_id = "r0000000-0000-4000-8000-000000000002", "r0000000-0000-4000-8000-000000000003"
    _add_session(db_factory, old_id, captured_at=_local(2026, 11, 24, 20, 0), **_write_media(tmp_path, old_id))
    _add_session(db_factory, new_id, captured_at=_local(2026, 11, 25, 10, 0), **_write_media(tmp_path, new_id))

    body = client.get(
        f"/api/admin/subjects/{_SUBJECT_ID}/media",
        params={"date": "2026-11-24"},
        headers=admin_headers,
    ).json()

    assert body["code"] == 0
    assert body["data"]["date"] == "2026-11-24"
    assert body["data"]["available_dates"] == ["2026-11-25", "2026-11-24"]
    assert [entry["session_id"] for entry in body["data"]["items"]] == [old_id]


def test_media_returns_null_item_for_empty_day(
    client, db_factory, admin_headers, tmp_path, monkeypatch
):
    monkeypatch.setattr(admin_router, "STORAGE_ROOT", str(tmp_path))
    _add_subject(db_factory)
    session_id = "r0000000-0000-4000-8000-000000000004"
    _add_session(db_factory, session_id, captured_at=_local(2026, 11, 25, 9, 0), **_write_media(tmp_path, session_id))

    body = client.get(
        f"/api/admin/subjects/{_SUBJECT_ID}/media",
        params={"date": "2026-11-01"},
        headers=admin_headers,
    ).json()

    assert body["code"] == 0
    assert body["data"]["items"] == []
    assert body["data"]["date"] == "2026-11-01"


def test_media_rejects_invalid_date(client, db_factory, admin_headers):
    _add_subject(db_factory)

    body = client.get(
        f"/api/admin/subjects/{_SUBJECT_ID}/media",
        params={"date": "2026/11/25"},
        headers=admin_headers,
    ).json()

    assert body["code"] == 1001
    assert body["message"] == "invalid_date"


def test_media_unknown_subject_returns_not_found(client, admin_headers):
    body = client.get(
        "/api/admin/subjects/00000000-0000-4000-8000-000000000000/media",
        headers=admin_headers,
    ).json()

    assert body["code"] == 1004
    assert body["message"] == "not_found"


def test_media_requires_admin_token(client):
    response = client.get(f"/api/admin/subjects/{_SUBJECT_ID}/media")

    # 鉴权失败按统一信封返回 HTTP 200 + 业务码。
    assert response.status_code == 200
    assert response.json()["code"] in (1002, 1003)


def test_media_writes_transcript_audit_log(
    client, db_factory, admin_headers, tmp_path, monkeypatch
):
    monkeypatch.setattr(admin_router, "STORAGE_ROOT", str(tmp_path))
    _add_subject(db_factory)
    session_id = "r0000000-0000-4000-8000-000000000005"
    _add_session(db_factory, session_id, captured_at=_local(2026, 11, 25, 10, 0), **_write_media(tmp_path, session_id, transcript="需要留痕的文本"))

    client.get(
        f"/api/admin/subjects/{_SUBJECT_ID}/media",
        params={"date": "2026-11-25"},
        headers=admin_headers,
    )

    with db_factory() as db:
        logs = db.execute(
            select(AuditLog).where(AuditLog.action == "sensitive.view")
        ).scalars().all()
    assert len(logs) == 1
    assert logs[0].target_type == "subject"
    assert logs[0].target_id == _SUBJECT_ID
    assert json.loads(logs[0].detail_json) == {
        "field": "transcript",
        "date": "2026-11-25",
        "count": 1,
    }


def test_media_items_are_ascending_by_captured_at(
    client, db_factory, admin_headers, tmp_path, monkeypatch
):
    """同一天多条记录按时间升序返回，前端默认选中最后一条（最新）。"""
    monkeypatch.setattr(admin_router, "STORAGE_ROOT", str(tmp_path))
    _add_subject(db_factory)
    first, second, third = (
        "r0000000-0000-4000-8000-000000000010",
        "r0000000-0000-4000-8000-000000000011",
        "r0000000-0000-4000-8000-000000000012",
    )
    _add_session(db_factory, third, captured_at=_local(2026, 11, 25, 20, 0), **_write_media(tmp_path, third))
    _add_session(db_factory, first, captured_at=_local(2026, 11, 25, 8, 0), **_write_media(tmp_path, first))
    _add_session(db_factory, second, captured_at=_local(2026, 11, 25, 12, 0), **_write_media(tmp_path, second))

    body = client.get(
        f"/api/admin/subjects/{_SUBJECT_ID}/media",
        params={"date": "2026-11-25"},
        headers=admin_headers,
    ).json()

    assert body["code"] == 0
    items = body["data"]["items"]
    assert [entry["session_id"] for entry in items] == [first, second, third]
    assert items[-1]["session_id"] == third
    assert body["data"]["available_dates"] == ["2026-11-25"]


def test_media_audit_counts_multiple_transcripts(
    client, db_factory, admin_headers, tmp_path, monkeypatch
):
    monkeypatch.setattr(admin_router, "STORAGE_ROOT", str(tmp_path))
    _add_subject(db_factory)
    for index, hour in enumerate((9, 10), start=20):
        session_id = f"r0000000-0000-4000-8000-0000000000{index}"
        _add_session(
            db_factory,
            session_id,
            captured_at=_local(2026, 11, 25, hour, 0),
            **_write_media(tmp_path, session_id, transcript=f"第 {hour} 点汇报"),
        )

    client.get(
        f"/api/admin/subjects/{_SUBJECT_ID}/media",
        params={"date": "2026-11-25"},
        headers=admin_headers,
    )

    with db_factory() as db:
        logs = db.execute(
            select(AuditLog).where(AuditLog.action == "sensitive.view")
        ).scalars().all()
    assert len(logs) == 1
    assert json.loads(logs[0].detail_json)["count"] == 2


def test_media_returns_emotion_aligned_with_each_record(
    client, db_factory, admin_headers, tmp_path, monkeypatch
):
    """情绪结果按会话独立解析，checkin 无情绪通道时为 null。"""
    monkeypatch.setattr(admin_router, "STORAGE_ROOT", str(tmp_path))
    _add_subject(db_factory)
    checkin_id = "c0000000-0000-4000-8000-000000000020"
    report_id = "r0000000-0000-4000-8000-000000000021"
    _add_session(
        db_factory,
        checkin_id,
        kind="checkin",
        captured_at=_local(2026, 11, 25, 8, 0),
        face_path=f"subjects/{_SUBJECT_ID}/sessions/{checkin_id}/face.jpg",
        audio_path=None,
    )
    emotion_payload = json.dumps(
        {
            "channels": {
                "emotion": {
                    "status": "ok",
                    "model_version": "sensevoice-emotion@1.0",
                    "output": {"valence": 0.6, "arousal": 0.6, "label": "neutral"},
                }
            }
        }
    )
    _add_session(
        db_factory,
        report_id,
        captured_at=_local(2026, 11, 25, 9, 0),
        analysis_json=emotion_payload,
        **_write_media(tmp_path, report_id, transcript="情绪对齐校验"),
    )

    body = client.get(
        f"/api/admin/subjects/{_SUBJECT_ID}/media",
        params={"date": "2026-11-25"},
        headers=admin_headers,
    ).json()

    items = body["data"]["items"]
    assert [entry["session_id"] for entry in items] == [checkin_id, report_id]
    assert items[0]["emotion"] is None
    assert items[1]["emotion"] == {
        "status": "ok",
        "model_version": "sensevoice-emotion@1.0",
        "valence": 0.6,
        "arousal": 0.6,
        "label": "neutral",
    }


def test_audio_endpoint_streams_wav_and_audits(
    client, db_factory, admin_headers, tmp_path, monkeypatch
):
    monkeypatch.setattr(admin_router, "STORAGE_ROOT", str(tmp_path))
    _add_subject(db_factory)
    session_id = "r0000000-0000-4000-8000-000000000006"
    _add_session(db_factory, session_id, captured_at=_local(2026, 11, 25, 10, 0), **_write_media(tmp_path, session_id))

    response = client.get(f"/api/admin/sessions/{session_id}/audio", headers=admin_headers)

    assert response.status_code == 200
    assert response.headers["content-type"] == "audio/wav"
    assert response.content == _AUDIO_BYTES
    with db_factory() as db:
        logs = db.execute(select(AuditLog).where(AuditLog.action == "sensitive.view")).scalars().all()
    assert len(logs) == 1
    assert logs[0].target_type == "session"
    assert logs[0].target_id == session_id
    assert json.loads(logs[0].detail_json) == {"field": "audio"}


def test_audio_missing_file_returns_not_found(
    client, db_factory, admin_headers, tmp_path, monkeypatch
):
    monkeypatch.setattr(admin_router, "STORAGE_ROOT", str(tmp_path))
    _add_subject(db_factory)
    session_id = "r0000000-0000-4000-8000-000000000007"
    # DB 记录存在但磁盘文件缺失
    _add_session(
        db_factory,
        session_id,
        captured_at=_local(2026, 11, 25, 10, 0),
        audio_path=f"subjects/{_SUBJECT_ID}/sessions/{session_id}/audio.wav",
    )

    body = client.get(f"/api/admin/sessions/{session_id}/audio", headers=admin_headers).json()

    assert body["code"] == 1004
    assert body["message"] == "not_found"


def test_audio_without_audio_path_returns_not_found(
    client, db_factory, admin_headers
):
    _add_subject(db_factory)
    session_id = "c0000000-0000-4000-8000-000000000008"
    _add_session(
        db_factory,
        session_id,
        kind="checkin",
        captured_at=_local(2026, 11, 25, 8, 0),
        face_path=f"subjects/{_SUBJECT_ID}/sessions/{session_id}/face.jpg",
    )

    body = client.get(f"/api/admin/sessions/{session_id}/audio", headers=admin_headers).json()

    assert body["code"] == 1004


def test_media_returns_three_channel_analysis(
    client, db_factory, admin_headers, tmp_path, monkeypatch
):
    """analysis 固定三键：face / emotion / psych，缺通道为 None。"""
    monkeypatch.setattr(admin_router, "STORAGE_ROOT", str(tmp_path))
    _add_subject(db_factory)
    checkin_id = "c0000000-0000-4000-8000-000000000030"
    report_id = "r0000000-0000-4000-8000-000000000031"
    _add_session(
        db_factory,
        checkin_id,
        kind="checkin",
        captured_at=_local(2026, 11, 25, 8, 0),
        face_path=f"subjects/{_SUBJECT_ID}/sessions/{checkin_id}/face.jpg",
        analysis_json=json.dumps(
            {
                "channels": {
                    "face": {
                        "status": "ok",
                        "model_version": "mock-face@1.0",
                        "output": {
                            "expression_label": "neutral",
                            "intensity": 0.22,
                            "face_confidence": 0.71,
                            "frame_count": 3,
                            "valid_frames": 3,
                        },
                    }
                }
            }
        ),
    )
    _add_session(
        db_factory,
        report_id,
        captured_at=_local(2026, 11, 25, 9, 0),
        analysis_json=json.dumps(
            {
                "channels": {
                    "emotion": {
                        "status": "ok",
                        "model_version": "sensevoice-emotion@1.0",
                        "output": {"valence": 0.6, "arousal": 0.6, "label": "neutral"},
                    },
                    "psych": {
                        "status": "ok",
                        "model_version": "mock-psych@1.0",
                        "output": {
                            "signal_strength": 41.2,
                            "intent_flag": "none",
                            "keywords": ["累", "睡不着"],
                            "rationale_signal": "出现疲劳与睡眠相关表达",
                        },
                    },
                }
            }
        ),
        **_write_media(tmp_path, report_id, transcript="三路分析校验"),
    )

    body = client.get(
        f"/api/admin/subjects/{_SUBJECT_ID}/media",
        params={"date": "2026-11-25"},
        headers=admin_headers,
    ).json()

    items = body["data"]["items"]
    checkin, report = items
    assert checkin["analysis"]["face"]["expression_label"] == "neutral"
    assert checkin["analysis"]["emotion"] is None
    assert checkin["analysis"]["psych"] is None
    assert report["analysis"]["face"] is None
    assert report["analysis"]["emotion"]["label"] == "neutral"
    assert report["analysis"]["psych"]["signal_strength"] == 41.2
    assert report["analysis"]["psych"]["keywords"] == ["累", "睡不着"]
    # 顶层 emotion 保留兼容，与 analysis.emotion 一致。
    assert report["emotion"] == report["analysis"]["emotion"]


def test_media_rules_and_evidence_follow_latest_review(
    client, db_factory, admin_headers, tmp_path, monkeypatch
):
    """规则/证据只取该会话条目，且使用最新一条包含它的复盘。"""
    monkeypatch.setattr(admin_router, "STORAGE_ROOT", str(tmp_path))
    _add_subject(db_factory)
    first, second = (
        "r0000000-0000-4000-8000-000000000040",
        "r0000000-0000-4000-8000-000000000041",
    )
    _add_session(db_factory, first, captured_at=_local(2026, 11, 25, 9, 0), **_write_media(tmp_path, first))
    _add_session(db_factory, second, captured_at=_local(2026, 11, 25, 10, 0), **_write_media(tmp_path, second))

    def evidence(rule_id: str, session_id: str | None, value: float) -> dict:
        row = {
            "rule_id": rule_id,
            "rule_version": "1.0",
            "field_path": "channels.psych.output.signal_strength",
            "observed_value": value,
            "threshold_key": "SINGLE_ORANGE_SIGNAL_MIN",
            "threshold_value": 40,
            "triggered_at": "2026-11-25T23:00:00+08:00",
        }
        if session_id is not None:
            row["session_id"] = session_id
        return row

    with db_factory() as db:
        db.add(
            Review(
                id="old-review",
                subject_id=_SUBJECT_ID,
                source_session_id=first,
                window_start="2026-11-19",
                window_end="2026-11-25",
                window_days=7,
                single_session_risk="none",
                trend_color="blue",
                final_color="blue",
                consistency="high",
                manual_review=0,
                rules_fired=json.dumps(["R_TREND_BLUE"]),
                evidence_json=json.dumps([evidence("R_TREND_BLUE", first, 10)]),
                grading_version="1.0",
                created_at=_iso(_local(2026, 11, 25, 23, 0)),
            )
        )
        db.add(
            Review(
                id="new-review",
                subject_id=_SUBJECT_ID,
                source_session_id=second,
                window_start="2026-11-19",
                window_end="2026-11-26",
                window_days=7,
                single_session_risk="orange",
                trend_color="yellow",
                final_color="orange",
                consistency="medium",
                manual_review=0,
                rules_fired=json.dumps(["R_SINGLE_ORANGE", "R_CONSISTENCY_CAP"]),
                evidence_json=json.dumps(
                    [
                        evidence("R_SINGLE_ORANGE", first, 41.2),
                        evidence("R_SINGLE_ORANGE", first, 0.55),
                        evidence("R_SINGLE_ORANGE", second, 48.0),
                        evidence("R_CONSISTENCY_CAP", None, 0.5),
                    ]
                ),
                grading_version="1.0",
                created_at=_iso(_local(2026, 11, 25, 23, 30)),
            )
        )
        db.commit()

    body = client.get(
        f"/api/admin/subjects/{_SUBJECT_ID}/media",
        params={"date": "2026-11-25"},
        headers=admin_headers,
    ).json()

    items = body["data"]["items"]
    assert [entry["session_id"] for entry in items] == [first, second]
    first_item, second_item = items
    assert first_item["review_color"] == "orange"
    assert first_item["rules_fired"] == ["R_SINGLE_ORANGE"]
    assert len(first_item["evidence"]) == 2
    assert {row["session_id"] for row in first_item["evidence"]} == {first}
    assert second_item["rules_fired"] == ["R_SINGLE_ORANGE"]
    assert second_item["evidence"][0]["session_id"] == second


def test_media_without_review_returns_empty_rules(
    client, db_factory, admin_headers, tmp_path, monkeypatch
):
    monkeypatch.setattr(admin_router, "STORAGE_ROOT", str(tmp_path))
    _add_subject(db_factory)
    session_id = "r0000000-0000-4000-8000-000000000050"
    _add_session(db_factory, session_id, captured_at=_local(2026, 11, 25, 9, 0), **_write_media(tmp_path, session_id))

    body = client.get(
        f"/api/admin/subjects/{_SUBJECT_ID}/media",
        params={"date": "2026-11-25"},
        headers=admin_headers,
    ).json()

    item = body["data"]["items"][0]
    assert item["analysis"] == {"face": None, "emotion": None, "psych": None}
    assert item["rules_fired"] == []
    assert item["evidence"] == []
    assert item["review_color"] is None


def test_removed_sensevoice_sync_endpoints_return_not_found(
    client, db_factory, admin_headers
):
    """思想汇报同步模块已下线，旧端点不再挂载。"""
    _add_subject(db_factory)

    responses = [
        client.post(
            f"/api/admin/subjects/{_SUBJECT_ID}/sensevoice-sync",
            headers=admin_headers,
        ),
        client.get(
            f"/api/admin/subjects/{_SUBJECT_ID}/sensevoice-syncs",
            headers=admin_headers,
        ),
        client.get(
            "/api/admin/sensevoice-syncs/00000000-0000-4000-8000-000000000000",
            headers=admin_headers,
        ),
    ]
    # 未挂载路由按统一信封返回 HTTP 200 + code=1004（api.md §2）。
    assert [response.status_code for response in responses] == [200, 200, 200]
    assert [response.json()["code"] for response in responses] == [1004, 1004, 1004]
