"""Production binding for the ``RandomSource`` abstraction."""

from __future__ import annotations

import secrets

from {{ cookiecutter.package_name }}.application.random_source import RandomSource


class SystemRandomSource(RandomSource):
    """Cryptographically strong random source backed by ``secrets``."""

    def next_int(self, low: int, high: int) -> int:
        if low > high:
            raise ValueError(f"low ({low}) must be <= high ({high})")
        return low + secrets.randbelow(high - low + 1)

    def next_float(self) -> float:
        # 53 bits of randomness mapped to [0.0, 1.0)
        return secrets.randbits(53) / (1 << 53)
