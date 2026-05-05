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
from tests.fakes.id_generator import SequentialIdGenerator
from tests.fakes.repositories.user import InMemoryUserRepository


@pytest.mark.unit
async def test_given_empty_repository_when_creating_user_then_persists_and_returns_output() -> None:
    # GIVEN
    repo = InMemoryUserRepository()
    clock = FrozenClock(at=datetime(2026, 5, 5, 12, 0, tzinfo=UTC))
    ids = SequentialIdGenerator(start=1)
    use_case = CreateUserUseCase(users=repo, clock=clock, ids=ids)

    # WHEN
    output = await use_case.execute(CreateUserInput(email="Alice@Example.com", name="Alice"))

    # THEN
    assert output.id == UUID(int=1)
    assert output.email == "alice@example.com"
    assert output.name == "Alice"
    assert output.created_at == datetime(2026, 5, 5, 12, 0, tzinfo=UTC)
    assert len(repo.users) == 1


@pytest.mark.unit
async def test_given_existing_email_when_creating_user_then_raises_user_already_exists() -> None:
    # GIVEN
    repo = InMemoryUserRepository(
        seed=[
            User(
                id=UserId(UUID(int=1)),
                email=Email("alice@example.com"),
                name="Alice",
                created_at=datetime(2026, 5, 5, tzinfo=UTC),
            )
        ]
    )
    use_case = CreateUserUseCase(
        users=repo,
        clock=FrozenClock(at=datetime(2026, 5, 5, tzinfo=UTC)),
        ids=SequentialIdGenerator(start=2),
    )

    # WHEN / THEN
    with pytest.raises(UserAlreadyExistsError):
        await use_case.execute(CreateUserInput(email="alice@example.com", name="Alice2"))


@pytest.mark.unit
async def test_given_invalid_email_when_creating_user_then_raises_invalid_email() -> None:
    # GIVEN
    use_case = CreateUserUseCase(
        users=InMemoryUserRepository(),
        clock=FrozenClock(at=datetime(2026, 5, 5, tzinfo=UTC)),
        ids=SequentialIdGenerator(),
    )

    # WHEN / THEN
    with pytest.raises(InvalidEmailError):
        await use_case.execute(CreateUserInput(email="not-an-email", name="Bob"))


@pytest.mark.unit
async def test_given_clock_at_specific_instant_when_creating_user_then_created_at_matches_clock() -> None:
    # GIVEN
    instant = datetime(2030, 1, 1, 9, 30, tzinfo=UTC)
    repo = InMemoryUserRepository()
    use_case = CreateUserUseCase(
        users=repo,
        clock=FrozenClock(at=instant),
        ids=SequentialIdGenerator(),
    )

    # WHEN
    output = await use_case.execute(CreateUserInput(email="bob@example.com", name="Bob"))

    # THEN
    assert output.created_at == instant
