"""建库入口：`python -m app.db.init`。

只创建六张业务表（subjects / sessions / reviews / review_tickets / audit_logs /
sensevoice_syncs），不插入任何演示数据；幂等，重复执行不报错。
"""

from __future__ import annotations

from sqlalchemy import inspect

from app.db import database
from app.db import models  # noqa: F401  导入以确保模型注册到 Base.metadata


def _existing_tables() -> set[str]:
    return set(inspect(database.engine).get_table_names())


def _expected_tables() -> list[str]:
    return sorted(database.Base.metadata.tables)


def init_db() -> None:
    """建目录并创建全部表，打印数据库绝对路径与逐表状态。"""
    db_file = database.DB_PATH.resolve()
    db_file.parent.mkdir(parents=True, exist_ok=True)

    before = _existing_tables() if db_file.exists() else set()
    database.Base.metadata.create_all(database.engine)
    after = _existing_tables()

    print(f"[app.db.init] database={db_file}")
    for name in _expected_tables():
        if name not in after:
            raise RuntimeError(f"table not created: {name}")
        state = "exists" if name in before else "created"
        print(f"[app.db.init] table {name}: {state}")


if __name__ == "__main__":
    init_db()
