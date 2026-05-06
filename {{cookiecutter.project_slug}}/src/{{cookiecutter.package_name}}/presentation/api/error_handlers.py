"""Centralised exception → HTTP mapping.

The mapping ``ERROR_HTTP_MAPPING`` is the single source of truth for the HTTP
status code returned for each ``DomainError`` subclass. A test in
``tests/unit/presentation/`` iterates ``DomainError.__subclasses__()`` and
fails if a subclass is missing here.
"""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from opentelemetry import trace

from {{ cookiecutter.package_name }}.domain.exceptions.base import DomainError
from {{ cookiecutter.package_name }}.domain.exceptions.user import UserAlreadyExistsError, UserNotFoundError
from {{ cookiecutter.package_name }}.domain.value_objects.email import InvalidEmailError

logger = structlog.get_logger(__name__)

ERROR_HTTP_MAPPING: dict[type[DomainError], int] = {
    InvalidEmailError: 422,
    UserAlreadyExistsError: status.HTTP_409_CONFLICT,
    UserNotFoundError: status.HTTP_404_NOT_FOUND,
    # Concrete subclasses are added by their owning bounded context.
    # The mapping is checked by tests/unit/presentation/test_error_mapping.py.
}


def _http_status_for(exc: DomainError) -> int:
    return ERROR_HTTP_MAPPING.get(type(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


def _current_trace_id() -> str | None:
    span = trace.get_current_span()
    if span is None:
        return None
    ctx = span.get_span_context()
    if not ctx.is_valid:
        return None
    return f"{ctx.trace_id:032x}"


async def handle_domain_error(request: Request, exc: DomainError) -> JSONResponse:
    """Translate a ``DomainError`` into a structured JSON response."""
    logger.warning(
        "domain_error",
        code=exc.code,
        path=request.url.path,
        context=exc.context,
    )
    return JSONResponse(
        status_code=_http_status_for(exc),
        content={"error": {"code": exc.code, "message": exc.message}},
    )


async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:  # noqa: ARG001
    """Translate any uncaught exception into a 500 with a trace id for support."""
    trace_id = _current_trace_id()
    logger.exception(
        "unexpected_error",
        path=request.url.path,
        trace_id=trace_id,
    )
    payload: dict[str, Any] = {
        "error": {
            "code": "INTERNAL_ERROR",
            "message": "An internal error occurred. Contact support with the trace identifier.",
        }
    }
    if trace_id:
        payload["error"]["trace_id"] = trace_id
    return JSONResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content=payload)


def register_error_handlers(app: FastAPI) -> None:
    """Register the domain and fallback handlers on the FastAPI app."""
    # Starlette's overload set does not include the (Request, Exception) -> JSONResponse
    # signature returned by our async handlers; FastAPI accepts it at runtime via
    # adapter logic, so we intentionally bypass the static check here.
    app.add_exception_handler(DomainError, handle_domain_error)  # ty: ignore[invalid-argument-type]
    app.add_exception_handler(Exception, handle_unexpected_error)
