"""Request ID middleware — correlation identifier propagation."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from uuid import uuid4

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

REQUEST_ID_HEADER = "X-Request-ID"


class RequestIdMiddleware(BaseHTTPMiddleware):
    """Bind a request identifier to logs and echo it on the response.

    Reads an incoming ``X-Request-ID`` header (trusting upstream proxies that
    propagate one) or generates a fresh UUID4. The id is bound to the
    structlog context so every log emitted during the request includes it,
    and is exposed back to the caller via the same header for end-to-end
    correlation.
    """

    async def dispatch(self, request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        """Generate or honour the request id, bind it to logs, echo it back."""
        request_id = request.headers.get(REQUEST_ID_HEADER) or uuid4().hex
        request.state.request_id = request_id
        structlog.contextvars.bind_contextvars(request_id=request_id)
        try:
            response = await call_next(request)
        finally:
            structlog.contextvars.unbind_contextvars("request_id")
        response.headers.setdefault(REQUEST_ID_HEADER, request_id)
        return response
