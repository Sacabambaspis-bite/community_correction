"""db@1.4 可空 JSON 列与 `sessions.codes` 默认值的回归测试。

本机 SQLite 中 `json_valid(NULL) = 0`，因此可空 JSON 列的 CHECK 必须带 `IS NULL OR`；
`codes` 为状态类列，NOT NULL DEFAULT '[]'。全部使用内存引擎，不碰 storage。
"""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.db.database import Base
from app.db.models import AuditLog, CaptureSession, Subject

_NOW = "2026-11-23T10:00:00+08:00"


@pytest.fixture()
def db_factory():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    try:
        yield factory
    finally:
        engine.dispose()


def test_subject_allows_null_json_columns(db_factory):
    with db_factory() as db:
        db.add(
            Subject(
                id="subject-1",
                code="S900",
                name="测试对象",
                consent_json=None,
                baseline_json=None,
                created_at=_NOW,
                updated_at=_NOW,
            )
        )
        db.commit()

    with db_factory() as db:
        subject = db.get(Subject, "subject-1")
        assert subject.consent_json is None
        assert subject.baseline_json is None


def test_session_allows_null_analysis_json_and_defaults_codes(db_factory):
    with db_factory() as db:
        db.add(
            Subject(
                id="subject-2",
                code="S901",
                name="测试对象",
                created_at=_NOW,
                updated_at=_NOW,
            )
        )
        db.add(
            CaptureSession(
                id="session-1",
                subject_id="subject-2",
                status="created",
                analysis_json=None,
                created_at=_NOW,
                updated_at=_NOW,
            )
        )
        db.commit()

    with db_factory() as db:
        session = db.get(CaptureSession, "session-1")
        assert session.analysis_json is None
        assert session.codes == "[]"
        assert session.analysis_status == "pending"


def test_audit_log_allows_null_detail_json(db_factory):
    with db_factory() as db:
        db.add(
            AuditLog(
                actor_type="system",
                action="session.analyze",
                detail_json=None,
                created_at=_NOW,
            )
        )
        db.commit()

    with db_factory() as db:
        log = db.scalars(select(AuditLog)).one()
        assert log.detail_json is None
