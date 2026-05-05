---
name: observability-patterns
description: How to use structlog + OpenTelemetry across the codebase, and where logging is forbidden.
when_to_use: Adding tracing or logs; touching infrastructure/observability/; a use case needs to "log".
---

# Observability patterns

## Where you can log

| Layer | Allowed? |
|---|---|
| `domain/` | NO — silent. Raise typed exceptions instead. |
| `application/` | NO. Same reason. |
| `infrastructure/` | YES — log on the boundary (repository persisted, http client called). |
| `presentation/` | YES — error handlers, request middleware. |

The split keeps domain logic pure and testable, and concentrates technical noise at I/O edges.

## Logger API

```python
import structlog

logger = structlog.get_logger(__name__)

logger.info("user.created", user_id=str(user.id), email=str(user.email))
logger.warning("payment.declined", reason=reason, attempt=attempt)
logger.exception("unexpected_error", path=path)
```

- **Event-style**: first positional argument is a dot-separated event name (`<noun>.<verb_past>`).
- **Structured kwargs**: never f-string interpolation. The renderer JSON-encodes in prod, pretty-prints in dev.
- **Trace correlation is automatic** when OTel is on (`trace_id` and `span_id` are injected by the `opentelemetry-instrumentation-logging` integration).
- **Sensitive keys are redacted automatically** — see `_redact_secrets` in `infrastructure/observability/logging.py`. Anything matching `password`, `token`, `authorization`, `secret`, `api_key` becomes `***`.

## Tracing

Auto-instrumentations cover FastAPI, SQLAlchemy, asyncpg, httpx out of the box.

For custom spans (a use case, a service call), use the `@traced` decorator:

```python
from {{ cookiecutter.package_name }}.infrastructure.observability import traced

class CreateUserUseCase:
    @traced("create_user")
    async def execute(self, input: CreateUserInput) -> CreateUserOutput:
        ...
```

The span name is dot-separated, lowercase. Add attributes via `trace.get_current_span().set_attribute(...)` only when the value is meaningful for debugging (don't dump full payloads).

## Exporter switching

- No `OTEL_EXPORTER_OTLP_ENDPOINT` set ⇒ spans go to stdout (dev default, also fine for CI).
- `OTEL_EXPORTER_OTLP_ENDPOINT=...` ⇒ OTLP gRPC export.

## Anti-patterns

- `print(...)` anywhere — caught by ruff `T20`.
- `logging.getLogger(__name__).info(...)` — use structlog instead.
- `f"user {user.id} created"` — use `logger.info("user.created", user_id=...)`.
- Logging inside a use case "for visibility" — instead, raise a typed `DomainError` if it's a business event, or let the calling layer log on the boundary.
