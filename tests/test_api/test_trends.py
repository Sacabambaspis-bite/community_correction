"""对象心理状态趋势端点测试（api@1.5 §7.18）。"""

from __future__ import annotations

import json
import statistics
from datetime import date, datetime, time, timedelta
from typing import Optional
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.db.models import AuditLog, CaptureSession, Review, Subject

_SUBJECT_ID = "3b1e7c90-2f4a-4d51-8c6b-7d9e0f1a2b3c"
_OTHER_ID = "9e8d7c6b-5a4f-4e3d-2c1b-0a9f8e7d6c5b"
_TZ = datetime.now().astimezone().tzinfo


def _today() -> date:
    return datetime.now().astimezone().date()


def _iso(value: datetime) -> str:
    return value.isoformat(timespec="seconds")


def _add_subject(
    db_factory,
    *,
    subject_id: str = _SUBJECT_ID,
    code: str = "S001",
    checkin_interval_days: int = 1,
    report_interval_days: int = 3,
) -> None:
    now = datetime.now().astimezone()
    with db_factory() as db:
        db.add(
            Subject(
                id=subject_id,
                code=code,
                name="趋势对象",
                status="active",
                checkin_interval_days=checkin_interval_days,
                report_interval_days=report_interval_days,
                created_at=_iso(now - timedelta(days=30)),
                updated_at=_iso(now),
            )
        )
        db.commit()


def _analysis(
    session_id: str,
    *,
    valence: float = 0.0,
    signal: float = 40.0,
    risk: str = "none",
    consistency: str = "medium",
    conflict: bool = False,
    degraded: bool = False,
    arousal: Optional[float] = 0.4,
    emotion: bool = True,
) -> str:
    """最小可用的 analysis_json；含 transcript_path 以便验证不泄漏。"""
    emotion_output = (
        None
        if not emotion
        else {
            "valence": valence,
            "arousal": arousal,
            "label": "neutral",
        }
    )
    return json.dumps(
        {
            "schema_version": "1.0",
            "session_id": session_id,
            "subject_id": _SUBJECT_ID,
            "overall": {
                "text_valence": valence,
                "text_signal": signal,
                "risk_level": risk,
                "summary_signal": "中性描述",
            },
            "channels": {
                "asr": {
                    "status": "ok",
                    "model_version": "mock-asr@1.0",
                    "latency_ms": 1,
                    "confidence": 0.9,
                    "output": {
                        "transcript_path": f"subjects/x/sessions/{session_id}/transcript.txt",
                        "duration_sec": 10.0,
                        "speech_ratio": 0.5,
                        "char_count": 12,
                    },
                    "reason": None,
                },
                "emotion": {
                    "status": "ok" if emotion else "skipped",
                    "model_version": "mock-emotion@1.0",
                    "latency_ms": 1,
                    "confidence": 0.8,
                    "output": emotion_output,
                    "reason": None,
                },
                "face": {
                    "status": "ok",
                    "model_version": "mock-face@1.0",
                    "latency_ms": 1,
                    "confidence": 0.7,
                    "output": {
                        "expression_label": "neutral",
                        "intensity": 0.2,
                        "face_confidence": 0.7,
                        "frame_count": 3,
                        "valid_frames": 3,
                    },
                    "reason": None,
                },
                "psych": {
                    "status": "degraded" if degraded else "ok",
                    "model_version": "mock-psych@1.0",
                    "latency_ms": 1,
                    "confidence": 0.7,
                    "output": {
                        "signal_strength": signal,
                        "intent_flag": "none",
                        "keywords": [],
                        "rationale_signal": "中性描述",
                    },
                    "reason": None,
                },
            },
            "consistency": consistency,
            "consistency_basis": {
                "agree_count": 1,
                "conflict": conflict,
                "low_confidence_channels": [],
            },
            "needs_review": bool(degraded or consistency == "low"),
            "degraded": degraded,
            "threshold_profile": "default@v1",
            "started_at": "2026-01-01T10:00:00+08:00",
            "finished_at": "2026-01-01T10:00:01+08:00",
            "latency_ms": 4,
        },
        ensure_ascii=False,
    )


