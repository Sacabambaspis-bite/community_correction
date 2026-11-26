"""删除已废弃的 ``sensevoice_syncs`` 表。

「思想汇报同步」模块已整体下线，历史迁移
``202611251200_add_sensevoice_syncs.py`` 一并移除；本迁移负责把存量库中的
该表与其索引清理干净。可重复执行（``DROP TABLE IF EXISTS``）。
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
        connection.exec_driver_sql("DROP TABLE IF EXISTS sensevoice_syncs")


if __name__ == "__main__":
    upgrade()
