---
name: idempotency-and-retries
description: How the IdempotencyMiddleware lets clients retry POST/PUT/PATCH/DELETE without double-effects. State machine, replay rules, error codes, configuration, limitations, and the manual-cleanup story.
when_to_use: A client retries a write and worries about duplicates; you're debugging a 409/422 with an Idempotency-Key code; you're considering disabling idempotency for a specific deployment; you're adding a write endpoint and want to know what the middleware does for free.
---

# Idempotency & retries

## The contract clients see

Clients add the header `Idempotency-Key: <random-uuid>` on retry-eligible writes (default: POST, PUT, PATCH, DELETE). The header is **client-generated** — a v4 UUID, or any 1–255 char string unique enough that a separate request never collides.

Three outcomes are possible on retry:

| Retry with same key… | Server response |
|---|---|
| ...same method + same path, original completed | Original 2xx/4xx response replayed (handler does NOT run again) |
| ...same method + same path, original still in-flight | `409 IDEMPOTENCY_IN_PROGRESS` (retry later) |
| ...different method or path | `422 IDEMPOTENCY_KEY_MISMATCH` |
| ...key TTL elapsed (default 24h) | Treated as a fresh request, handler runs |

## How it works under the hood

`presentation/api/middleware/idempotency.py` runs between the security headers and the route. It uses its own DB session (separate from the request transaction) so the row commits independently of the handler outcome.

### State machine on ``idempotency_records``

```
client → POST /v1/X  Idempotency-Key: abc-123

middleware:
  INSERT idempotency_records (key='abc-123', status='in_progress', method, path, expires_at)
   │
   ├── IntegrityError (key exists)
   │     └── SELECT existing row:
   │           ├── status='completed' + match → replay original response
   │           ├── status='completed' + mismatch → 422
   │           ├── status='in_progress'         → 409
   │           └── expires_at <= now            → DELETE + recycle as in_progress
   │
   └── success → handler runs → UPDATE status='completed', response_status, response_body
```

The state row therefore goes `in_progress → completed` (or expires `in_progress` if the handler crashes between INSERT and UPDATE, freeing the key after the TTL).

## Configuration

| Setting | Default | What it does |
|---|---|---|
| `IDEMPOTENCY_ENABLED` | `true` | Master switch. `false` skips the middleware entirely. |
| `IDEMPOTENCY_METHODS` | `POST,PUT,PATCH,DELETE` | Comma-separated list of methods that opt in to the middleware. GET / HEAD / OPTIONS are pass-through by design (already idempotent at HTTP semantics level). |
| `IDEMPOTENCY_TTL_SECONDS` | `86400` (24h) | After this delay a row is recycled as fresh. Tune to the slowest legitimate client retry window. |

## Limitations (intentional)

* **No body hash check.** Two retries with the same key and method+path but *different* request bodies will receive the cached response of the first. If body equality matters in your domain, validate at the schema level or enforce uniqueness in the use case.
* **No automatic cleanup.** Expired rows are recycled lazily *when their key is re-used*; rows whose key is never re-tried accumulate. Ship a CronJob or `pg_cron` job per project: `DELETE FROM idempotency_records WHERE expires_at < now() - interval '7 days'`.
* **Streaming responses are not cached** — the middleware reads the body iterator into memory before replay. A `StreamingResponse` reaches the client unchanged but the cached row stores the raw bytes under a `__raw__` key (best-effort replay; do not rely on it).
* **Per-process scoping.** The cache key is the bare ``Idempotency-Key`` string; SOMA assumes clients send random UUIDs so cross-user collisions are impossible. If your clients reuse keys deterministically, scope the key with a per-tenant prefix before sending.

## Client-side patterns

Recommended ``Idempotency-Key`` lifecycle:

* Generate one UUID v4 **per logical action** (the user clicks "Pay" → one key for the whole click, including all transparent retries triggered by the network layer).
* Do NOT regenerate on retry: that defeats the purpose.
* Discard the key after success — re-using on a later, unrelated action collides only by `(method, path)` match, which is unlikely but possible.

## Operational queries

```sql
-- How many keys are currently outstanding?
SELECT status, COUNT(*) FROM idempotency_records GROUP BY status;

-- The oldest in-flight row (suspect handler crash if very old)
SELECT key, method, path, created_at
FROM idempotency_records
WHERE status = 'in_progress'
ORDER BY created_at
LIMIT 1;

-- Manual cleanup
DELETE FROM idempotency_records WHERE expires_at < now() - interval '7 days';
```

## Disabling for one route

There is no per-route opt-out; the middleware is global. Clients control the opt-in by sending — or not — the header. If a single endpoint must never be idempotency-cached even with the header (e.g. an admin reset endpoint that must always run), set `IDEMPOTENCY_ENABLED=false` for that deployment or split the endpoint into a separate service.

## Mistakes to avoid

* **Treating the cached response as authoritative state.** A replay returns the *original* response — if state changed between the original and the retry (another user updated the same resource), the replay is stale. This is by design: the client asked for "the same answer as last time".
* **Using a deterministic key (e.g. `<user_id>:<resource_id>`).** Two unrelated requests with the same composite get falsely deduplicated. Always use a random UUID per action.
* **Returning the cached row from the use case layer.** The middleware handles replay at the presentation boundary — use cases should remain unaware of `Idempotency-Key`. If you need a deeper notion of "this aggregate is being created", track it at the domain level.
* **Forgetting the cleanup CronJob in production.** Without it the table grows unbounded over months. Default TTL is 24h but rows are deleted only on key re-use.
