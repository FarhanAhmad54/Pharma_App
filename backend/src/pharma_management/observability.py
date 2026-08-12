from __future__ import annotations

import logging
import time
import uuid
from collections.abc import Callable

from fastapi import HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from starlette.middleware.base import BaseHTTPMiddleware


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable):
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        request.state.request_id = request_id
        started = time.perf_counter()
        logger = logging.getLogger("pharma.api")
        try:
            response = await call_next(request)
        except Exception:
            duration_ms = round((time.perf_counter() - started) * 1000, 2)
            logger.exception(
                "request_failed",
                extra={
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.url.path,
                    "duration_ms": duration_ms,
                },
            )
            raise
        duration_ms = round((time.perf_counter() - started) * 1000, 2)
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Process-Time-Ms"] = str(duration_ms)
        logger.info(
            "request_complete",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "duration_ms": duration_ms,
            },
        )
        return response


def request_id(request: Request) -> str:
    return getattr(request.state, "request_id", "unknown")


def install_exception_handlers(app) -> None:
    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {
                    "code": f"HTTP_{exc.status_code}",
                    "message": exc.detail if isinstance(exc.detail, str) else "Request failed",
                    "details": exc.detail if not isinstance(exc.detail, str) else None,
                    "request_id": request_id(request),
                }
            },
            headers={**(exc.headers or {}), "X-Request-ID": request_id(request)},
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(request: Request, exc: RequestValidationError):
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "One or more request fields are invalid.",
                    "details": exc.errors(),
                    "request_id": request_id(request),
                }
            },
            headers={"X-Request-ID": request_id(request)},
        )

    @app.exception_handler(IntegrityError)
    async def integrity_error_handler(request: Request, _exc: IntegrityError):
        return JSONResponse(
            status_code=409,
            content={
                "error": {
                    "code": "INTEGRITY_CONSTRAINT",
                    "message": "The requested operation conflicts with existing data or a database constraint.",
                    "request_id": request_id(request),
                }
            },
            headers={"X-Request-ID": request_id(request)},
        )

    @app.exception_handler(SQLAlchemyError)
    async def sqlalchemy_error_handler(request: Request, _exc: SQLAlchemyError):
        return JSONResponse(
            status_code=503,
            content={
                "error": {
                    "code": "DATABASE_UNAVAILABLE",
                    "message": "The database operation could not be completed. Retry the request.",
                    "request_id": request_id(request),
                }
            },
            headers={"X-Request-ID": request_id(request)},
        )

    @app.exception_handler(Exception)
    async def unexpected_error_handler(request: Request, _exc: Exception):
        logging.getLogger("pharma.api").exception(
            "unhandled_exception", extra={"request_id": request_id(request)}
        )
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "An unexpected server error occurred.",
                    "request_id": request_id(request),
                }
            },
            headers={"X-Request-ID": request_id(request)},
        )
