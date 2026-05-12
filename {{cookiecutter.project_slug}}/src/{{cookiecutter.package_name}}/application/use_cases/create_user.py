"""``CreateUserUseCase`` — reference use case."""

from __future__ import annotations

from {{ cookiecutter.package_name }}.application.clock import Clock
from {{ cookiecutter.package_name }}.application.dtos.user import CreateUserInput, CreateUserOutput
from {{ cookiecutter.package_name }}.application.event_bus import EventBus
from {{ cookiecutter.package_name }}.application.id_generator import IdGenerator
from {{ cookiecutter.package_name }}.application.repositories.user import UserRepository
from {{ cookiecutter.package_name }}.application.use_cases.base import UseCase
from {{ cookiecutter.package_name }}.domain.entities.user import User
from {{ cookiecutter.package_name }}.domain.exceptions.user import UserAlreadyExistsError
from {{ cookiecutter.package_name }}.domain.value_objects.email import Email
from {{ cookiecutter.package_name }}.domain.value_objects.user_id import UserId


class CreateUserUseCase(UseCase[CreateUserInput, CreateUserOutput]):
    """Register a new user account and emit ``user.created``.

    Raises:
        UserAlreadyExistsError: a user with the same email already exists.
        InvalidEmailError: the supplied email fails validation.
    """

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

    async def execute(self, input: CreateUserInput) -> CreateUserOutput:
        """Create the user, publish ``user.created``, return its projection."""
        email = Email(input.email)
        existing = await self._users.find_by_email(email)
        if existing is not None:
            raise UserAlreadyExistsError(email=str(email))

        user = User(
            id=UserId(self._ids.new()),
            email=email,
            name=input.name,
            created_at=self._clock.now(),
        )
        await self._users.add(user)
        await self._events.publish(
            "user.created",
            {
                "user_id": str(user.id.value),
                "email": str(user.email),
                "name": user.name,
                "created_at": user.created_at.isoformat(),
            },
        )
        return CreateUserOutput(
            id=user.id.value,
            email=str(user.email),
            name=user.name,
            created_at=user.created_at,
        )
