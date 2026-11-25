"""思想汇报 SenseVoice 同步表迁移（db@1.5 §7）。

空库按当前 ORM 元数据建全表；存量库只新增 ``sensevoice_syncs`` 表与其索引，
不改动任何既有表，可重复执行。
"""

from __future__ import annotations

from sqlalchemy import inspect

from app.db import database
from app.db import models  # noqa: F401  注册全部 ORM 表
from app.db.database import Base


def upgrade(engine=None) -> None:
    """升级指定引擎；缺省使用应用数据库。"""
    bind = engine or database.engine
    if not inspect(bind).get_table_names():
        Base.metadata.create_all(bind)
        return

    with bind.begin() as connection:
        connection.exec_driver_sql(
            """
            CREATE TABLE IF NOT EXISTS sensevoice_syncs (
                id TEXT PRIMARY KEY,
                subject_id TEXT NOT NULL REFERENCES subjects(id),
                session_id TEXT NOT NULL REFERENCES sessions(id),
                status TEXT NOT NULL DEFAULT 'succeeded',
                provider TEXT NOT NULL DEFAULT 'sensevoice',
                transcript_text TEXT NOT NULL,
                transcript_language TEXT,
                emotion_json TEXT NOT NULL,
                emotion_primary TEXT,
                emotion_confidence REAL,
                data_version TEXT NOT NULL,
                operator TEXT NOT NULL DEFAULT 'staff',
                error_code TEXT,
                error_message TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                CONSTRAINT ck_sensevoice_syncs_status CHECK (
                    status IN ('succeeded','failed')
                ),
                CONSTRAINT ck_sensevoice_syncs_emotion_json CHECK (
                    json_valid(emotion_json)
                ),
                CONSTRAINT ck_sensevoice_syncs_emotion_confidence CHECK (
                    emotion_confidence IS NULL
                    OR (emotion_confidence >= 0 AND emotion_confidence <= 1)
                )
            )
            """
        )
        connection.exec_driver_sql(
            """
            CREATE INDEX IF NOT EXISTS ix_sensevoice_syncs_subject_created_at
            ON sensevoice_syncs (subject_id, created_at DESC)
            """
        )
        connection.exec_driver_sql(
            """
            CREATE INDEX IF NOT EXISTS ix_sensevoice_syncs_session_id
            ON sensevoice_syncs (session_id)
            """
        )


if __name__ == "__main__":
    upgrade()
