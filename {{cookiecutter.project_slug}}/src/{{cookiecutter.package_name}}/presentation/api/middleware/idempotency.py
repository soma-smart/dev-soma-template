"""Idempotency middleware.

Clients add ``Idempotency-Key: <random-uuid>`` on retry-eligible writes
(POST, PUT, PATCH, DELETE). The middleware:

* On the first request, inserts a row with ``status='in_progress'`` then
  runs the handler. After the handler returns successfully, the row is
  updated to ``status='completed'`` with the captured response.
* On a retry with the same key:

  - if the original is ``completed`` and the method+path match, the
    cached response is returned **without re-running the handler**.
  - if the original is still ``in_progress`` (a race or a stalled
    earlier attempt that has not yet expired), the retry is rejected
    with 409 ``IDEMPOTENCY_IN_PROGRESS``.
  - if the method+path mismatch, the retry is rejected with 422
    ``IDEMPOTENCY_KEY_MISMATCH``.
  - if the row has expired, it is deleted and the request is treated as
    fresh.

The middleware uses its own session (from
``request.app.state.session_factory``) so the idempotency lock commits
independently of the request transaction.

Limitations (documented in the ``adding-idempotency-safety`` skill):

* Request body is NOT hashed; mismatched-body retries with the same
  method+path silently return the cached reply. Validate at the schema
  level if precise replay matters.
* Streaming responses are passed through without caching — only the
  first reply is sent; logs a warning.
"""

from __future__ import annotations

import json
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from {{ cookiecutter.package_name }}.infrastructure.persistence.models.idempotency_record import IdempotencyRecord

logger = structlog.get_logger(__name__)

IDEMPOTENCY_HEADER = "Idempotency-Key"
_KEY_MAX_LENGTH = 255