def _add_session(
    db_factory,
    *,
    kind: str = "report",
    day: Optional[date] = None,
    hour: int = 12,
    status: str = "captured",
    analysis_status: str = "done",
    analysis: Optional[str] = None,
    subject_id: str = _SUBJECT_ID,
) -> str:
    session_id = str(uuid4())
    captured_day = day or _today()
    captured_at = datetime.combine(captured_day, time(hour), tzinfo=_TZ)
    with db_factory() as db:
        db.add(
            CaptureSession(
                id=session_id,
                subject_id=subject_id,
                kind=kind,
                status=status,
                capture_status="ok",
                captured_at=_iso(captured_at),
                analysis_status=analysis_status,
                analysis_json=analysis,
                codes="[]",
                created_at=_iso(captured_at - timedelta(minutes=2)),
                updated_at=_iso(captured_at),
            )
        )
        db.commit()
    return session_id


def _add_review(
    db_factory,
    *,
    day: date,
    color: str = "yellow",
    rules: Optional[list[str]] = None,
    consistency: str = "medium",
    manual_review: bool = False,
    evidence: Optional[list[dict]] = None,
    subject_id: str = _SUBJECT_ID,
) -> str:
    review_id = str(uuid4())
    with db_factory() as db:
        db.add(
            Review(
                id=review_id,
                subject_id=subject_id,
                source_session_id=None,
                window_start=(day - timedelta(days=6)).isoformat(),
                window_end=day.isoformat(),
                window_days=7,
                single_session_risk="none",
                trend_color=color if color in {"green", "blue", "yellow"} else "green",
                final_color=color,
                consistency=consistency,
                manual_review=1 if manual_review else 0,
                rules_fired=json.dumps(rules or []),
                evidence_json=json.dumps(
                    evidence if evidence is not None else [{"rule_id": "R_X"}]
                ),
                grading_version="grading@1.2",
                created_at=_iso(
                    datetime.combine(day, time(21), tzinfo=_TZ)
                ),
            )
        )
        db.commit()
    return review_id


def _trends(client, admin_headers, *, start_date=None, end_date=None, subject_id=_SUBJECT_ID):
    params = {}
    if start_date is not None:
        params["start_date"] = start_date
    if end_date is not None:
        params["end_date"] = end_date
    response = client.get(
        f"/api/admin/subjects/{subject_id}/trends",
        params=params,
        headers=admin_headers,
    )
    assert response.status_code == 200
    return response.json()


def _day(body: dict, day: date) -> dict:
    for item in body["data"]["days"]:
        if item["date"] == day.isoformat():
            return item
    raise AssertionError(f"day {day} not in response")


def test_default_range_returns_14_days_with_empty_metrics(
    client, db_factory, admin_headers
):
    _add_subject(db_factory)
    body = _trends(client, admin_headers)
    assert body["code"] == 0
    data = body["data"]
    today = _today()
    assert data["start_date"] == (today - timedelta(days=13)).isoformat()
    assert data["end_date"] == today.isoformat()
    assert len(data["days"]) == 14
    assert [item["date"] for item in data["days"]] == sorted(
        item["date"] for item in data["days"]
    )
    for item in data["days"]:
        assert item["review"] is None
        assert item["analysis_risk_level"] is None
        assert item["sessions"] == {
            "total": 0,
            "checkin": 0,
            "report": 0,
            "analyzed": 0,
            "failed": 0,
        }
        assert item["text_valence"] == {"mean": None, "std": None, "count": 0}
        assert item["text_signal"] == {"mean": None, "std": None, "count": 0}
        assert item["consistency"] == {"degraded": 0, "low": 0, "conflict": 0}
        assert item["behavior"] == {
            "checkin": {"expected": False, "completed": False, "overdue": False},
            "report": {"expected": False, "completed": False, "overdue": False},
        }
    assert data["interval_days"] == {"checkin": 1, "report": 3}
    assert data["scatter_points"] == []
    assert data["summary"]["analyzed_count"] == 0
    assert data["summary"]["avg_valence"] is None
    assert data["summary"]["coverage_rate"] == 0
    assert data["summary"]["signals"] == ["insufficient_data"]
    assert data["degraded"] == []
    assert body["degraded"] == []
    with db_factory() as db:
        assert db.scalars(select(AuditLog)).all() == []


