"""Outbox relay retry policy — pure functions, no I/O.

Schedule:

    after 1 failure  → wait 1 second
    after 2 failures → wait 5 seconds
    after 3 failures → wait 30 seconds
    after 4 failures → wait 2 minutes
    after 5 failures → wait 10 minutes
    after 6 failures → wait 30 minutes
    after 7+ failures → wait 1 hour (capped)
    after MAX_ATTEMPTS failures → row is poisoned, no further retries

Total elapsed time before poison ≈ 1 + 5 + 30 + 120 + 600 + 1800 + 3600 ×
(MAX_ATTEMPTS - 7) ≈ 3 hours at MAX_ATTEMPTS=10. Tune by editing this file.
"""

from __future__ import annotations

from datetime import timedelta

MAX_ATTEMPTS = 10
"""After this many failed attempts a row is marked ``poisoned`` and stops being polled."""

_DELAY_SCHEDULE_SECONDS: tuple[int, ...] = (1, 5, 30, 120, 600, 1800, 3600)
"""Indexed by ``(attempts - 1)``; values past the end use the last entry (cap)."""


def compute_next_attempt(attempts: int) -> timedelta:
    """Return the delay before re-attempting a row that has failed ``attempts`` times.

    ``attempts`` is the post-failure count: 1 means "just failed for the first
    time". Values <= 0 are treated as 1 — a row that has not failed at all has
    no business calling this function, but the contract stays defensive.
    """
    safe_attempts = max(attempts, 1)
    index = min(safe_attempts - 1, len(_DELAY_SCHEDULE_SECONDS) - 1)
    return timedelta(seconds=_DELAY_SCHEDULE_SECONDS[index])
