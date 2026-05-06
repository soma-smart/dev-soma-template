"""Access log middleware — one structured line per HTTP request."""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = structlog.get_logger("http.access")

# Endpoints whose volume would drown the log stream and that bring no value
# to ingest. Kept short on purpose: anything user-meaningful is logged.
SILENT_PATHS = ("/health/live", "/health/ready", "/health/startup")


class AccessLogMiddleware(BaseHTTPMiddleware):
    """Emit one ``http.request`` event with method, path, status, duration."""

    async def dispatch(self, request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        """Time the request, then log a single structured event."""
        if request.url.path in SILENT_PATHS:
            return await call_next(request)

        start = time.perf_counter()
        response = await call_next(request)
        duration_ms = round((time.perf_counter() - start) * 1000, 2)

        logger.info(
            "http.request",
            method=request.method,
            path=request.url.path,
            status=response.status_code,
            duration_ms=duration_ms,
            client=request.client.host if request.client else None,
        )
        return response
