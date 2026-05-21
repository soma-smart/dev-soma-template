{% if cookiecutter.include_otel == "yes" -%}
"""OpenTelemetry tracing setup with auto-switching exporter.

When ``OTEL_EXPORTER_OTLP_ENDPOINT`` is set the SDK exports spans via gRPC
OTLP. Otherwise spans are written to stdout (zero-config dev). The
``@traced`` decorator opens a custom span around any callable.
"""

from __future__ import annotations

import functools
from collections.abc import Awaitable, Callable
from typing import ParamSpec, TypeVar

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
from opentelemetry.sdk.trace.sampling import ParentBased, TraceIdRatioBased

from {{ cookiecutter.package_name }}.infrastructure.config.settings import Settings

P = ParamSpec("P")
R = TypeVar("R")


def configure_tracing(settings: Settings) -> None:
    """Initialise the global tracer provider based on settings.

    Idempotent: subsequent calls replace the active provider.
    """
    resource = Resource.create({"service.name": settings.service_name})
    sampler = ParentBased(TraceIdRatioBased(settings.otel_traces_sampler_arg))
    provider = TracerProvider(resource=resource, sampler=sampler)

    exporter: OTLPSpanExporter | ConsoleSpanExporter
    if settings.otel_exporter_otlp_endpoint:
        exporter = OTLPSpanExporter(endpoint=settings.otel_exporter_otlp_endpoint)
    else:
        exporter = ConsoleSpanExporter()

    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)


def traced(span_name: str) -> Callable[[Callable[P, Awaitable[R]]], Callable[P, Awaitable[R]]]:
    """Decorate an async callable with a custom OTel span.

    Usage:
        @traced("ensure_user_exists")
        async def execute(self, input: EnsureUserExistsInput) -> EnsureUserExistsOutput: ...
    """

    def decorator(func: Callable[P, Awaitable[R]]) -> Callable[P, Awaitable[R]]:
        tracer = trace.get_tracer(func.__module__)

        @functools.wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            with tracer.start_as_current_span(span_name):
                return await func(*args, **kwargs)

        return wrapper

    return decorator
{%- else -%}
"""OpenTelemetry tracing is disabled in this generated project.

Re-enable by regenerating with ``include_otel=yes`` or by adding
``opentelemetry-api`` + ``opentelemetry-sdk`` to ``pyproject.toml`` and
restoring the implementation from the template repository.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import ParamSpec, TypeVar

from {{ cookiecutter.package_name }}.infrastructure.config.settings import Settings

P = ParamSpec("P")
R = TypeVar("R")


def configure_tracing(_settings: Settings) -> None:
    """No-op when OTel is not included."""


def traced(_span_name: str) -> Callable[[Callable[P, Awaitable[R]]], Callable[P, Awaitable[R]]]:
    """Identity decorator when OTel is not included."""

    def decorator(func: Callable[P, Awaitable[R]]) -> Callable[P, Awaitable[R]]:
        return func

    return decorator
{%- endif %}
