"""双模块数据库默认值、CHECK 与手工迁移测试。"""

from __future__ import annotations

import importlib

import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError

from app.db.models import CaptureSession, Subject

_NOW = "2026-11-24T09:00:00+08:00"
_MIGRATION = importlib.import_module(
    "app.db.migrations.202611241200_add_dual_module_tasks"
)


def _add_subject(db: object, subject_id: str = "subject-dual", **overrides) -> None:
    values = {
        "id": subject_id,
        "code": f"S-{subject_id}",
        "name": "测试对象",
        "created_at": _NOW,
        "updated_at": _NOW,
    }
    values.update(overrides)
    db.add(Subject(**values))


def test_dual_module_defaults_and_kind_index(db_factory):
    with db_factory() as db:
        _add_subject(db)
        db.flush()
        db.add(
            CaptureSession(
                id="session-default-kind",
                subject_id="subject-dual",
                status="created",
                codes="[]",
                created_at=_NOW,
                updated_at=_NOW,
            )
        )
        db.commit()

    with db_factory() as db:
        subject = db.get(Subject, "subject-dual")
        session = db.get(CaptureSession, "session-default-kind")
        assert subject.checkin_interval_days == 1
        assert subject.report_interval_days == 3
        assert session.kind == "report"
        index_names = {
            index["name"]
            for index in inspect(db.get_bind()).get_indexes("sessions")
        }
        assert "ix_sessions_subject_kind_captured_at" in index_names


@pytest.mark.parametrize("field", ["checkin_interval_days", "report_interval_days"])
@pytest.mark.parametrize("value", [0, -1])
def test_subject_interval_check_rejects_values_below_one(
    db_factory, field, value
):
    with db_factory() as db:
        _add_subject(db, **{field: value})
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()


def test_session_kind_check_rejects_unknown_value(db_factory):
    with db_factory() as db:
        _add_subject(db)
        db.flush()
        db.add(
            CaptureSession(
                id="session-invalid-kind",
                subject_id="subject-dual",
                kind="unknown",
                status="created",
                codes="[]",
                created_at=_NOW,
                updated_at=_NOW,
            )
        )
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()


def test_migration_builds_empty_database(tmp_path):
    engine = create_engine(f"sqlite:///{(tmp_path / 'empty.db').as_posix()}")
    try:
        _MIGRATION.upgrade(engine)
        subject_columns = {
            column["name"] for column in inspect(engine).get_columns("subjects")
        }
        session_columns = {
            column["name"] for column in inspect(engine).get_columns("sessions")
        }
        ticket_columns = {
            column["name"]: column
            for column in inspect(engine).get_columns("review_tickets")
        }
        assert {"checkin_interval_days", "report_interval_days"} <= subject_columns
        assert "kind" in session_columns
        assert "detail_json" in ticket_columns
        assert ticket_columns["review_id"]["nullable"] is True
    finally:
        engine.dispose()


def _create_legacy_schema(engine) -> None:
    statements = [
        """
        CREATE TABLE subjects (
            id TEXT PRIMARY KEY,
            code TEXT NOT NULL UNIQUE,
            name TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """,
        """
        CREATE TABLE sessions (
            id TEXT PRIMARY KEY,
            subject_id TEXT NOT NULL REFERENCES subjects(id),
            status TEXT NOT NULL,
            captured_at TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """,
        "CREATE TABLE reviews (id TEXT PRIMARY KEY)",
        """
        CREATE TABLE review_tickets (
            id TEXT PRIMARY KEY,
            review_id TEXT NOT NULL UNIQUE REFERENCES reviews(id),
            subject_id TEXT NOT NULL REFERENCES subjects(id),
            status TEXT NOT NULL,
            priority TEXT NOT NULL,
            due_at TEXT,
            triggered_rules TEXT NOT NULL,
            evidence_json TEXT NOT NULL,
            suggested_method TEXT NOT NULL,
            assignee TEXT,
            conclusion_color TEXT,
            conclusion_note TEXT,
            opened_at TEXT NOT NULL,
            closed_at TEXT
        )
        """,
        """
        INSERT INTO subjects (id, code, name, created_at, updated_at)
        VALUES ('subject-legacy', 'S-LEGACY', '存量对象', :now, :now)
        """,
        """
        INSERT INTO sessions (
            id, subject_id, status, captured_at, created_at, updated_at
        ) VALUES (
            'session-legacy', 'subject-legacy', 'captured', :now, :now, :now
        )
        """,
        "INSERT INTO reviews (id) VALUES ('review-legacy')",
        """
        INSERT INTO review_tickets (
            id, review_id, subject_id, status, priority, triggered_rules,
            evidence_json, suggested_method, opened_at
        ) VALUES (
            'ticket-legacy', 'review-legacy', 'subject-legacy', 'pending', 'P2',
            '[]', '[]', 'routine_checkin', :now
        )
        """,
    ]
    with engine.begin() as connection:
        for statement in statements:
            connection.execute(text(statement), {"now": _NOW})


def test_migration_upgrades_legacy_rows_and_allows_null_review_ids(tmp_path):
    engine = create_engine(f"sqlite:///{(tmp_path / 'legacy.db').as_posix()}")
    try:
        _create_legacy_schema(engine)
        _MIGRATION.upgrade(engine)
        _MIGRATION.upgrade(engine)
        with engine.begin() as connection:
            subject = connection.execute(
                text(
                    """
                    SELECT checkin_interval_days, report_interval_days
                    FROM subjects WHERE id = 'subject-legacy'
                    """
                )
            ).one()
            kind = connection.execute(
                text("SELECT kind FROM sessions WHERE id = 'session-legacy'")
            ).scalar_one()
            preserved = connection.execute(
                text("SELECT COUNT(*) FROM review_tickets WHERE id = 'ticket-legacy'")
            ).scalar_one()
            assert tuple(subject) == (1, 3)
            assert kind == "report"
            assert preserved == 1

            for ticket_id in ("overdue-a", "overdue-b"):
                connection.execute(
                    text(
                        """
                        INSERT INTO review_tickets (
                            id, review_id, subject_id, status, priority,
                            triggered_rules, evidence_json, suggested_method, opened_at
                        ) VALUES (
                            :ticket_id, NULL, 'subject-legacy', 'pending', 'P0',
                            '[]', '[]', 'talk_to_staff', :now
                        )
                        """
                    ),
                    {"ticket_id": ticket_id, "now": _NOW},
                )
    finally:
        engine.dispose()
