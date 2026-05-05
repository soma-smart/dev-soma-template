"""Deterministic id generator fake."""

from __future__ import annotations

from uuid import UUID

from {{ cookiecutter.package_name }}.application.id_generator import IdGenerator


class SequentialIdGenerator(IdGenerator):
    """Yields predictable UUIDs ``00000000-0000-0000-0000-00000000000n``."""

    def __init__(self, start: int = 1) -> None:
        self._counter = start

    def new(self) -> UUID:
        value = UUID(int=self._counter)
        self._counter += 1
        return value
