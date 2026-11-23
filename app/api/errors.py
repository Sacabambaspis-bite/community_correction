"""统一响应信封与业务错误处理。

所有业务响应（含可预期错误）HTTP 恒为 200；未捕获异常返回 HTTP 500 + `code=5000`。
唯一不走 JSON 信封的成功响应是面部图接口的 `image/jpeg` 二进制。
"""

from __future__ import annotations

import logging
from contextvars import ContextVar
from typing import Any, Optional

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger("app.api")

#: 当前请求 id；由中间件写入，供信封与审计留痕读取。
request_id_var: ContextVar[str] = ContextVar("request_id", default="")

# ---- 业务码（api.md §3）----
OK = 0
INVALID_REQUEST = 1001
UNAUTHENTICATED = 1002
FORBIDDEN = 1003
NOT_FOUND = 1004
STATE_CONFLICT = 1005
RATE_LIMITED = 1006
CAPTURE_FAILED = 2001
ANALYSIS_FAILED = 2003
SESSION_NOT_CAPTURED = 4000
INTERNAL_ERROR = 5000


class BizError(Exception):
    """可预期的业务错误，由异常处理器转为 HTTP 200 的信封。"""

    def __init__(self, code: int, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def current_request_id() -> str:
    """返回当前请求 id；不在请求上下文中时为空串。"""
    return request_id_var.get()


def envelope(
    code: int = 0,
    message: str = "ok",
    data: Any = None,
    degraded: Optional[list[str]] = None,
    request_id: Optional[str] = None,
) -> dict[str, Any]:
    """构造统一响应体；`degraded` 固定为数组，`request_id` 缺省取 contextvar。"""
    return {
        "code": code,
        "message": message,
        "data": data,
        "degraded": [] if degraded is None else degraded,
        "request_id": current_request_id() if request_id is None else request_id,
    }


def _safe_exc_summary(exc: Exception) -> str:
    """异常摘要：避免把文件路径等敏感信息写进日志。"""
    if isinstance(exc, OSError):
        return ""
    return " ".join(str(exc).split())[:120]


async def _biz_error_handler(request: Request, exc: BizError) -> JSONResponse:
    return JSONResponse(
        status_code=200,
        content=envelope(code=exc.code, message=exc.message),
    )


async def _validation_error_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    return JSONResponse(
        status_code=200,
        content=envelope(code=INVALID_REQUEST, message="invalid_request"),
    )


async def _http_error_handler(
    request: Request, exc: StarletteHTTPException
) -> JSONResponse:
    if exc.status_code == 404:
        return JSONResponse(
            status_code=200,
            content=envelope(code=NOT_FOUND, message="not_found"),
        )
    return JSONResponse(
        status_code=200,
        content=envelope(code=INVALID_REQUEST, message="invalid_request"),
    )


async def _unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
    # 未捕获异常由 Starlette ServerErrorMiddleware 在外层处理，
    # 此时中间件的 contextvar 已 reset，只能从 request.state 取 request_id。
    rid = getattr(request.state, "request_id", "")
    logger.error(
        "api.unhandled_exception request_id=%s type=%s msg=%s",
        rid,
        type(exc).__name__,
        _safe_exc_summary(exc),
    )
    return JSONResponse(
        status_code=500,
        headers={"X-Request-Id": rid},
        content=envelope(
            code=INTERNAL_ERROR,
            message="internal_error",
            request_id=rid,
        ),
    )


def register_exception_handlers(app: FastAPI) -> None:
    """注册业务错误、参数校验、HTTP 404 与兜底异常的统一处理器。"""
    app.add_exception_handler(BizError, _biz_error_handler)
    app.add_exception_handler(RequestValidationError, _validation_error_handler)
    app.add_exception_handler(StarletteHTTPException, _http_error_handler)
    app.add_exception_handler(Exception, _unhandled_error_handler)
