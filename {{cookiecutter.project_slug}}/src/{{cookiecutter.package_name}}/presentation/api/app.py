"""FastAPI application factory.

Builds the app from settings, attaches observability, registers middlewares
and error handlers, and exposes the database session factory through
``app.state``.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
{%- if cookiecutter.include_otel == "yes" %}
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.logging import LoggingInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
{%- endif %}
from prometheus_fastapi_instrumentator import Instrumentator

from {{ cookiecutter.package_name }}.infrastructure.config.settings import Settings, get_settings
from {{ cookiecutter.package_name }}.infrastructure.container import build_database
from {{ cookiecutter.package_name }}.infrastructure.observability import (
    configure_logging,
{%- if cookiecutter.include_otel == "yes" %}
    configure_tracing,
{%- endif %}
)
from {{ cookiecutter.package_name }}.presentation.api.error_handlers import register_error_handlers
from {{ cookiecutter.package_name }}.presentation.api.health import router as health_router
from {{ cookiecutter.package_name }}.presentation.api.middleware import (
    AccessLogMiddleware,
    BodySizeLimitMiddleware,
    IdempotencyMiddleware,
    RequestIdMiddleware,
    RequestTimeoutMiddleware,
    SecurityHeadersMiddleware,
)
from {{ cookiecutter.package_name }}.presentation.api.v1 import auth as auth_v1
from {{ cookiecutter.package_name }}.presentation.api.v1 import users as users_v1

logger = structlog.get_logger(__name__)


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build and configure the FastAPI application."""
    settings = settings or get_settings()
    configure_logging(log_format=settings.log_format, log_level=settings.log_level)
{%- if cookiecutter.include_otel == "yes" %}
    configure_tracing(settings)
    # Idempotent guard: ``create_app`` may run multiple times in the same
    # process (e.g. test fixtures); instrumenting twice raises warnings.
    _logging_instrumentor = LoggingInstrumentor()
    if not getattr(_logging_instrumentor, "_is_instrumented_by_opentelemetry", False):
        _logging_instrumentor.instrument(set_logging_format=False)
{%- endif %}

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        engine, factory = build_database(settings)
        app.state.engine = engine
        app.state.session_factory = factory
{%- if cookiecutter.include_otel == "yes" %}
        SQLAlchemyInstrumentor().instrument(engine=engine.sync_engine)
{%- endif %}
        logger.info("app.startup", service=settings.service_name)
        try:
            yield
        finally:
            await engine.dispose()
            logger.info("app.shutdown")

    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        lifespan=lifespan,
    )

    # Middleware order: the LAST ``add_middleware`` becomes the OUTERMOST
    # wrapper. We want, from outermost to innermost:
    #   RequestId -> AccessLog -> BodySizeLimit -> RequestTimeout -> CORS ->
    #   Idempotency -> SecurityHeaders -> handler
    # Idempotency sits close to the handler so timing/body-limit middleware
    # don't get bypassed on a cached replay.
    app.add_middleware(SecurityHeadersMiddleware)
    if settings.idempotency_enabled:
        app.add_middleware(
            IdempotencyMiddleware,
            methods=frozenset(settings.idempotency_methods),
            ttl_seconds=settings.idempotency_ttl_seconds,
        )
    if settings.cors_allowed_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_allowed_origins,
            allow_methods=["*"],
            allow_headers=["*"],
            allow_credentials=True,
        )
    app.add_middleware(RequestTimeoutMiddleware, timeout_seconds=settings.request_timeout_seconds)
    app.add_middleware(BodySizeLimitMiddleware, max_bytes=settings.request_max_body_bytes)
    app.add_middleware(AccessLogMiddleware)
    app.add_middleware(RequestIdMiddleware)

    register_error_handlers(app)

{%- if cookiecutter.include_otel == "yes" %}
    FastAPIInstrumentor().instrument_app(app)
{%- endif %}

    # Prometheus metrics endpoint. Always-on by design: the Helm chart's
    # ServiceMonitor (gated by metrics.enabled) decides whether the cluster
    # actually scrapes this endpoint. Excluded paths avoid /metrics scraping
    # itself (recursive noise) and the high-volume health probes.
    Instrumentator(
        excluded_handlers=["/metrics", "/health/.*"],
        should_group_status_codes=False,
    ).instrument(app).expose(app, include_in_schema=False, endpoint="/metrics")

    app.include_router(health_router)
    app.include_router(auth_v1.router)
    app.include_router(users_v1.router)
    return app


app = create_app()
