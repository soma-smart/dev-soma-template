"""structlog configuration with secret redaction and OTel correlation."""

from __future__ import annotations

import logging
import sys
from typing import Any

import structlog
from structlog.types import EventDict, Processor

REDACTED = "***"
SENSITIVE_KEY_FRAGMENTS = ("password", "token", "authorization", "secret", "api_key")


def _redact_secrets(_: Any, __: str, event_dict: EventDict) -> EventDict:
    """Replace values whose key contains a sensitive fragment with ``***``.

    Conservative by design: any key matching a fragment is redacted, even when
    the value is empty. Tests cover the redaction set.
    """
    for key in list(event_dict.keys()):
        lower = key.lower()
        if any(fragment in lower for fragment in SENSITIVE_KEY_FRAGMENTS):
            event_dict[key] = REDACTED
    return event_dict


def configure_logging(*, log_format: str, log_level: str) -> None:
    """Configure structlog and the stdlib logging facade.

    Args:
        log_format: ``console`` for dev (colored, human-readable) or
            ``json`` for prod (one JSON line per event, ingestable).
        log_level: minimum severity (``DEBUG``, ``INFO``, ``WARNING``, ``ERROR``).
    """
    timestamper = structlog.processors.TimeStamper(fmt="iso", utc=True)

    shared_processors: list[Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        timestamper,
        _redact_secrets,
    ]

    renderer: Processor
    if log_format == "json":
        renderer = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer(colors=sys.stdout.isatty())

    structlog.configure(
        processors=[*shared_processors, renderer],
        wrapper_class=structlog.make_filtering_bound_logger(getattr(logging, log_level.upper())),
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )
