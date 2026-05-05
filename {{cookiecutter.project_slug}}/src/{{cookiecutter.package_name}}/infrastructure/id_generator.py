"""Production binding for the ``IdGenerator`` abstraction."""

from __future__ import annotations

from uuid import UUID, uuid4

from {{ cookiecutter.package_name }}.application.id_generator import IdGenerator


class Uuid4IdGenerator(IdGenerator):
    """``IdGenerator`` returning random UUID4 values."""

    def new(self) -> UUID:
        return uuid4()
