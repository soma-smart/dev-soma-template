"""Unit tests for the outbox backoff schedule."""

from __future__ import annotations

from datetime import timedelta

import pytest

from {{ cookiecutter.package_name }}.infrastructure.jobs.backoff import compute_next_attempt


@pytest.mark.unit
def test_given_first_failure_when_computing_next_attempt_then_returns_one_second() -> None:
    # GIVEN
    attempts = 1

    # WHEN
    delay = compute_next_attempt(attempts)

    # THEN
    assert delay == timedelta(seconds=1)


@pytest.mark.unit
def test_given_third_failure_when_computing_next_attempt_then_returns_thirty_seconds() -> None:
    # GIVEN
    attempts = 3

    # WHEN
    delay = compute_next_attempt(attempts)

    # THEN
    assert delay == timedelta(seconds=30)


@pytest.mark.unit
def test_given_eighth_failure_when_computing_next_attempt_then_caps_at_one_hour() -> None:
    # GIVEN
    attempts = 8

    # WHEN
    delay = compute_next_attempt(attempts)

    # THEN
    assert delay == timedelta(hours=1)


@pytest.mark.unit
def test_given_far_beyond_schedule_when_computing_next_attempt_then_still_capped_at_one_hour() -> None:
    # GIVEN
    attempts = 999

    # WHEN
    delay = compute_next_attempt(attempts)

    # THEN
    assert delay == timedelta(hours=1)


@pytest.mark.unit
def test_given_zero_attempts_when_computing_next_attempt_then_treats_as_first_failure() -> None:
    # GIVEN
    attempts = 0

    # WHEN
    delay = compute_next_attempt(attempts)

    # THEN
    assert delay == timedelta(seconds=1)
