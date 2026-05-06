"""Kubernetes-style health endpoints.

Three probes mapping to the K8s probe semantics:
  * ``/health/live``    — process is responsive. No downstream check.
                          Failing causes a pod restart.
  * ``/health/ready``   — app can serve traffic right now (DB reachable).
                          Failing removes the pod from the load balancer
                          but does NOT restart it.
  * ``/health/startup`` — app has finished its boot routine. Same DB check
                          as ready, but with longer K8s timeouts allowed
                          before liveness/readiness kick in.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from {{ cookiecutter.package_name }}.presentation.api.dependencies.common import get_session

router = APIRouter(prefix="/health", tags=["health"])


@router.get("/live")
async def live() -> dict[str, str]:
    """Liveness probe — process is responsive.

    Never checks downstream dependencies: a degraded DB must not trigger
    pod restarts, only LB removal via ``/health/ready``.
    """
    return {"status": "live"}


@router.get("/ready")
async def ready(session: AsyncSession = Depends(get_session)) -> JSONResponse:
    """Readiness probe — app can serve traffic right now."""
    return await _check_database(session, ready_label="ready", failed_label="not_ready")


@router.get("/startup")
async def startup(session: AsyncSession = Depends(get_session)) -> JSONResponse:
    """Startup probe — app has finished its boot routine.

    Implementation-wise identical to ``/health/ready``; K8s applies looser
    timeouts so slow boots (warm caches, schema migrations) do not trip
    liveness while the pod is still coming up.
    """
    return await _check_database(session, ready_label="started", failed_label="not_started")


async def _check_database(session: AsyncSession, *, ready_label: str, failed_label: str) -> JSONResponse:
    try:
        await session.execute(text("SELECT 1"))
    except SQLAlchemyError:
        return JSONResponse(
            content={"status": failed_label, "reason": "database_unreachable"},
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        )
    return JSONResponse(content={"status": ready_label}, status_code=status.HTTP_200_OK)
