"""User-related FastAPI dependencies."""

from __future__ import annotations

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from {{ cookiecutter.package_name }}.application.auth.current_user import CurrentUser
from {{ cookiecutter.package_name }}.application.clock import Clock
from {{ cookiecutter.package_name }}.application.dtos.user import (
    EnsureUserExistsInput,
    EnsureUserExistsOutput,
)
from {{ cookiecutter.package_name }}.application.event_bus import EventBus
from {{ cookiecutter.package_name }}.application.id_generator import IdGenerator
from {{ cookiecutter.package_name }}.application.repositories.user import UserRepository
from {{ cookiecutter.package_name }}.application.use_cases.ensure_user_exists import (
    EnsureUserExistsUseCase,
)
from {{ cookiecutter.package_name }}.infrastructure.container import (
    build_ensure_user_exists_use_case,
    build_event_bus,
    build_user_repository,
)
from {{ cookiecutter.package_name }}.presentation.api.dependencies.auth import (
    get_current_user,
)
from {{ cookiecutter.package_name }}.presentation.api.dependencies.common import (
    get_clock,
    get_id_generator,
    get_session,
)


def get_user_repository(session: AsyncSession = Depends(get_session)) -> UserRepository:
    """Inject ``SqlAlchemyUserRepository`` bound to the request session."""
    return build_user_repository(session)


def get_event_bus(session: AsyncSession = Depends(get_session)) -> EventBus:
    """Inject ``SqlOutboxEventBus`` bound to the request session.

    Sharing the request session is intentional — the outbox row commits
    with the entity write, never in isolation (ADR 0004 + ADR 0005).
    """
    return build_event_bus(session)


def get_ensure_user_exists_use_case(
    users: UserRepository = Depends(get_user_repository),
    clock: Clock = Depends(get_clock),
    ids: IdGenerator = Depends(get_id_generator),
    events: EventBus = Depends(get_event_bus),
) -> EnsureUserExistsUseCase:
    """Inject the ``EnsureUserExistsUseCase`` wired with its collaborators."""
    return build_ensure_user_exists_use_case(
        users=users, clock=clock, ids=ids, events=events
    )


async def get_or_provision_user(
    current_user: CurrentUser = Depends(get_current_user),
    use_case: EnsureUserExistsUseCase = Depends(get_ensure_user_exists_use_case),
) -> EnsureUserExistsOutput:
    """Chain JWT verification with lazy SSO auto-provisioning.

    Routes that need the caller's ``User`` row (the internal UUID, not
    just the JWT subject) declare this dependency. On the first
    authenticated request for a given JWT subject the use case provisions
    a fresh ``User`` row from the JWT claims (``email``, ``name``); on
    subsequent calls the existing row is returned.

    Raises:
        MissingTokenError: 401 — no usable bearer header.
        InvalidTokenError: 401 — token failed verification.
        MissingProfileClaimsError: 401 — verified JWT lacks ``email`` /
            ``name`` claims required to provision the user.
    """
    return await use_case.execute(EnsureUserExistsInput(current_user=current_user))
