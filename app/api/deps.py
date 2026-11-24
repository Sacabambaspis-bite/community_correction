"""鉴权依赖与数据库会话依赖。"""

from __future__ import annotations

import os
from typing import Iterator, Optional

from fastapi import Depends, Header
from sqlalchemy.orm import Session

from app.api.errors import FORBIDDEN, INVALID_REQUEST, UNAUTHENTICATED, BizError
from app.db.database import SessionLocal

_ENV_USER_TOKEN = os.environ.get("USER_TOKEN") or None
_ENV_ADMIN_TOKEN = os.environ.get("ADMIN_TOKEN") or None

#: 本地开发缺省值；`APP_ENV=production` 时禁止使用。
DEMO_USER_TOKEN = "user_demo"
DEMO_ADMIN_TOKEN = "admin_demo"

APP_ENV = (os.environ.get("APP_ENV") or "development").strip().lower()

if APP_ENV == "production":
    _missing = [
        name
        for name, value, demo in (
            ("USER_TOKEN", _ENV_USER_TOKEN, DEMO_USER_TOKEN),
            ("ADMIN_TOKEN", _ENV_ADMIN_TOKEN, DEMO_ADMIN_TOKEN),
        )
        if not value or value == demo
    ]
    if _missing:
        raise RuntimeError(
            "production requires non-demo " + ", ".join(_missing)
        )

USER_TOKEN = _ENV_USER_TOKEN or DEMO_USER_TOKEN
ADMIN_TOKEN = _ENV_ADMIN_TOKEN or DEMO_ADMIN_TOKEN
USER_TOKEN_FROM_ENV = bool(_ENV_USER_TOKEN)
ADMIN_TOKEN_FROM_ENV = bool(_ENV_ADMIN_TOKEN)

ROLE_SUBJECT = "subject"
ROLE_STAFF = "staff"


def get_session_factory():
    """返回数据库会话工厂；后台任务经此获取会话，测试可 monkeypatch 覆盖。"""
    return SessionLocal


def get_db() -> Iterator[Session]:
    """请求级数据库会话：异常回滚，结束必关闭；提交由路由自行负责。"""
    db = SessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def _extract_token(authorization: Optional[str]) -> str:
    if not authorization:
        raise BizError(UNAUTHENTICATED, "unauthenticated")
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer" or not parts[1]:
        raise BizError(UNAUTHENTICATED, "unauthenticated")
    return parts[1]


def _resolve_role(authorization: Optional[str] = Header(default=None)) -> str:
    token = _extract_token(authorization)
    if token == ADMIN_TOKEN:
        return ROLE_STAFF
    if token == USER_TOKEN:
        return ROLE_SUBJECT
    raise BizError(UNAUTHENTICATED, "unauthenticated")


def require_user(role: str = Depends(_resolve_role)) -> str:
    """仅用户端 token（subject）。"""
    if role != ROLE_SUBJECT:
        raise BizError(FORBIDDEN, "forbidden")
    return role


def require_admin(role: str = Depends(_resolve_role)) -> str:
    """仅管理端 token（staff）。"""
    if role != ROLE_STAFF:
        raise BizError(FORBIDDEN, "forbidden")
    return role


def require_any_subject_or_staff(role: str = Depends(_resolve_role)) -> str:
    """用户端或管理端均可。"""
    return role


def enforce_session_owner(session, role: str, subject_id: Optional[str]) -> None:
    """会话归属校验（api.md §7.3 / §7.8）。

    - `staff` 角色跳过；
    - `subject` 角色必须声明 `subject_id`，缺失返回 `1001`，不匹配返回 `1003`。
    """
    if role == ROLE_STAFF:
        return
    if not subject_id:
        raise BizError(INVALID_REQUEST, "invalid_request")
    if session.subject_id != subject_id:
        raise BizError(FORBIDDEN, "forbidden")
