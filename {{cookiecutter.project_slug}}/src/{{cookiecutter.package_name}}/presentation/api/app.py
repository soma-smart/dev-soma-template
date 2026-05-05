"""FastAPI application factory.

Phase A delivers a minimal app with a /health endpoint. Phase B will wire
settings, observability, error handlers, middlewares and the DI container.
"""

from __future__ import annotations

from fastapi import FastAPI


def create_app() -> FastAPI:
    """Build and return the FastAPI application."""
    app = FastAPI(
        title="{{ cookiecutter.project_name }}",
        version="0.1.0",
    )

    @app.get("/health", tags=["health"])
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
