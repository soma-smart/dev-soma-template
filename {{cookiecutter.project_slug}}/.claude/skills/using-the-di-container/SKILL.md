---
name: using-the-di-container
description: How the DI container is wired (pure-function factories in infrastructure/container.py + Depends wrappers in presentation/api/dependencies/) and how tests override either layer. The container is the single seam between application abstractions and infrastructure concretes.
when_to_use: Adding a use case with new collaborators; introducing a new abstract dependency; debugging a "where does this concrete come from?" question; writing a test that overrides a dependency.
---

# Using the DI container

The container is **pure factory functions** in `infrastructure/container.py`. No DI framework, no magic — just functions that build concrete instances. FastAPI `Depends` wraps each factory in `presentation/api/dependencies/`. Tests override at the `Depends` layer with `app.dependency_overrides`.

This is the **only** seam between `application/` (abstractions) and `infrastructure/` (concretes). Anywhere else, importing from `infrastructure/` in `presentation/` is a layer violation — see `clean-architecture-layers`.

## Factories shipped

The container already ships these (reference them, do not redefine):

| Factory | Returns | Source |
|---|---|---|
| `build_clock()` | `Clock` (production: `SystemClock`) | `infrastructure/container.py` |
| `build_id_generator()` | `IdGenerator` (`Uuid4IdGenerator`) | same |
| `build_random_source()` | `RandomSource` (`SystemRandomSource`) | same |
| `build_database(settings)` | `(AsyncEngine, async_sessionmaker)` | same |
| `build_user_repository(session)` | `UserRepository` (`SqlAlchemyUserRepository`) | same |
| `build_event_bus(session)` | `EventBus` (`SqlOutboxEventBus`) | same |
| `build_create_user_use_case(*, users, clock, ids)` | `CreateUserUseCase` wrapped with `_instrumented` | same |

The matching `Depends` shipped in `presentation/api/dependencies/`:

* `get_settings_dependency`, `get_session`, `get_clock`, `get_id_generator`, `get_random_source` (in `common.py`)
* `get_user_repository`, `get_create_user_use_case` (in `users.py`)

## Adding a new factory

`infrastructure/container.py`:

```python
def build_<noun>_repository(session: AsyncSession) -> <Noun>Repository:
    return SqlAlchemy<Noun>Repository(session)


def build_<action>_<noun>_use_case(
    *,
    <noun>s: <Noun>Repository,
    clock: Clock,
    ids: IdGenerator,
) -> <Action><Noun>UseCase:
    use_case = <Action><Noun>UseCase(<noun>s=<noun>s, clock=clock, ids=ids)
    return _instrumented(use_case, span_name="<action>_<noun>")
```

Every use case factory **must** wrap with `_instrumented(span_name=...)`. The wrapper:

* opens an OTel span around `execute`
* logs `DomainError` raises at `WARNING` with `code` + `context`
* logs unexpected exceptions at `ERROR` with the full stack trace
* re-raises in all cases (the presentation layer maps the exception to HTTP)

This is **the** reason application/ never imports structlog or OpenTelemetry: the wrapper bolts cross-cutting concerns on from the outside.

Factory rules:

* **Pure** — no I/O, no globals (settings flow in as a parameter when needed).
* **Synchronous** unless it has to be async — only the session generator (`get_session`) is async.
* **Composable** — a use case factory takes the repo factory's output as a typed parameter, not a raw `AsyncSession`. The `Depends` wrapper handles the chain.

## Adding the `Depends` wrapper

`presentation/api/dependencies/<noun>.py`:

```python
def get_<noun>_repository(
    session: AsyncSession = Depends(get_session),
) -> <Noun>Repository:
    return build_<noun>_repository(session)


def get_<action>_<noun>_use_case(
    <noun>s: <Noun>Repository = Depends(get_<noun>_repository),
    clock: Clock = Depends(get_clock),
    ids: IdGenerator = Depends(get_id_generator),
) -> <Action><Noun>UseCase:
    return build_<action>_<noun>_use_case(<noun>s=<noun>s, clock=clock, ids=ids)
```

Wire the use case into the route:

```python
@router.post("", response_model=<Noun>ReadSchema, status_code=201)
async def <verb>_<noun>(
    payload: <Noun>CreateSchema,
    use_case: <Action><Noun>UseCase = Depends(get_<action>_<noun>_use_case),
) -> <Noun>ReadSchema:
    output = await use_case.execute(<Action><Noun>Input(...))
    return <Noun>ReadSchema(...)
```

## Tests override at the `Depends` layer

The e2e fixture in `tests/e2e/conftest.py::app` already pre-wires the in-memory Fakes for User. **Most e2e tests do not need to override anything** — they request `client` and the wiring is done.

When you DO need a custom override (simulate a DB outage on `/health/ready`, swap a use case for a hand-built one), do it on the app fixture:

```python
async def failing_session() -> AsyncIterator[AsyncSession]:
    yield StubAsyncSession(raises=OperationalError("db down", params=None, orig=None))

def test_given_db_unreachable_when_calling_ready_then_returns_503(app, client) -> None:
    # GIVEN
    app.dependency_overrides[get_session] = failing_session

    # WHEN
    response = client.get("/health/ready")

    # THEN
    assert response.status_code == 503
```

Pattern: override the `Depends` you want to swap, leave everything else inherited from the fixture.

## Anti-patterns

| Wrong | Right |
|---|---|
| `from {pkg}.infrastructure.persistence.user_repository import SqlAlchemyUserRepository` in a route | `Depends(get_user_repository)` — let the container provide the concrete |
| `Depends(SqlAlchemyUserRepository)` directly | depend on `get_user_repository` — keeps the seam at the factory |
| `build_*_use_case` returns the use case **without** `_instrumented(...)` | always wrap; that is how observability stays out of `application/` |
| Use case takes `Settings` as a constructor parameter | factories read from `Settings`, the use case takes the abstractions only |
| Test mutates a fixture in place across tests | overrides go on the per-test `app.dependency_overrides`, not by mutating fixtures |
| `Depends(lambda: build_user_repository(...))` inline in a route | declare a `get_user_repository` in `presentation/api/dependencies/` and depend on its name |
