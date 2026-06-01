"""Observability primitives: structured logging, tracing, metrics setup."""

from {{ cookiecutter.package_name }}.infrastructure.observability.logging import configure_logging
{%- if cookiecutter.include_otel == "yes" %}
from {{ cookiecutter.package_name }}.infrastructure.observability.tracing import configure_tracing, traced
{%- endif %}

__all__ = [
    "configure_logging",
{%- if cookiecutter.include_otel == "yes" %}
    "configure_tracing",
    "traced",
{%- endif %}
]
