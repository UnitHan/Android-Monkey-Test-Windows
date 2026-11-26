"""RFC 9457 problem+json responses. The only place errors become HTTP."""

from __future__ import annotations

import traceback
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from starlette.exceptions import HTTPException as StarletteHTTPException

from monkey_api.core.errors import AppError
from monkey_api.core.logging import log, request_id_var

PROBLEM_JSON = "application/problem+json"


class Problem(BaseModel):
    type: str = "about:blank"
    title: str
    status: int
    code: str
    detail: str
    request_id: str | None = None
    extra: dict[str, Any] | None = None
    errors: list[dict[str, Any]] | None = None


def problem_response(problem: Problem) -> JSONResponse:
    return JSONResponse(problem.model_dump(exclude_none=True), status_code=problem.status, media_type=PROBLEM_JSON)


async def _app_error(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, AppError)
    level = "ERROR" if exc.status >= 500 else "WARNING"
    log("http", f"{exc.code}: {exc.detail}", level, code=exc.code, status=exc.status, **exc.extra)
    return problem_response(
        Problem(
            title=exc.title,
            status=exc.status,
            code=exc.code,
            detail=exc.detail,
            request_id=request_id_var.get(),
            extra=exc.extra or None,
        )
    )


async def _validation_error(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, RequestValidationError)
    errors = [
        {"loc": list(e.get("loc", ())), "msg": str(e.get("msg", "")), "type": str(e.get("type", ""))}
        for e in exc.errors()
    ]
    log("http", "request validation failed", "WARNING", errors=errors)
    return problem_response(
        Problem(
            title="Unprocessable Content",
            status=422,
            code="validation_failed",
            detail="request validation failed",
            request_id=request_id_var.get(),
            errors=errors,
        )
    )


async def _http_error(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, StarletteHTTPException)
    code = "not_found" if exc.status_code == 404 else f"http_{exc.status_code}"
    return problem_response(
        Problem(
            title=str(exc.detail),
            status=exc.status_code,
            code=code,
            detail=str(exc.detail),
            request_id=request_id_var.get(),
        )
    )


def unhandled_response(exc: Exception) -> JSONResponse:
    """Called by RequestContextMiddleware so request_id is still bound."""
    log(
        "http",
        f"unhandled {type(exc).__name__}: {exc}",
        "ERROR",
        trace="".join(traceback.format_exception(exc))[-3000:],
    )
    return problem_response(
        Problem(
            title="Internal Server Error",
            status=500,
            code="internal_error",
            detail=f"{type(exc).__name__}: {exc}",
            request_id=request_id_var.get(),
        )
    )


def install_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AppError, _app_error)
    app.add_exception_handler(RequestValidationError, _validation_error)
    app.add_exception_handler(StarletteHTTPException, _http_error)


def problem_responses(*statuses: int) -> dict[int | str, dict[str, Any]]:
    """OpenAPI `responses=` entry documenting problem+json for the given statuses."""
    return {s: {"model": Problem, "content": {PROBLEM_JSON: {}}} for s in statuses}