def test_only_start_date_keeps_14_day_window(client, db_factory, admin_headers):
    _add_subject(db_factory)
    body = _trends(client, admin_headers, start_date="2025-01-01")
    assert body["code"] == 0
    assert body["data"]["start_date"] == "2025-01-01"
    assert body["data"]["end_date"] == "2025-01-14"
    assert len(body["data"]["days"]) == 14


def test_only_end_date_keeps_14_day_window(client, db_factory, admin_headers):
    _add_subject(db_factory)
    body = _trends(client, admin_headers, end_date="2025-02-10")
    assert body["code"] == 0
    assert body["data"]["start_date"] == "2025-01-28"
    assert body["data"]["end_date"] == "2025-02-10"


def test_invalid_parameters(client, db_factory, admin_headers):
    _add_subject(db_factory)
    invalid = _trends(client, admin_headers, start_date="2025/01/01")
    assert invalid["code"] == 1001
    assert invalid["message"] == "invalid_date"

    reversed_range = _trends(
        client, admin_headers, start_date="2025-02-01", end_date="2025-01-01"
    )
    assert reversed_range["code"] == 1001
    assert reversed_range["message"] == "invalid_date_range"

    too_large = _trends(
        client,
        admin_headers,
        start_date="2025-01-01",
        end_date=(date(2025, 1, 1) + timedelta(days=366)).isoformat(),
    )
    assert too_large["code"] == 1001
    assert too_large["message"] == "date_range_too_large"

    max_allowed = _trends(
        client,
        admin_headers,
        start_date="2025-01-01",
        end_date=(date(2025, 1, 1) + timedelta(days=365)).isoformat(),
    )
    assert max_allowed["code"] == 0
    assert len(max_allowed["data"]["days"]) == 366


def test_unknown_subject_returns_not_found(client, admin_headers):
    body = _trends(client, admin_headers, subject_id=str(uuid4()))
    assert body["code"] == 1004
    assert body["message"] == "not_found"


def test_text_stats_mean_and_sample_stdev(client, db_factory, admin_headers):
    _add_subject(db_factory)
    today = _today()
    _add_session(
        db_factory,
        day=today,
        hour=10,
        analysis=_analysis(str(uuid4()), valence=-0.4, signal=40.0),
    )
    _add_session(
        db_factory,
        day=today,
        hour=18,
        analysis=_analysis(str(uuid4()), valence=0.2, signal=60.0),
    )
    item = _day(_trends(client, admin_headers), today)
    assert item["text_valence"]["mean"] == pytest.approx(-0.1)
    assert item["text_valence"]["std"] == pytest.approx(
        round(statistics.stdev([-0.4, 0.2]), 4)
    )
    assert item["text_valence"]["count"] == 2
    assert item["text_signal"]["mean"] == pytest.approx(50.0)
    assert item["text_signal"]["std"] == pytest.approx(
        round(statistics.stdev([40.0, 60.0]), 4)
    )
    assert item["sessions"] == {
        "total": 2,
        "checkin": 0,
        "report": 2,
        "analyzed": 2,
        "failed": 0,
    }


def test_single_report_has_null_std(client, db_factory, admin_headers):
    _add_subject(db_factory)
    today = _today()
    _add_session(
        db_factory,
        day=today,
        analysis=_analysis(str(uuid4()), valence=-0.3, signal=55.0, risk="elevated"),
    )
    item = _day(_trends(client, admin_headers), today)
    assert item["text_valence"] == {"mean": -0.3, "std": None, "count": 1}
    assert item["text_signal"] == {"mean": 55.0, "std": None, "count": 1}
    assert item["analysis_risk_level"] == "elevated"


