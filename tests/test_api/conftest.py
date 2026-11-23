"""确保从仓库根导入 `app`，并为 API 测试提供临时 SQLite 与依赖覆盖。"""

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app.api import deps
from app.api.deps import get_db
from app.api.main import app
from app.db.database import Base


def _enable_sqlite_foreign_keys(engine) -> None:
    """测试库与生产引擎一致：每条连接打开外键约束。"""

    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_connection, _connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


@pytest.fixture(autouse=True)
def _fake_capture(monkeypatch):
    """默认走假采集，避免测试触达真实摄像头。"""
    monkeypatch.setenv("CAPTURE_FAKE", "1")


@pytest.fixture()
def db_factory(tmp_path):
    """每个测试一个临时库，避免触碰到 storage/app.db。"""
    engine = create_engine(f"sqlite:///{(tmp_path / 'test.db').as_posix()}")
    _enable_sqlite_foreign_keys(engine)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    try:
        yield factory
    finally:
        engine.dispose()


@pytest.fixture()
def client(db_factory):
    def override_get_db():
        db = db_factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()


@pytest.fixture()
def user_headers():
    return {"Authorization": f"Bearer {deps.USER_TOKEN}"}


@pytest.fixture()
def admin_headers():
    return {"Authorization": f"Bearer {deps.ADMIN_TOKEN}"}
