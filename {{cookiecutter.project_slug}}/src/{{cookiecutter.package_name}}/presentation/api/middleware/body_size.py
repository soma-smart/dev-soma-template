"""Reject requests whose declared body exceeds the configured limit."""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


class BodySizeLimitMiddleware(BaseHTTPMiddleware):
    """Reject oversized requests early via the ``Content-Length`` header.

    Trusts ``Content-Length`` (set by sane HTTP clients). Chunked uploads
    without ``Content-Length`` slip past this gate by design — pair the
    middleware with an upstream proxy size limit (Ingress / Envoy) for
    defence in depth.
    """

    def __init__(self, app: Callable[..., Awaitable[Response]], *, max_bytes: int) -> None:
        super().__init__(app)
        self.max_bytes = max_bytes

    async def dispatch(self, request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        """Return 413 when ``Content-Length`` exceeds ``max_bytes``."""
        content_length = request.headers.get("content-length")
        if content_length is not None:
            try:
                declared = int(content_length)
            except ValueError:
                declared = 0
            if declared > self.max_bytes:
                return JSONResponse(
                    status_code=413,
                    content={
                        "error": {
                            "code": "PAYLOAD_TOO_LARGE",
                            "message": f"Request body exceeds the {self.max_bytes}-byte limit.",
                        }
                    },
                )
        return await call_next(request)
