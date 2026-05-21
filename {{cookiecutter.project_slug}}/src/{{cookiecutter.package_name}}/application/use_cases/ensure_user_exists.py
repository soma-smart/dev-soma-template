"""``EnsureUserExistsUseCase`` — SSO lazy auto-provisioning.

Called from ``Depends(get_or_provision_user)`` on every authenticated
request. The first time a JWT subject is seen, a ``User`` row is created
from the JWT claims; subsequent requests reuse the existing row.
"""

from __future__ import annotations

from {{ cookiecutter.package_name }}.application.clock import Clock
from {{ cookiecutter.package_name }}.application.dtos.user import (
    EnsureUserExistsInput,
    EnsureUserExistsOutput,
)
from {{ cookiecutter.package_name }}.application.event_bus import EventBus
from {{ cookiecutter.package_name }}.application.id_generator import IdGenerator
from {{ cookiecutter.package_name }}.application.repositories.user import UserRepository
from {{ cookiecutter.package_name }}.application.use_cases.base import UseCase
from {{ cookiecutter.package_name }}.domain.entities.user import User
from {{ cookiecutter.package_name }}.domain.exceptions.auth import MissingProfileClaimsError
from {{ cookiecutter.package_name }}.domain.value_objects.email import Email
from {{ cookiecutter.package_name }}.domain.value_objects.user_id import UserId


class EnsureUserExistsUseCase(UseCase[EnsureUserExistsInput, EnsureUserExistsOutput]):
    """Map a verified JWT subject to a persisted ``User`` row, creating if needed."""

    def __init__(
        self,
        *,
        users: UserRepository,
        clock: Clock,
        ids: IdGenerator,
        events: EventBus,
    ) -> None:
        self._users = users
        self._clock = clock
        self._ids = ids
        self._events = events

    async def execute(self, input: EnsureUserExistsInput) -> EnsureUserExistsOutput:
        """Find the user for ``current_user.subject`` or provision one."""
        current = input.current_user
        existing = await self._users.find_by_subject(current.subject)
        if existing is not None:
            return _to_output(existing)

        if not current.email or not current.name:
            raise MissingProfileClaimsError(
                subject=current.subject,
                has_email=bool(current.email),
                has_name=bool(current.name),
            )

        user = User(
            id=UserId(self._ids.new()),
            subject=current.subject,
            email=Email(current.email),
            name=current.name,
            created_at=self._clock.now(),
        )
        await self._users.add(user)
        await self._events.publish(
            "user.provisioned",
            {
                "user_id": str(user.id.value),
                "subject": user.subject,
                "email": str(user.email),
                "name": user.name,
                "created_at": user.created_at.isoformat(),
            },
        )
        return _to_output(user)


def _to_output(user: User) -> EnsureUserExistsOutput:
    return EnsureUserExistsOutput(
        id=user.id.value,
        subject=user.subject,
        email=str(user.email),
        name=user.name,
        created_at=user.created_at,
    )
