"""Concrete handlers for domain events.

This module is imported once by the outbox relay at startup so the
``@handler`` decorators run and populate the registry in
:mod:`{{ cookiecutter.package_name }}.infrastructure.jobs.handlers`.

Add a new handler by:

1. Writing an async function ``async def my_handler(payload: dict) -> None:``.
2. Decorating it with ``@handler("<aggregate>.<verb_past>")``.
3. Restarting the relay (no other wiring needed).

The shipped ``handle_user_created`` is the reference example — a structured
log line per event. Replace or extend it with real side-effects (welcome
email, cache warm-up, projection update …).
"""

from __future__ import annotations

from typing import Any

import structlog

from {{ cookiecutter.package_name }}.infrastructure.jobs.handlers import handler

logger = structlog.get_logger(__name__)


@handler("user.created")
async def handle_user_created(payload: dict[str, Any]) -> None:
    """Log a structured line for each new user.

    Reference handler — replace with the real side-effect (welcome email,
    analytics enrichment, downstream projection …) when the project needs
    one. Must be idempotent: at-least-once delivery means this handler may
    run multiple times for the same ``user_id``.
    """
    logger.info(
        "event.user_created",
        user_id=payload.get("user_id"),
        email=payload.get("email"),
    )
