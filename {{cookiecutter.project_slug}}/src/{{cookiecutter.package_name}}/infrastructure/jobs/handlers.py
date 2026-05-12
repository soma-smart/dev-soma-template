"""In-process event handler registry.

This is the consumer side of the outbox pattern (ADR 0005). The current SOMA
template runs handlers in the SAME process as the outbox relay — there is no
external broker. The swap point is :func:`dispatch`: replace its body with a
real broker publish call (Kafka, Pub/Sub, SQS, …) when the project goes
multi-service.

Handlers are registered with the :func:`handler` decorator at module import
time. The relay worker imports :mod:`event_handlers` once at startup so the
decorators run and populate the registry; from then on, every drained outbox
row is forwarded to all matching handlers in registration order.

Concurrency posture (in-process variant):

* Handlers run sequentially per event. If a handler raises, the row stays
  unpublished and the relay retries on the next tick (see :func:`_drain_once`).
* Replicating the relay across pods will run handlers on every replica —
  either keep a single replica, or make handlers idempotent.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Awaitable, Callable
from typing import Any

Handler = Callable[[dict[str, Any]], Awaitable[None]]

_HANDLERS: dict[str, list[Handler]] = defaultdict(list)


def handler(event_name: str) -> Callable[[Handler], Handler]:
    """Register ``fn`` as a handler for ``event_name``.

    Multiple handlers per event are allowed; they run in registration order.
    The handler MUST be idempotent: at-least-once delivery is the guarantee
    the outbox gives, so a retry after a relay crash will re-invoke the
    handler on the same payload.
    """

    def decorator(fn: Handler) -> Handler:
        _HANDLERS[event_name].append(fn)
        return fn

    return decorator


async def dispatch(event_name: str, payload: dict[str, Any]) -> None:
    """Run all handlers registered for ``event_name`` against ``payload``.

    Raises the first handler exception encountered. The outbox relay catches
    it, logs it, and leaves the row unpublished so the next tick retries.

    This is the function to replace when wiring a real broker — its body
    becomes ``await broker.publish(event_name, payload)`` and the registry
    is removed (or kept for local development).
    """
    for fn in _HANDLERS[event_name]:
        await fn(payload)


def registered_event_names() -> list[str]:
    """Return the event names that currently have at least one handler.

    Exposed for diagnostics — startup banners, readiness checks, tests that
    assert a handler was wired.
    """
    return [name for name, fns in _HANDLERS.items() if fns]
