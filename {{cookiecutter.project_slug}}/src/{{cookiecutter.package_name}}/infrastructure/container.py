"""Dependency injection container.

Pure factory functions (no framework). FastAPI ``Depends`` wraps these in
``presentation/api/dependencies/``. CLI entry points and workers can call
these directly.

Use cases returned by ``build_*_use_case`` go through ``_instrumented``,
which transparently adds an OTel span and structured logging around
``execute``. This is where the application/observability boundary lives:
application code never imports structlog or OpenTelemetry — those concerns
are bolted on from the outside.
"""

from __future__ import annotations

from typing import Any

import structlog
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from {{ cookiecutter.package_name }}.application.auth.token_verifier import TokenVerifier
from {{ cookiecutter.package_name }}.application.clock import Clock
from {{ cookiecutter.package_name }}.application.event_bus import EventBus
from {{ cookiecutter.package_name }}.application.id_generator import IdGenerator
from {{ cookiecutter.package_name }}.application.random_source import RandomSource
from {{ cookiecutter.package_name }}.application.repositories.user import UserRepository
from {{ cookiecutter.package_name }}.application.use_cases.base import UseCase
from {{ cookiecutter.package_name }}.application.use_cases.create_user import CreateUserUseCase
from {{ cookiecutter.package_name }}.domain.exceptions.base import DomainError
from {{ cookiecutter.package_name }}.infrastructure.auth.jwt_verifier import JwtTokenVerifier
from {{ cookiecutter.package_name }}.infrastructure.clock import SystemClock
from {{ cookiecutter.package_name }}.infrastructure.config.settings import Settings
from {{ cookiecutter.package_name }}.infrastructure.id_generator import Uuid4IdGenerator
from {{ cookiecutter.package_name }}.infrastructure.observability.tracing import traced
from {{ cookiecutter.package_name }}.infrastructure.outbox import SqlOutboxEventBus
from {{ cookiecutter.package_name }}.infrastructure.persistence.session import (
    build_engine,
    build_session_factory,
)
from {{ cookiecutter.package_name }}.infrastructure.persistence.user_repository import SqlAlchemyUserRepository
from {{ cookiecutter.package_name }}.infrastructure.random_source import SystemRandomSource


def build_clock() -> Clock:
    """Return the production ``Clock`` binding."""
    return SystemClock()


def build_id_generator() -> IdGenerator:
    """Return the production ``IdGenerator`` binding."""
    return Uuid4IdGenerator()


def build_random_source() -> RandomSource:
    """Return the production ``RandomSource`` binding."""
    return SystemRandomSource()


def build_database(settings: Settings) -> tuple[AsyncEngine, async_sessionmaker[AsyncSession]]:
    """Build the engine and session factory from the application settings."""
    engine = build_engine(settings)
    return engine, build_session_factory(engine)


def build_user_repository(session: AsyncSession) -> UserRepository:
    """Build the SQLAlchemy-backed ``UserRepository`` for a given session."""
    return SqlAlchemyUserRepository(session)


def build_token_verifier(settings: Settings) -> TokenVerifier:
    """Build the production ``TokenVerifier``.

    Wired to :class:`JwtTokenVerifier`; swap this body if the project moves
    to a different scheme (mTLS, opaque tokens, …).
    """
    secret = settings.auth_jwt_secret.get_secret_value() if settings.auth_jwt_secret else None
    return JwtTokenVerifier(
        algorithm=settings.auth_jwt_algorithm,
        secret=secret,
        jwks_url=settings.auth_jwt_jwks_url,
        audience=settings.auth_jwt_audience,
        issuer=settings.auth_jwt_issuer,
        roles_claim=settings.auth_jwt_roles_claim,
    )


def build_event_bus(session: AsyncSession) -> EventBus:
    """Build the production ``EventBus`` — writes events to the SQL outbox.

    Use cases that publish events receive this; the outbox row is committed
    inside the request transaction (see ADR 0004), then forwarded to the
    real broker by ``infrastructure/jobs/outbox_relay.py`` (see ADR 0005).
    """
    return SqlOutboxEventBus(session)


def build_create_user_use_case(
    *,
    users: UserRepository,
    clock: Clock,
    ids: IdGenerator,
    events: EventBus,
) -> CreateUserUseCase:
    """Construct ``CreateUserUseCase`` with cross-cutting tracing + logging."""
    use_case = CreateUserUseCase(users=users, clock=clock, ids=ids, events=events)
    return _instrumented(use_case, span_name="create_user")


def _instrumented[U: UseCase[Any, Any]](use_case: U, *, span_name: str) -> U:
    """Wrap a use case's ``execute`` with OTel tracing + structured logging.

    The wrapper:
      - opens an OTel span named ``span_name`` (no-op when OTel is disabled)
      - logs ``DomainError`` raises at WARNING with ``code`` and ``context``
      - logs unexpected exceptions at ERROR with full stack trace
      - re-raises in all cases — the presentation handler still maps the
        exception to an HTTP response.

    The wrapped use case is returned unchanged in identity; only its
    ``execute`` attribute is rebound. Application code never sees this
    wrapping — it imports nothing from infrastructure.
    """
    original_execute = use_case.execute
    logger = structlog.get_logger(use_case.__class__.__module__)

    @traced(span_name)
    async def execute(input: Any) -> Any:
        try:
            return await original_execute(input)
        except DomainError as exc:
            logger.warning(
                f"{span_name}.domain_error",
                code=exc.code,
                context=exc.context,
            )
            raise
        except Exception:
            logger.exception(f"{span_name}.unexpected_error")
            raise

    # method-assign: rebinding the bound method on the instance is the whole
    # point of the wrapper — both type checkers (mypy, ty) flag it because
    # the closure signature is not the unbound class method shape.
    use_case.execute = execute  # type: ignore[method-assign] # ty: ignore[invalid-assignment]
    return use_case
