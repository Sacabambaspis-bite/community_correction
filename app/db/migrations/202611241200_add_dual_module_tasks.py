"""双模块字段、逾期工单支撑列与索引迁移。

空库直接按当前 ORM 元数据建全表；存量库以非破坏方式补列，并重建
``review_tickets`` 以允许无复盘关联的逾期工单。可重复执行。
"""

from __future__ import annotations

from sqlalchemy import inspect

from app.db import database
from app.db import models  # noqa: F401  注册全部 ORM 表
from app.db.database import Base


def _columns(connection, table_name: str) -> dict[str, dict]:
    return {
        column["name"]: column
        for column in inspect(connection).get_columns(table_name)
    }


def _rebuild_review_tickets(connection, existing_columns: dict[str, dict]) -> None:
    """SQLite 通过建表、拷贝、换名调整 NULL 与状态 CHECK 约束。"""
    detail_select = "detail_json" if "detail_json" in existing_columns else "NULL"
    connection.exec_driver_sql(
        "ALTER TABLE review_tickets RENAME TO review_tickets_legacy"
    )
    connection.exec_driver_sql(
        """
        CREATE TABLE review_tickets (
            id TEXT PRIMARY KEY,
            review_id TEXT REFERENCES reviews(id),
            subject_id TEXT NOT NULL REFERENCES subjects(id),
            status TEXT NOT NULL,
            priority TEXT NOT NULL,
            due_at TEXT,
            triggered_rules TEXT NOT NULL,
            evidence_json TEXT NOT NULL,
            detail_json TEXT,
            suggested_method TEXT NOT NULL,
            assignee TEXT,
            conclusion_color TEXT,
            conclusion_note TEXT,
            opened_at TEXT NOT NULL,
            closed_at TEXT,
            CONSTRAINT uq_review_tickets_review_id UNIQUE (review_id),
            CONSTRAINT ck_review_tickets_status CHECK (
                status IN ('pending','confirmed','corrected','closed')
            ),
            CONSTRAINT ck_review_tickets_priority CHECK (priority IN ('P0','P1','P2')),
            CONSTRAINT ck_review_tickets_conclusion_color CHECK (
                conclusion_color IN ('green','blue','yellow','orange','red')
            ),
            CONSTRAINT ck_review_tickets_triggered_rules CHECK (
                json_valid(triggered_rules)
            ),
            CONSTRAINT ck_review_tickets_evidence_json CHECK (json_valid(evidence_json)),
            CONSTRAINT ck_review_tickets_detail_json CHECK (
                detail_json IS NULL OR json_valid(detail_json)
            )
        )
        """
    )
    connection.exec_driver_sql(
        f"""
        INSERT INTO review_tickets (
            id, review_id, subject_id, status, priority, due_at,
            triggered_rules, evidence_json, detail_json, suggested_method,
            assignee, conclusion_color, conclusion_note, opened_at, closed_at
        )
        SELECT
            id, review_id, subject_id,
            CASE WHEN status = 'open' THEN 'pending' ELSE status END,
            priority, due_at,
            triggered_rules, evidence_json, {detail_select}, suggested_method,
            assignee, conclusion_color, conclusion_note, opened_at, closed_at
        FROM review_tickets_legacy
        """
    )
    connection.exec_driver_sql("DROP TABLE review_tickets_legacy")
    connection.exec_driver_sql(
        """
        CREATE INDEX ix_review_tickets_status_priority_opened_at
        ON review_tickets (status, priority, opened_at DESC)
        """
    )
    connection.exec_driver_sql(
        "CREATE INDEX ix_review_tickets_subject_id ON review_tickets (subject_id)"
    )


def upgrade(engine=None) -> None:
    """升级指定引擎；缺省使用应用数据库。"""
    bind = engine or database.engine
    if not inspect(bind).get_table_names():
        Base.metadata.create_all(bind)
        return

    with bind.begin() as connection:
        subject_columns = _columns(connection, "subjects")
        if "checkin_interval_days" not in subject_columns:
            connection.exec_driver_sql(
                """
                ALTER TABLE subjects ADD COLUMN checkin_interval_days INTEGER
                NOT NULL DEFAULT 1 CHECK (checkin_interval_days >= 1)
                """
            )
        if "report_interval_days" not in subject_columns:
            connection.exec_driver_sql(
                """
                ALTER TABLE subjects ADD COLUMN report_interval_days INTEGER
                NOT NULL DEFAULT 3 CHECK (report_interval_days >= 1)
                """
            )

        session_columns = _columns(connection, "sessions")
        if "kind" not in session_columns:
            connection.exec_driver_sql(
                """
                ALTER TABLE sessions ADD COLUMN kind TEXT NOT NULL DEFAULT 'report'
                CHECK (kind IN ('checkin','report'))
                """
            )
        connection.exec_driver_sql(
            """
            CREATE INDEX IF NOT EXISTS ix_sessions_subject_kind_captured_at
            ON sessions (subject_id, kind, captured_at DESC)
            """
        )

        ticket_columns = _columns(connection, "review_tickets")
        table_sql = connection.exec_driver_sql(
            """
            SELECT sql FROM sqlite_master
            WHERE type = 'table' AND name = 'review_tickets'
            """
        ).scalar_one_or_none()
        review_id = ticket_columns["review_id"]
        if (
            "detail_json" not in ticket_columns
            or not review_id["nullable"]
            or "'open'" in (table_sql or "")
        ):
            _rebuild_review_tickets(connection, ticket_columns)


if __name__ == "__main__":
    upgrade()
