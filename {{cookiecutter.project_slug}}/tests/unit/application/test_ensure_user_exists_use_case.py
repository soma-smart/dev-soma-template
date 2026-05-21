"""Outside-in TDD for ``EnsureUserExistsUseCase``.

This use case backs the SSO auto-provisioning flow: on every
authenticated request, the route's ``Depends(get_or_provision_user)``
chains the verified ``CurrentUser`` into this use case. The first time
a JWT subject is seen, a row is created; subsequent calls return the
existing row.
"""

from __future__ import annotations

import pytest

from tests.fakes.event_bus import InMemoryEventBus
from tests.fakes.repositories.user import InMemoryUserRepository
from {{ cookiecutter.package_name }}.application.auth.current_user import CurrentUser
from {{ cookiecutter.package_name }}.application.dtos.user import EnsureUserExistsInput
from {{ cookiecutter.package_name }}.application.use_cases.ensure_user_exists import (
    EnsureUserExistsUseCase,
)
from {{ cookiecutter.package_name }}.domain.exceptions.auth import MissingProfileClaimsError


def _claims(
    *,
    subject: str = "azure-sub-abc",
    email: str | None = "alice@example.com",
    name: str | None = "Alice",
) -> CurrentUser:
    return CurrentUser(subject=subject, email=email, name=name)


@pytest.mark.unit
async def test_given_subject_never_seen_when_ensuring_then_creates_one_user(
    ensure_user_exists_use_case: EnsureUserExistsUseCase,
    user_repository: InMemoryUserRepository,
) -> None:
    # GIVEN
    claims = _claims(subject="azure-sub-1", email="alice@example.com", name="Alice")

    # WHEN
    await ensure_user_exists_use_case.execute(EnsureUserExistsInput(current_user=claims))

    # THEN
    assert len(user_repository.users) == 1


@pytest.mark.unit
async def test_given_subject_already_persisted_when_ensuring_then_no_new_user_is_created(
    ensure_user_exists_use_case: EnsureUserExistsUseCase,
    user_repository: InMemoryUserRepository,
) -> None:
    # GIVEN
    claims = _claims(subject="azure-sub-2", email="bob@example.com", name="Bob")
    await ensure_user_exists_use_case.execute(EnsureUserExistsInput(current_user=claims))

    # WHEN
    await ensure_user_exists_use_case.execute(EnsureUserExistsInput(current_user=claims))

    # THEN
    assert len(user_repository.users) == 1


@pytest.mark.unit
async def test_given_subject_already_persisted_when_ensuring_then_returns_existing_user(
    ensure_user_exists_use_case: EnsureUserExistsUseCase,
    user_repository: InMemoryUserRepository,
) -> None:
    # GIVEN
    claims = _claims(subject="azure-sub-3", email="carol@example.com", name="Carol")
    first = await ensure_user_exists_use_case.execute(
        EnsureUserExistsInput(current_user=claims)
    )

    # WHEN
    second = await ensure_user_exists_use_case.execute(
        EnsureUserExistsInput(current_user=claims)
    )

    # THEN
    assert second.id == first.id


@pytest.mark.unit
async def test_given_claims_without_email_when_ensuring_then_raises_missing_profile_claims(
    ensure_user_exists_use_case: EnsureUserExistsUseCase,
) -> None:
    # GIVEN
    claims = _claims(subject="azure-sub-4", email=None, name="Dan")

    # WHEN / THEN
    with pytest.raises(MissingProfileClaimsError):
        await ensure_user_exists_use_case.execute(
            EnsureUserExistsInput(current_user=claims)
        )


@pytest.mark.unit
async def test_given_claims_without_name_when_ensuring_then_raises_missing_profile_claims(
    ensure_user_exists_use_case: EnsureUserExistsUseCase,
) -> None:
    # GIVEN
    claims = _claims(subject="azure-sub-5", email="erin@example.com", name=None)

    # WHEN / THEN
    with pytest.raises(MissingProfileClaimsError):
        await ensure_user_exists_use_case.execute(
            EnsureUserExistsInput(current_user=claims)
        )


@pytest.mark.unit
async def test_given_first_provision_when_inspecting_event_then_publishes_user_provisioned(
    ensure_user_exists_use_case: EnsureUserExistsUseCase,
    event_bus: InMemoryEventBus,
) -> None:
    # GIVEN
    claims = _claims(subject="azure-sub-6", email="fred@example.com", name="Fred")

    # WHEN
    await ensure_user_exists_use_case.execute(EnsureUserExistsInput(current_user=claims))

    # THEN
    event_name, _ = event_bus.published[0]
    assert event_name == "user.provisioned"


@pytest.mark.unit
async def test_given_already_persisted_when_ensuring_again_then_does_not_republish_event(
    ensure_user_exists_use_case: EnsureUserExistsUseCase,
    event_bus: InMemoryEventBus,
) -> None:
    # GIVEN
    claims = _claims(subject="azure-sub-7", email="gail@example.com", name="Gail")
    await ensure_user_exists_use_case.execute(EnsureUserExistsInput(current_user=claims))
    initial_events = len(event_bus.published)

    # WHEN
    await ensure_user_exists_use_case.execute(EnsureUserExistsInput(current_user=claims))

    # THEN
    assert len(event_bus.published) == initial_events
