"""Deterministic random source fake."""

from __future__ import annotations

import random

from {{ cookiecutter.package_name }}.application.random_source import RandomSource


class SeededRandomSource(RandomSource):
    """Random source backed by ``random.Random(seed)`` for repeatable tests."""

    def __init__(self, seed: int = 0) -> None:
        self._rng = random.Random(seed)  # noqa: S311 — non-cryptographic on purpose for tests

    def next_int(self, low: int, high: int) -> int:
        if low > high:
            raise ValueError(f"low ({low}) must be <= high ({high})")
        return self._rng.randint(low, high)

    def next_float(self) -> float:
        return self._rng.random()
