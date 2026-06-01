"""Per-request timeout middleware."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable

import structlog
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

logger = structlog.get_logger(__name__)


class RequestTimeoutMiddleware(BaseHTTPMiddleware):
    """Cap the wall-clock duration of each request.

    Returns 504 Gateway Timeout when the configured budget is exceeded. The
    underlying coroutine is cancelled, so DB connections and HTTP clients
    are released through their normal context-manager teardown.
    """

    def __init__(self, app: ASGIApp, *, timeout_seconds: float) -> None:
        super().__init__(app)
        self.timeout_seconds = timeout_seconds

    async def dispatch(self, request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        """Run the request with an asyncio timeout, return 504 on overrun."""
        try:
            return await asyncio.wait_for(call_next(request), timeout=self.timeout_seconds)
        except TimeoutError:
            logger.warning(
                "http.timeout",
                method=request.method,
                path=request.url.path,
                timeout_seconds=self.timeout_seconds,
            )
            return JSONResponse(
                status_code=504,
                content={
                    "error": {
                        "code": "REQUEST_TIMEOUT",
                        "message": f"The request exceeded the {self.timeout_seconds}-second budget.",
                    }
                },
            )
