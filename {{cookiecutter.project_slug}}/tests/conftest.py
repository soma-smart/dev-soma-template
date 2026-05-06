"""Root conftest — primitives shared by all three test layers.

Per-layer conftests under ``tests/unit/``, ``tests/integration/`` and
``tests/e2e/`` scope additional fixtures to their intended audience. The
fixtures kept here are the ones reused across layers — most notably
``user_repository`` and ``create_user_use_case``, which doubles as a
unit-test Fake AND as the in-memory backing of the e2e
``dependency_overrides``.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from {{ cookiecutter.package_name }}.application.use_cases.create_user import CreateUserUseCase
from tests.fakes.clock import FrozenClock
from tests.fakes.id_generator import SequentialIdGenerator
from tests.fakes.random_source import SeededRandomSource
from tests.fakes.repositories.user import InMemoryUserRepository

DEFAULT_TEST_INSTANT = datetime(2026, 5, 5, 12, 0, tzinfo=UTC)


# ─── Primitive fakes ─────────────────────────────────────────────────
@pytest.fixture
def frozen_clock() -> FrozenClock:
    return FrozenClock(at=DEFAULT_TEST_INSTANT)


@pytest.fixture
def sequential_ids() -> SequentialIdGenerator:
    return SequentialIdGenerator(start=1)


@pytest.fixture
def seeded_random() -> SeededRandomSource:
    return SeededRandomSource(seed=0)


# ─── Repository fake (also acts as Spy via .users) ───────────────────
@pytest.fixture
def user_repository() -> InMemoryUserRepository:
    return InMemoryUserRepository()


# ─── Use case composed for unit + e2e tests ──────────────────────────
@pytest.fixture
def create_user_use_case(
    user_repository: InMemoryUserRepository,
    frozen_clock: FrozenClock,
    sequential_ids: SequentialIdGenerator,
) -> CreateUserUseCase:
    return CreateUserUseCase(users=user_repository, clock=frozen_clock, ids=sequential_ids)
