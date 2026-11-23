"""确保从仓库根导入 `app`，并提供开启外键约束的内存库 fixture。

pytest 默认把测试文件所在目录加入 sys.path，这里显式补上仓库根，
使 `pytest tests/test_db/ -q` 在任意工作目录下都能 import app。
"""

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app.db.database import Base


def enable_sqlite_foreign_keys(engine) -> None:
    """与生产引擎一致：每条 SQLite 连接打开外键约束。"""

    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_connection, _connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


@pytest.fixture()
def db_factory():
    """内存库：开外键、建全表，测试结束释放引擎。"""
    engine = create_engine("sqlite://")
    enable_sqlite_foreign_keys(engine)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    try:
        yield factory
    finally:
        engine.dispose()
