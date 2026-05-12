"""User-related FastAPI dependencies."""

from __future__ import annotations

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from {{ cookiecutter.package_name }}.application.clock import Clock
from {{ cookiecutter.package_name }}.application.event_bus import EventBus
from {{ cookiecutter.package_name }}.application.id_generator import IdGenerator
from {{ cookiecutter.package_name }}.application.repositories.user import UserRepository
from {{ cookiecutter.package_name }}.application.use_cases.create_user import CreateUserUseCase
from {{ cookiecutter.package_name }}.infrastructure.container import (
    build_create_user_use_case,
    build_event_bus,
    build_user_repository,
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


def get_create_user_use_case(
    users: UserRepository = Depends(get_user_repository),
    clock: Clock = Depends(get_clock),
    ids: IdGenerator = Depends(get_id_generator),
    events: EventBus = Depends(get_event_bus),
) -> CreateUserUseCase:
    """Inject the ``CreateUserUseCase`` wired with its collaborators."""
    return build_create_user_use_case(users=users, clock=clock, ids=ids, events=events)
