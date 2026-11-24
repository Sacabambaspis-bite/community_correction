"""FastAPI 应用工厂与模块级 `app`。"""

from __future__ import annotations

import logging
import uuid

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.api import deps
from app.api.errors import register_exception_handlers, request_id_var
from app.api.routers import admin, health, sessions, user

logger = logging.getLogger("app.api")

_ALLOWED_ORIGINS = ["http://127.0.0.1:5173"]


def _register_request_id_middleware(app: FastAPI) -> None:
    @app.middleware("http")
    async def request_id_middleware(request: Request, call_next):
        rid = str(uuid.uuid4())
        request.state.request_id = rid
        token = request_id_var.set(rid)
        try:
            response = await call_next(request)
            response.headers["X-Request-Id"] = rid
            logger.info(
                "api.request request_id=%s method=%s path=%s status=%s",
                rid,
                request.method,
                request.url.path,
                response.status_code,
            )
            return response
        finally:
            request_id_var.reset(token)


def create_app() -> FastAPI:
    if not deps.USER_TOKEN_FROM_ENV:
        logger.warning("USER_TOKEN not set; using local demo token")
    if not deps.ADMIN_TOKEN_FROM_ENV:
        logger.warning("ADMIN_TOKEN not set; using local demo token")

    app = FastAPI(title="community-correction API", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Request-Id"],
    )
    register_exception_handlers(app)
    _register_request_id_middleware(app)
    app.include_router(health.router)
    app.include_router(sessions.router)
    app.include_router(admin.router)
    app.include_router(user.router)
    return app


app = create_app()