def test_checkin_excluded_from_text_stats(client, db_factory, admin_headers):
    _add_subject(db_factory)
    today = _today()
    _add_session(
        db_factory,
        kind="checkin",
        day=today,
        hour=9,
        analysis=_analysis(str(uuid4()), valence=0.9, signal=99.0),
    )
    _add_session(
        db_factory,
        day=today,
        hour=19,
        analysis=_analysis(str(uuid4()), valence=-0.2, signal=45.0),
    )
    item = _day(_trends(client, admin_headers), today)
    assert item["text_valence"] == {"mean": -0.2, "std": None, "count": 1}
    assert item["text_signal"] == {"mean": 45.0, "std": None, "count": 1}
    assert item["sessions"]["checkin"] == 1
    assert item["sessions"]["report"] == 1
    assert item["sessions"]["analyzed"] == 2


def test_consistency_counters(client, db_factory, admin_headers):
    _add_subject(db_factory)
    today = _today()
    _add_session(
        db_factory,
        day=today,
        hour=8,
        analysis_status="degraded",
        analysis=_analysis(str(uuid4()), consistency="medium", degraded=True),
    )
    _add_session(
        db_factory,
        day=today,
        hour=12,
        analysis=_analysis(str(uuid4()), consistency="low", conflict=False),
    )
    _add_session(
        db_factory,
        day=today,
        hour=16,
        analysis=_analysis(str(uuid4()), consistency="medium", conflict=True),
    )
    item = _day(_trends(client, admin_headers), today)
    assert item["consistency"] == {"degraded": 1, "low": 1, "conflict": 1}
    assert item["sessions"]["analyzed"] == 3


def test_analysis_risk_level_takes_highest(client, db_factory, admin_headers):
    _add_subject(db_factory)
    today = _today()
    _add_session(
        db_factory, day=today, hour=8, analysis=_analysis(str(uuid4()), risk="none")
    )
    _add_session(
        db_factory,
        day=today,
        hour=12,
        analysis=_analysis(str(uuid4()), risk="elevated"),
    )
    _add_session(
        db_factory,
        day=today,
        hour=16,
        analysis=_analysis(str(uuid4()), risk="high"),
    )
    body = _trends(client, admin_headers)
    assert _day(body, today)["analysis_risk_level"] == "high"
    assert _day(body, today - timedelta(days=1))["analysis_risk_level"] is None


def test_behavior_overdue_backtracks_from_latest_completed_day(
    client, db_factory, admin_headers
):
    _add_subject(db_factory, checkin_interval_days=1, report_interval_days=3)
    today = _today()
    _add_session(db_factory, kind="checkin", day=today, hour=9)
    _add_session(db_factory, day=today, hour=19)
    _add_session(db_factory, day=today - timedelta(days=3), hour=19)

    body = _trends(client, admin_headers)
    # checkin 频率 1 天：每天都应完成，昨天与前天缺失 → 逾期。
    for offset in (1, 2):
        missing_day = _day(body, today - timedelta(days=offset))
        assert missing_day["behavior"]["checkin"] == {
            "expected": True,
            "completed": False,
            "overdue": True,
        }
    # report 频率 3 天：从今天回溯 3 天是期望日，且该日已完成。
    three_days_ago = _day(body, today - timedelta(days=3))
    assert three_days_ago["behavior"]["report"] == {
        "expected": True,
        "completed": True,
        "overdue": False,
    }
    # 6 天前同为期望日但未完成 → 逾期（历史回溯口径）。
    six_days_ago = _day(body, today - timedelta(days=6))
    assert six_days_ago["behavior"]["report"] == {
        "expected": True,
        "completed": False,
        "overdue": True,
    }
    assert "behavior_overdue_frequent" in body["data"]["summary"]["signals"]


