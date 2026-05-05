"""User endpoints (API v1)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, status

from {{ cookiecutter.package_name }}.application.dtos.user import CreateUserInput
from {{ cookiecutter.package_name }}.application.use_cases.create_user import CreateUserUseCase
from {{ cookiecutter.package_name }}.presentation.api.dependencies.users import get_create_user_use_case
from {{ cookiecutter.package_name }}.presentation.api.schemas.user import UserCreateSchema, UserReadSchema

router = APIRouter(prefix="/v1/users", tags=["users"])


@router.post("", response_model=UserReadSchema, status_code=status.HTTP_201_CREATED)
async def create_user(
    payload: UserCreateSchema,
    use_case: CreateUserUseCase = Depends(get_create_user_use_case),
) -> UserReadSchema:
    """Register a new user account."""
    output = await use_case.execute(CreateUserInput(email=payload.email, name=payload.name))
    return UserReadSchema(
        id=output.id,
        email=output.email,
        name=output.name,
        created_at=output.created_at,
    )
