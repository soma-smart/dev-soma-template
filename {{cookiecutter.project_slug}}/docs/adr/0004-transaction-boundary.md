# 4. Transaction boundary aligned with the HTTP request

Date: 2026-05-06

## Status

Accepted.

## Context

A use case may issue several writes (insert the user, insert the audit row, insert the outbox event). Three places could own the commit:

1. **Repository** — `add()` calls `commit()` after `flush()`. Couples the repo to the lifecycle, makes multi-write use cases impossible to keep atomic, and breaks the dependency direction (the repo does not know whether the use case has more work to do).
2. **Use case** — the use case calls `commit()` at the end of `execute()`. Forces every use case to know about persistence, leaks an infrastructure concern into `application/`.
3. **Request boundary** — the FastAPI dependency that produces the session also opens a transaction. Commit on successful return; rollback on any raised exception.

We took option 3.

## Decision

`presentation/api/dependencies/common.py::get_session` opens **both** a session and a transaction:

```python
async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    factory = request.app.state.session_factory
    async with factory() as session, session.begin():
        yield session
```

Consequences for downstream code:

- **Repositories** call `flush()` to surface integrity errors immediately (e.g. `UserAlreadyExistsError`) but never `commit()`. They translate `IntegrityError` to a `DomainError` and re-raise.
- **Use cases** never see transactions. They issue domain operations through the repository and let exceptions bubble.
- **Route handlers** and the use case itself can raise `DomainError` freely — the dependency wrapper rolls back, the registered exception handler converts to the HTTP error response.
- **A single HTTP request = a single transaction.** A use case that needs multiple independent transactions either issues sub-transactions via `session.begin_nested()` (savepoints) or, for cross-process orchestration, persists outbox events that a worker consumes (see ADR 0005).

## Consequences

**Positive**:
- Correctness by default. The previous code path opened a session without `begin()` — writes were silently rolled back at session close. This rewrite fixes that latent bug.
- Atomicity matches user intent: the user either created with everything that hangs off it, or nothing at all.
- The use case stays storage-agnostic.

**Negative**:
- A long-running use case holds the transaction open for its whole duration; we mitigate by capping every request at `request_timeout_seconds` (default 30s) and by keeping use cases thin.
- Read-only endpoints pay a tiny cost opening a transaction they won't use. SQLAlchemy elides empty transactions cheaply, so we accept it.
- Tests that override `get_session` must produce an object that supports `async with session.begin():`. The `StubAsyncSession` shipped in `tests/conftest.py` is fine because the override replaces the whole dependency, not just the inner session.