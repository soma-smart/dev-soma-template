"""Pydantic-Settings entry point.

All configuration is read from environment variables (via .env in dev).
Required fields without defaults crash the boot — there is no silent fallback.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Annotated, Any, Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    """Strongly-typed application settings."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="forbid",
        case_sensitive=False,
    )

    # ── App ──────────────────────────────────────────────────────────
    app_name: str = "{{ cookiecutter.project_name }}"
    log_format: Literal["console", "json"] = "console"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    service_name: str = "{{ cookiecutter.package_name }}"

    # ── Database ─────────────────────────────────────────────────────
    db_url: SecretStr = Field(...)
    db_pool_size: int = 10
    db_pool_max_overflow: int = 5
    db_pool_timeout: int = 30

    # ── Observability ────────────────────────────────────────────────
{%- if cookiecutter.include_otel == "yes" %}
    otel_exporter_otlp_endpoint: str | None = None
    otel_traces_sampler_arg: float = 1.0
{%- endif %}

    # ── HTTP middleware ──────────────────────────────────────────────
    request_max_body_bytes: int = 1_048_576  # 1 MiB
    request_timeout_seconds: float = 30.0

    # ── Outbox relay ─────────────────────────────────────────────────
    # Port on which the relay process exposes /metrics (Prometheus).
    # Scraped by a dedicated ServiceMonitor — see writing-a-helm-change.
    relay_metrics_port: int = 9100

    # ── Idempotency ──────────────────────────────────────────────────
    # Bearer-style retry safety. Clients send Idempotency-Key: <uuid>
    # on retry-eligible writes; the middleware caches and replays the
    # original response. See adding-idempotency-safety skill.
    idempotency_enabled: bool = True
    idempotency_methods: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["POST", "PUT", "PATCH", "DELETE"]
    )
    idempotency_ttl_seconds: int = 86_400  # 24h

    @field_validator("idempotency_methods", mode="before")
    @classmethod
    def _split_methods(cls, value: Any) -> Any:
        """Accept comma-separated env-var override (POST,PUT,PATCH,DELETE)."""
        if isinstance(value, str):
            return [item.strip().upper() for item in value.split(",") if item.strip()]
        return value

    # ── Auth ─────────────────────────────────────────────────────────
    # Bearer-JWT verification. See ``infrastructure/auth/jwt_verifier.py``
    # and the ``adding-auth`` skill for the swap path to a real IdP.
    auth_jwt_algorithm: Literal["HS256", "RS256"] = "HS256"
    auth_jwt_secret: SecretStr | None = None
    auth_jwt_jwks_url: str | None = None
    auth_jwt_audience: str | None = None
    auth_jwt_issuer: str | None = None
    auth_jwt_roles_claim: str = "roles"

    # ── Security ─────────────────────────────────────────────────────
    # ``NoDecode`` opts out of Pydantic's default JSON decoding so we can
    # accept the much friendlier comma-separated format in .env files.
    cors_allowed_origins: Annotated[list[str], NoDecode] = Field(default_factory=list)

    @field_validator("cors_allowed_origins", mode="before")
    @classmethod
    def _split_cors(cls, value: Any) -> Any:
        """Allow comma-separated values in env files: 'a,b,c' -> ['a','b','c']."""
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the application settings singleton.

    Cached for the process lifetime. Tests should override via
    ``app.dependency_overrides[get_settings]`` rather than calling
    ``get_settings.cache_clear()``.
    """
    return Settings()
