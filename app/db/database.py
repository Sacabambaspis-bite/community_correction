"""数据库连接与会话工厂。

- 路径：`DB_PATH` 环境变量可覆盖，默认 `{仓库根}/storage/app.db`；
- 引擎：SQLite，连接建立时开启外键约束；
- 不做 FastAPI 依赖注入，调用方自行从 `SessionLocal` 取会话。

导入本模块不会创建数据库文件，也不会建立连接。
"""

from __future__ import annotations

import os
from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker

# 仓库根目录：app/db/database.py -> app/db -> app -> 仓库根
_REPO_ROOT = Path(__file__).resolve().parents[2]


def _resolve_db_path() -> Path:
    """解析数据库文件绝对路径，不创建任何目录或文件。"""
    raw = os.environ.get("DB_PATH")
    if raw:
        candidate = Path(raw).expanduser()
        if not candidate.is_absolute():
            candidate = _REPO_ROOT / candidate
        return candidate
    return _REPO_ROOT / "storage" / "app.db"


DB_PATH = _resolve_db_path()


class Base(DeclarativeBase):
    """所有 ORM 模型的声明式基类。"""


engine = create_engine(f"sqlite:///{DB_PATH.as_posix()}")


@event.listens_for(engine, "connect")
def _enable_sqlite_foreign_keys(dbapi_connection, connection_record) -> None:  # noqa: ANN001
    """SQLite 默认不开启外键，逐连接显式打开。"""
    cursor = dbapi_connection.cursor()
    try:
        cursor.execute("PRAGMA foreign_keys=ON")
    finally:
        cursor.close()


SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
