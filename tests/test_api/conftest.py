"""确保从仓库根导入 `app`，并为 API 测试提供临时 SQLite 与依赖覆盖。"""

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api import deps
from app.api.deps import get_db
from app.api.main import app
from app.db.database import Base


@pytest.fixture()
def db_factory(tmp_path):
    """每个测试一个临时库，避免触碰到 storage/app.db。"""
    engine = create_engine(f"sqlite:///{(tmp_path / 'test.db').as_posix()}")
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
