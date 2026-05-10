---
name: observability-patterns
description: structlog + OpenTelemetry + Prometheus across the codebase. Where logging is forbidden, how use cases get instrumented from the outside, how /metrics is exposed, how requests correlate via X-Request-ID + trace_id.
when_to_use: Adding a log or a span; touching infrastructure/observability/; debugging "where does this log come from?"; a use case that "needs to log" (which is usually a signal to use a typed exception or AuditLog instead).
---

# Observability patterns

The codebase has four observability surfaces, each with strict rules about where it can appear.

## 1. Structured logs (structlog)

### Where you can log

| Layer | Allowed? | Why |
|---|---|---|
| `domain/` | NO | The domain is silent. Surface state changes via typed exceptions; the boundary will log them. |
| `application/` | NO | Use cases stay pure for testability. Cross-cutting log lines are added by the `_instrumented` wrapper from the container. |
| `infrastructure/` | YES | Boundary I/O is logged where it happens (repo persisted, http client returned). |
| `presentation/` | YES | Error handlers and request middleware emit access logs and error events. |

If a use case feels like it "needs a log", the right answer is almost always:

* a typed `DomainError` (business event) — the wrapper logs it at WARNING automatically, and `presentation/api/error_handlers.py` returns the matching HTTP error.
* an `AuditLog.record(...)` call (user-facing event) — see `application/audit_log.py`.

### Logger API

```python
import structlog

logger = structlog.get_logger(__name__)

logger.info("user.created", user_id=str(user.id), email=str(user.email))
logger.warning("payment.declined", reason=reason, attempt=attempt)
logger.exception("unexpected_error", path=path)
```

* **Event-style.** First positional arg is a dot-separated event name (`<noun>.<verb_past>`), same convention as domain events (see `transactions-and-events`).
* **Structured kwargs, never f-strings.** The renderer JSON-encodes in prod, pretty-prints in dev.
* **Sensitive keys redacted automatically.** The `_redact_secrets` processor in `infrastructure/observability/logging.py` replaces any key matching `password`, `token`, `authorization`, `secret`, `api_key` (case-insensitive substring) with `***`.

### Format switch — dev vs prod

`LOG_FORMAT` env var, read by `Settings`:

| Value | Renderer | Use |
|---|---|---|
| `console` (default in dev) | `structlog.dev.ConsoleRenderer` with colours | terminal-readable |
| `json` (default in prod containers) | `structlog.processors.JSONRenderer` | one JSON line per event, ingestable by Loki / CloudWatch / Datadog |

## 2. Tracing (OpenTelemetry)

### Auto-instrumentation, shipped

The `configure_tracing` call at app startup wires:

* `opentelemetry-instrumentation-fastapi` — one span per HTTP request, W3C TraceContext propagation
* `opentelemetry-instrumentation-sqlalchemy` — DB spans
* `opentelemetry-instrumentation-asyncpg` — connection-level spans
* `opentelemetry-instrumentation-httpx` — outgoing HTTP calls + trace headers propagation
* `opentelemetry-instrumentation-logging` — `trace_id` and `span_id` injected into structlog events

No code in `application/` or `domain/` touches OTel.

### Use case spans — via the container, not a decorator

Every use case built by the container goes through `_instrumented(use_case, span_name="...")` which:

1. Wraps `execute()` with a `@traced(span_name)` OTel span (opens a span around the body).
2. Adds a try/except that logs `DomainError` raises at WARNING with `code` + `context`, and unexpected exceptions at ERROR with the full stack trace.
3. Re-raises in both cases — the presentation layer maps the exception to HTTP.

**Do NOT** put `@traced` on the use case class — that would force `application/` to import from `infrastructure/observability/`, which is a layer violation. Instrumentation is bolted on from the outside, in `infrastructure/container.py`:

```python
def build_create_user_use_case(*, ...) -> CreateUserUseCase:
    use_case = CreateUserUseCase(...)
    return _instrumented(use_case, span_name="create_user")
```

### Custom spans inside infrastructure

If you need a span around a specific infra block (e.g., a slow SQL helper), `@traced` is fine **inside `infrastructure/`**:

```python
from {{ cookiecutter.package_name }}.infrastructure.observability import traced


@traced("user_repository.find_inactive")
async def find_inactive(self, before: datetime) -> list[User]:
    ...
```

Add attributes via `trace.get_current_span().set_attribute(...)` only when the value is **bounded and meaningful** for debugging — do not dump full payloads.

### Exporter switching

| `OTEL_EXPORTER_OTLP_ENDPOINT` | Behaviour |
|---|---|
| unset | spans go to stdout via `ConsoleSpanExporter` — dev default, CI default |
| set to a URL | OTLP gRPC export to the configured collector |

The devcontainer ships an OTel collector at `http://otel-collector:4317` that forwards to Jaeger; UI on `http://localhost:16686`.

## 3. Metrics (Prometheus)

`prometheus-fastapi-instrumentator` exposes `/metrics` (not in the OpenAPI schema). Out of the box:

* HTTP request count + duration histogram + in-progress gauge, per `(method, handler, status)`
* Process metrics from `prometheus_client` (CPU, memory, fds, uptime)

`/metrics` itself and `/health/*` are excluded from instrumentation to avoid feedback noise. The Helm chart ships a `ServiceMonitor` (gated by `metrics.enabled`) that points a Prometheus operator at it.

Custom metrics go in `infrastructure/observability/metrics.py` (create it when needed). Define counters / histograms at module load using `prometheus_client.Counter` / `Histogram`, label them by `(method, handler, status)` or a similar low-cardinality tuple, increment from infrastructure code.

## 4. Request correlation

Every HTTP request gets a `X-Request-ID` header:

* If the caller sent one, it is preserved (trust upstream).
* Otherwise `RequestIdMiddleware` generates a UUID4 hex.

The id is bound to the structlog context (`structlog.contextvars.bind_contextvars`), so every log line emitted during the request carries `request_id=<uuid>`. The response echoes it back so the caller can correlate.

`AccessLogMiddleware` emits one `http.request` event per non-health-check request with method, path, status, duration_ms, client. That single line is enough to grep the full request chain across services if everyone propagates `X-Request-ID` (httpx auto-propagation: not yet wired by default — set it explicitly when calling out).

## Anti-patterns

| Wrong | Right |
|---|---|
| `print(...)` | use structlog; `print` is caught by ruff `T20` |
| `logging.getLogger(__name__).info(...)` | `structlog.get_logger(__name__).info(...)` so the OTel/redaction processors fire |
| `logger.info(f"user {user.id} created")` | `logger.info("user.created", user_id=str(user.id))` — structured, machine-greppable |
| Logging inside a use case "for visibility" | raise a typed `DomainError` (business event) or call `AuditLog.record(...)` (user-facing event); the wrapper / handler logs technical details |
| `@traced` on a use case class | wrap in the container with `_instrumented` instead; application/ does not import infrastructure/ |
| Adding a span attribute with the full request payload | bounded, low-cardinality values only (user_id, status, error code) |
| New metric defined inside a request handler | define once at module import; only increment at the call site |
