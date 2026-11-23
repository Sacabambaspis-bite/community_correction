"""db@1.4 约束负例：外键、UNIQUE、CHECK（测试库已开 `PRAGMA foreign_keys=ON`）。"""

from __future__ import annotations

import pytest
from sqlalchemy.exc import IntegrityError

from app.db.models import CaptureSession, Subject

_NOW = "2026-11-24T09:00:00+08:00"


def test_session_requires_existing_subject(db_factory):
    with db_factory() as db:
        db.add(
            CaptureSession(
                id="session-orphan",
                subject_id="missing-subject",
                status="created",
                # 显式给 codes，避免 ORM 用 RETURNING 取 server_default，
                # 2.1.9 下该路径会把外键错误包装成 OperationalError。
                codes="[]",
                created_at=_NOW,
                updated_at=_NOW,
            )
        )
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()

    with db_factory() as db:
        assert db.get(CaptureSession, "session-orphan") is None


def test_subject_code_is_unique(db_factory):
    with db_factory() as db:
        db.add(
            Subject(
                id="subject-a",
                code="S920",
                name="A",
                created_at=_NOW,
                updated_at=_NOW,
            )
        )
        db.flush()
        db.add(
            Subject(
                id="subject-b",
                code="S920",
                name="B",
                created_at=_NOW,
                updated_at=_NOW,
            )
        )
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()

    with db_factory() as db:
        assert db.get(Subject, "subject-b") is None


def test_subject_status_check(db_factory):
    with db_factory() as db:
        db.add(
            Subject(
                id="subject-c",
                code="S921",
                name="C",
                status="bogus",
                created_at=_NOW,
                updated_at=_NOW,
            )
        )
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()

    with db_factory() as db:
        assert db.get(Subject, "subject-c") is None
