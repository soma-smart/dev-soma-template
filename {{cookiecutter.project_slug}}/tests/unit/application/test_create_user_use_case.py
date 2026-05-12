"""Unit tests for ``CreateUserUseCase`` — Fakes only, zero mocks."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

import pytest

from {{ cookiecutter.package_name }}.application.dtos.user import CreateUserInput
from {{ cookiecutter.package_name }}.application.use_cases.create_user import CreateUserUseCase
from {{ cookiecutter.package_name }}.domain.entities.user import User
from {{ cookiecutter.package_name }}.domain.exceptions.user import UserAlreadyExistsError
from {{ cookiecutter.package_name }}.domain.value_objects.email import Email, InvalidEmailError
from {{ cookiecutter.package_name }}.domain.value_objects.user_id import UserId
from tests.fakes.clock import FrozenClock
from tests.fakes.event_bus import InMemoryEventBus
from tests.fakes.id_generator import SequentialIdGenerator
from tests.fakes.repositories.user import InMemoryUserRepository


@pytest.mark.unit
async def test_given_empty_repository_when_creating_user_then_persists_and_returns_output(
    create_user_use_case: CreateUserUseCase,
    user_repository: InMemoryUserRepository,
) -> None:
    # GIVEN
    payload = CreateUserInput(email="Alice@Example.com", name="Alice")

    # WHEN
    output = await create_user_use_case.execute(payload)

    # THEN
    assert output.id == UUID(int=1)
    assert output.email == "alice@example.com"
    assert output.name == "Alice"
    assert output.created_at == datetime(2026, 5, 5, 12, 0, tzinfo=UTC)
    assert len(user_repository.users) == 1


@pytest.mark.unit
async def test_given_empty_repository_when_creating_user_then_publishes_user_created_event(
    create_user_use_case: CreateUserUseCase,
    event_bus: InMemoryEventBus,
) -> None:
    # GIVEN
    payload = CreateUserInput(email="alice@example.com", name="Alice")

    # WHEN
    await create_user_use_case.execute(payload)

    # THEN
    assert len(event_bus.published) == 1
    name, body = event_bus.published[0]
    assert name == "user.created"
    assert body == {
        "user_id": str(UUID(int=1)),
        "email": "alice@example.com",
        "name": "Alice",
        "created_at": datetime(2026, 5, 5, 12, 0, tzinfo=UTC).isoformat(),
    }


@pytest.mark.unit
async def test_given_existing_email_when_creating_user_then_does_not_publish_event(
    user_repository: InMemoryUserRepository,
    frozen_clock: FrozenClock,
    sequential_ids: SequentialIdGenerator,
    event_bus: InMemoryEventBus,
) -> None:
    # GIVEN
    user_repository.users[UserId(UUID(int=1))] = User(
        id=UserId(UUID(int=1)),
        email=Email("alice@example.com"),
        name="Alice",
        created_at=datetime(2026, 5, 5, tzinfo=UTC),
    )
    use_case = CreateUserUseCase(
        users=user_repository,
        clock=frozen_clock,
        ids=sequential_ids,
        events=event_bus,
    )

    # WHEN / THEN
    with pytest.raises(UserAlreadyExistsError):
        await use_case.execute(CreateUserInput(email="alice@example.com", name="Alice2"))
    assert event_bus.published == []


@pytest.mark.unit
async def test_given_existing_email_when_creating_user_then_raises_user_already_exists(
    user_repository: InMemoryUserRepository,
    frozen_clock: FrozenClock,
    sequential_ids: SequentialIdGenerator,
    event_bus: InMemoryEventBus,
) -> None:
    # GIVEN
    user_repository.users[UserId(UUID(int=1))] = User(
        id=UserId(UUID(int=1)),
        email=Email("alice@example.com"),
        name="Alice",
        created_at=datetime(2026, 5, 5, tzinfo=UTC),
    )
    use_case = CreateUserUseCase(
        users=user_repository,
        clock=frozen_clock,
        ids=sequential_ids,
        events=event_bus,
    )

    # WHEN / THEN
    with pytest.raises(UserAlreadyExistsError):
        await use_case.execute(CreateUserInput(email="alice@example.com", name="Alice2"))


@pytest.mark.unit
async def test_given_invalid_email_when_creating_user_then_raises_invalid_email(
    create_user_use_case: CreateUserUseCase,
) -> None:
    # GIVEN: use case wired by fixture

    # WHEN / THEN
    with pytest.raises(InvalidEmailError):
        await create_user_use_case.execute(CreateUserInput(email="not-an-email", name="Bob"))


@pytest.mark.unit
async def test_given_clock_at_specific_instant_when_creating_user_then_created_at_matches_clock(
    user_repository: InMemoryUserRepository,
    sequential_ids: SequentialIdGenerator,
    event_bus: InMemoryEventBus,
) -> None:
    # GIVEN
    instant = datetime(2030, 1, 1, 9, 30, tzinfo=UTC)
    use_case = CreateUserUseCase(
        users=user_repository,
        clock=FrozenClock(at=instant),
        ids=sequential_ids,
        events=event_bus,
    )

    # WHEN
    output = await use_case.execute(CreateUserInput(email="bob@example.com", name="Bob"))

    # THEN
    assert output.created_at == instant