def test_scatter_points_link_same_day_review(client, db_factory, admin_headers):
    _add_subject(db_factory)
    today = _today()
    session_id = _add_session(
        db_factory,
        day=today,
        analysis=_analysis(str(uuid4()), valence=-0.42, signal=41.2, arousal=0.36),
    )
    review_id = _add_review(
        db_factory,
        day=today,
        color="yellow",
        rules=["R_TREND_YELLOW"],
        consistency="medium",
    )
    body = _trends(client, admin_headers)
    points = body["data"]["scatter_points"]
    assert len(points) == 1
    point = points[0]
    assert point["session_id"] == session_id
    assert point["date"] == today.isoformat()
    assert point["kind"] == "report"
    assert point["valence"] == pytest.approx(-0.42)
    assert point["signal"] == pytest.approx(41.2)
    assert point["arousal"] == pytest.approx(0.36)
    assert point["emotion_label"] == "neutral"
    assert point["review_color"] == "yellow"
    assert point["review_rules"] == ["R_TREND_YELLOW"]
    assert point["review_id"] == review_id

    day_review = _day(body, today)["review"]
    assert day_review == {
        "color": "yellow",
        "review_id": review_id,
        "rules_fired": ["R_TREND_YELLOW"],
        "consistency": "medium",
        "manual_review": False,
        "evidence_available": True,
    }

    yesterday = _day(body, today - timedelta(days=1))
    assert yesterday["review"] is None


def test_scatter_arousal_null_when_emotion_unavailable(
    client, db_factory, admin_headers
):
    _add_subject(db_factory)
    today = _today()
    _add_session(
        db_factory,
        day=today,
        hour=10,
        analysis=_analysis(str(uuid4()), emotion=False),
    )
    _add_session(
        db_factory,
        day=today,
        hour=18,
        analysis=_analysis(str(uuid4()), arousal=0.72),
    )
    points = _trends(client, admin_headers)["data"]["scatter_points"]
    assert len(points) == 2
    # 一条 emotion 通道不可用 → null；另一条为 0.72。
    assert any(point["arousal"] is None for point in points)
    assert any(point["arousal"] == pytest.approx(0.72) for point in points)


def test_response_never_leaks_sensitive_paths(client, db_factory, admin_headers):
    _add_subject(db_factory)
    today = _today()
    _add_session(
        db_factory,
        day=today,
        analysis=_analysis(str(uuid4()), valence=-0.2, signal=44.0),
    )
    response = client.get(
        f"/api/admin/subjects/{_SUBJECT_ID}/trends", headers=admin_headers
    )
    text = response.text
    for forbidden in ("transcript_path", "audio_path", "face_path", "suicide_intent"):
        assert forbidden not in text
    body = response.json()
    assert body["data"]["degraded"] == []
    assert body["degraded"] == []


def test_cross_subject_isolation(client, db_factory, admin_headers):
    _add_subject(db_factory)
    _add_subject(db_factory, subject_id=_OTHER_ID, code="S002")
    today = _today()
    own_session = _add_session(
        db_factory,
        day=today,
        analysis=_analysis(str(uuid4()), valence=-0.2, signal=40.0),
    )
    _add_session(
        db_factory,
        day=today,
        hour=18,
        subject_id=_OTHER_ID,
        analysis=_analysis(str(uuid4()), valence=0.8, signal=90.0),
    )
    _add_review(db_factory, day=today, color="green", subject_id=_OTHER_ID)

    body = _trends(client, admin_headers)
    data = body["data"]
    assert [point["session_id"] for point in data["scatter_points"]] == [
        own_session
    ]
    assert [point["valence"] for point in data["scatter_points"]] == pytest.approx(
        [-0.2]
    )
    item = _day(body, today)
    assert item["sessions"]["total"] == 1
    assert item["review"] is None
    assert item["analysis_risk_level"] == "none"