class IdempotencyMiddleware(BaseHTTPMiddleware):
    """Cache responses keyed by ``Idempotency-Key`` for retry-eligible methods."""

    def __init__(
        self,
        app: Any,
        *,
        methods: frozenset[str],
        ttl_seconds: int,
    ) -> None:
        super().__init__(app)
        self._methods = methods
        self._ttl = timedelta(seconds=ttl_seconds)

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        """Resolve idempotency for the current request and dispatch the handler."""
        if request.method.upper() not in self._methods:
            return await call_next(request)

        key = request.headers.get(IDEMPOTENCY_HEADER)
        if not key:
            return await call_next(request)
        if len(key) > _KEY_MAX_LENGTH:
            return _error_response(
                status_code=400,
                code="IDEMPOTENCY_KEY_TOO_LONG",
                message=f"Idempotency-Key exceeds {_KEY_MAX_LENGTH} characters.",
            )

        factory = getattr(request.app.state, "session_factory", None)
        if factory is None:
            # Tests / health probes can stub out session_factory; degrade quietly.
            logger.warning("idempotency.no_session_factory", key=key)
            return await call_next(request)

        method = request.method.upper()
        path = request.url.path
        now = datetime.now(tz=UTC)

        # 1. Try to claim the key with status='in_progress'. On conflict, inspect
        #    the existing row and either replay, reject, or recycle (expired).
        claim_result = await self._claim_key(factory, key=key, method=method, path=path, now=now)
        if isinstance(claim_result, Response):
            return claim_result

        # 2. Run the handler.
        try:
            response = await call_next(request)
        except Exception:
            # Leave the in-progress row in place; it will expire and unblock the
            # next attempt. Do NOT delete here: a quick retry must still see the
            # in-progress state to avoid double work.
            raise

        # 3. Capture the response body so we can replay it AND so we can return
        #    a fresh Response (the body iterator can only be consumed once).
        body_bytes = b""
        async for chunk in response.body_iterator:
            body_bytes += chunk if isinstance(chunk, bytes) else chunk.encode()

        await self._complete(
            factory,
            key=key,
            response_status=response.status_code,
            body_bytes=body_bytes,
            headers=dict(response.headers),
            now=datetime.now(tz=UTC),
        )

        return Response(
            content=body_bytes,
            status_code=response.status_code,
            headers={k: v for k, v in response.headers.items() if k.lower() != "content-length"},
            media_type=response.media_type,
        )

    async def _claim_key(
        self,
        factory: Any,
        *,
        key: str,
        method: str,
        path: str,
        now: datetime,
    ) -> Response | None:
        """Atomic-ish: try to insert in_progress, fall back to inspecting an existing row.

        Returns ``None`` when the caller should run the handler, or a
        ``Response`` to return immediately.
        """
        async with factory() as session, session.begin():
            session.add(
                IdempotencyRecord(
                    key=key,
                    status="in_progress",
                    method=method,
                    path=path,
                    created_at=now,
                    expires_at=now + self._ttl,
                )
            )
            try:
                await session.flush()
            except IntegrityError:
                await session.rollback()
                return await self._inspect_existing(factory, key=key, method=method, path=path, now=now)
        return None

    async def _inspect_existing(
        self,
        factory: Any,
        *,
        key: str,
        method: str,
        path: str,
        now: datetime,
    ) -> Response | None:
        """Decide what to return for a retry on a key that already exists.

        Returns ``None`` when the existing row was expired and got recycled,
        meaning the caller should fall through to running the handler.
        Returns a ``Response`` to return to the client otherwise.
        """
        async with factory() as session, session.begin():
            existing = await session.scalar(
                select(IdempotencyRecord).where(IdempotencyRecord.key == key)
            )
            if existing is None:
                # Race: the row was deleted between our INSERT and this SELECT.
                # Behave as if the key was free — the caller will retry the claim.
                # Re-raising is uglier than logging: degrade quietly.
                logger.warning("idempotency.row_disappeared", key=key)
                return _error_response(
                    status_code=409,
                    code="IDEMPOTENCY_IN_PROGRESS",
                    message="Idempotency key is being processed; retry shortly.",
                )

            if existing.expires_at <= now:
                # Expired — clear it and tell the caller to treat as fresh.
                await session.delete(existing)
                # Synthesize a fresh in-progress row in this same transaction so
                # we keep the lock semantics.
                session.add(
                    IdempotencyRecord(
                        key=key,
                        status="in_progress",
                        method=method,
                        path=path,
                        created_at=now,
                        expires_at=now + self._ttl,
                    )
                )
                return None

            if existing.method != method or existing.path != path:
                return _error_response(
                    status_code=422,
                    code="IDEMPOTENCY_KEY_MISMATCH",
                    message=(
                        f"Idempotency-Key was first used for {existing.method} {existing.path}; "
                        f"now reused on {method} {path}."
                    ),
                )

            if existing.status == "in_progress":
                return _error_response(
                    status_code=409,
                    code="IDEMPOTENCY_IN_PROGRESS",
                    message="A request with this Idempotency-Key is still being processed.",
                )

            # status == 'completed' — replay the original response.
            body_bytes = (
                json.dumps(existing.response_body).encode()
                if existing.response_body is not None
                else b""
            )
            headers = {
                k: v
                for k, v in (existing.response_headers or {}).items()
                if k.lower() != "content-length"
            }
            return Response(
                content=body_bytes,
                status_code=existing.response_status or 200,
                headers=headers,
                media_type="application/json",
            )

    async def _complete(
        self,
        factory: Any,
        *,
        key: str,
        response_status: int,
        body_bytes: bytes,
        headers: dict[str, str],
        now: datetime,
    ) -> None:
        """Mark the in-progress row as completed and persist the response."""
        try:
            decoded_body = json.loads(body_bytes) if body_bytes else None
        except json.JSONDecodeError:
            # Non-JSON response (file download, plain text) — store the raw
            # bytes under a sentinel key; replay will best-effort serve them.
            logger.warning("idempotency.non_json_body", key=key)
            decoded_body = {"__raw__": body_bytes.decode(errors="replace")}

        async with factory() as session, session.begin():
            row = await session.scalar(
                select(IdempotencyRecord).where(IdempotencyRecord.key == key)
            )
            if row is None:
                logger.warning("idempotency.row_missing_on_complete", key=key)
                return
            row.status = "completed"
            row.response_status = response_status
            row.response_body = decoded_body
            row.response_headers = headers
            row.completed_at = now


def _error_response(*, status_code: int, code: str, message: str) -> JSONResponse:
    """Build an error response matching the project's JSON error shape."""
    return JSONResponse(
        status_code=status_code,
        content={"error": {"code": code, "message": message}},
    )
