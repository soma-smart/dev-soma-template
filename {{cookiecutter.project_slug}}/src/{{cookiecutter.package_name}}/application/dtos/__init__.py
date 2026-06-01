"""Use case input/output DTOs.

Each use case ships its ``...Input`` and ``...Output`` ``@dataclass(frozen=True,
slots=True)`` here. DTOs carry data only — never logic.
"""
