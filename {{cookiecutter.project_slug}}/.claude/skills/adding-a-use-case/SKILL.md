---
name: adding-a-use-case
description: End-to-end walkthrough for adding a new feature — domain types → application use case → infrastructure concretes → presentation route → tests at three levels. Cross-references the User feature shipped in the template as the canonical reference.
when_to_use: User asks for "a new endpoint", "let's implement <verb> <noun>", "add a feature to do X". Pair with tdd-workflow at every step that produces logic.
---

# Adding a use case (outside-in)

A new feature crosses all four layers. The discipline is **outside-in**: start from the feature description, write the failing outer test (use case with Fakes), let domain pieces emerge as the test demands them. NEVER pre-build VOs, entities, or Protocol methods that no test requires.

The shipped **User** feature is the file-by-file reference; cross-link each section with its `User` counterpart.

## 0. State the feature in one sentence

Before opening any file:

> *« As an authenticated user, I want to <do X> by providing <Y>. The system must <rule 1>. After success, <observable outcome / event>. »*

Write it down (in the PR description, in your scratchpad, in a doc). Each clause becomes either a unit test branch or a non-functional concern (auth, idempotency, observability).

## 1. Pair with `tdd-workflow` and write the outer test first

Open `tests/unit/application/test_<verb>_<noun>_use_case.py` and write the test as if every class and method already existed. The compiler's `ImportError` chain is your build plan. See `tdd-workflow` for the loop and `writing-tests` for the GIVEN/WHEN/THEN format.

The outer test references the things you'll build, **in their final names**:
- The `<Action><Noun>UseCase` class
- Its DTOs (`<Action><Noun>Input`, `<Action><Noun>Output`)
- The `InMemory<Entity>Repository` Fake
- The entity + value objects the assertions touch

Run the test. Get an `ImportError`. That's correct — the next file you create is the missing import.

## 2. Let the domain emerge — reference for "where does each piece go"

As the outer test imports things, you create them under these layers. **Don't open these files until the test demands them.**

### Domain (emerges first, because the Fake stores entities)

| Emerges when… | Where | Base | User reference |
|---|---|---|---|
| The test stores entity instances in the Fake | `domain/entities/<name>.py` | `Entity[<Name>Id]` | `domain/entities/user.py` |
| The entity needs a typed identifier or a constrained scalar (Email, Money, …) | `domain/value_objects/<name>.py` | `ValueObject` + `@dataclass(frozen=True, slots=True)` | `domain/value_objects/email.py`, `user_id.py` |
| The test calls `pytest.raises(<X>Error)` | `domain/exceptions/<bounded_context>.py` | `DomainError` (`code` + `default_message`) | `domain/exceptions/user.py` |

For the rules domain code must follow (no third-party, no `datetime.now()`, no `float`, no log), see `writing-domain-code`.

### Application (emerges next, because the use case is the Outer Test SUT)

| Emerges when… | Where | Base | User reference |
|---|---|---|---|
| The Fake stores something — you need a Protocol to type-hint it | `application/repositories/<entity>.py` | `Repository[<Entity>, <Entity>Id]` Protocol — start empty; add business-named methods only when a test forces them. | `application/repositories/user.py` |
| The use case body needs a collaborator that doesn't exist yet (`EmailSender`, `Cache`, …) | `application/<role>.py` | `typing.Protocol` | none in the User feature |

**Before declaring a new collaborator**, read `adding-a-new-abstraction`. The existing protocols (`Clock`, `IdGenerator`, `RandomSource`, `EventBus`, `AuditLog`, `Repository`) cover most "I need a new port" thoughts.

### Extending a Repository Protocol with business-named methods

The base `Repository[TEntity, TId]` Protocol ships only `add` and `find_by_id`. **Every other method is added by the test that needs it** (outside-in), named after the business question being asked, not the SQL operation. You don't add a method preemptively because "we'll probably need it"; you add it when the next red test refers to it.

A use case that needs to check "is this name available for this owner?" adds:

```python
class TodoListRepository(Repository[TodoList, TodoListId], Protocol):
    """Persistence contract for the TodoList aggregate.

    Methods carry the ubiquitous language of TodoList ownership and lifecycle.
    """

    async def find_active_by_owner_and_name(
        self, owner_id: UserId, name: str
    ) -> TodoList | None:
        """Return the non-deleted list named ``name`` owned by ``owner_id``.

        Used by CreateTodoListUseCase for the uniqueness check before
        creation. Soft-deleted lists are ignored.
        """
        ...
```

Naming rules (full table + anti-pattern examples in `naming-conventions`):

- The method name is a **business question**, not a SQL recipe. `find_active_by_owner_and_name` over `get_by_owner_and_name`.
- The **docstring is the contract** — explains which rows are filtered out (soft-deleted? archived?), what's returned when nothing matches, and which other Protocol method it complements.
- When the use case is built, the Fake repo under `tests/fakes/repositories/` MUST implement the new method so the unit tests run. The persistence binding picks it up later via its own builder.

A common mistake: dumping a `find_by_X(value)` for every field on the Repo. That's an ORM with extra steps. If the use case can express the question in business terms, the method should be named in business terms.

## 3. The use case body

`application/use_cases/<verb>_<noun>.py`:

```python
from {{ cookiecutter.package_name }}.application.use_cases.base import UseCase


class <Action><Noun>UseCase(UseCase[<Action><Noun>Input, <Action><Noun>Output]):
    """One-line summary including the exceptions it may raise."""

    def __init__(self, *, <collab1>: <Type1>, <collab2>: <Type2>) -> None:
        self._<collab1> = <collab1>
        self._<collab2> = <collab2>

    async def execute(self, input: <Action><Noun>Input) -> <Action><Noun>Output:
        ...
```

User reference: `application/use_cases/create_user.py`.

The `UseCase[TInput, TOutput]` generic surfaces input/output types at the class header. Cross-cutting concerns (OTel span, structured warning/error log on raise) are added by `_instrumented` in `infrastructure/container.py` — **never** inside the use case body. See `transactions-and-events` if the use case publishes a domain event.

### DTOs

`application/dtos/<noun>.py`:

```python
@dataclass(frozen=True, slots=True)
class <Action><Noun>Input:
    ...

@dataclass(frozen=True, slots=True)
class <Action><Noun>Output:
    ...
```

User reference: `application/dtos/user.py` (`CreateUserInput`, `CreateUserOutput`).

## 4. Next branches — each new business rule is a new outer red

After the happy-path test is green, each additional rule (refuses duplicates, emits an event, validates a field) is a NEW outer test that forces the next domain piece to emerge. Examples:

- "Refuses duplicates per owner" → adds a Protocol method + a `<Entity>AlreadyExistsError` + the check in the use case body.
- "Emits `<aggregate>.<verb_past>`" → adds `EventBus` to `__init__` + `await self._events.publish(...)` after the write.
- "Validates the input field" → either at the value object level (`<Field>Error` raised in `__post_init__`) or at the use case (a domain exception raised explicitly).

Inner unit tests (`tests/unit/domain/`) are added only for invariants that the use case test can't easily express — e.g. an entity's `complete()` is idempotent if and only if it's not already completed. Pure-domain drill.

After each green: `just test`. When the use case is behaviourally complete, `just mutate` and kill surviving mutants.

User reference: `tests/unit/application/test_create_user_use_case.py` (outer), `tests/unit/domain/test_email.py`, `test_user.py` (inner).

## 5. Infrastructure concretes

| Need | Where | User reference |
|---|---|---|
| SQLAlchemy ORM model | `infrastructure/persistence/models/<noun>.py` (suffix `…Model`) | `infrastructure/persistence/models/user.py` |
| Concrete repository | `infrastructure/persistence/<noun>_repository.py` (`SqlAlchemy<Noun>Repository`) with private `_to_entity` / `_to_model` | `infrastructure/persistence/user_repository.py` |
| New abstract collaborator's binding | `infrastructure/<role>.py` (`SendGrid<Role>`, `S3<Role>`, …) | none |
| DB schema migration | `just migration "add_<noun>"` then **read** the autogenerated revision before committing — see `database-and-migrations` | `alembic/versions/0001_init_users.py` |

## 6. Integration tests for the new repository

* `tests/integration/infrastructure/test_<noun>_repository.py` — at least: happy `add` + `find_by_id`, integrity violation translated to the right `DomainError`, missing-id returns `None`. One distinct test per edge case (no `parametrize`).
* Format: GIVEN / WHEN / THEN.
* Use the `pg_session` fixture from `tests/integration/conftest.py`.
* Run `just test-integration` (Docker required — testcontainers spawns Postgres).

User reference: `tests/integration/infrastructure/test_user_repository.py`.

## 7. DI container

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

User reference: `build_user_repository`, `build_create_user_use_case` already in `infrastructure/container.py`.

## 8. Presentation

| Need | Where | User reference |
|---|---|---|
| Pydantic schemas (request + response) | `presentation/api/schemas/<noun>.py` (suffix `…Schema`) | `presentation/api/schemas/user.py` |
| `Depends` wrappers around container factories | `presentation/api/dependencies/<noun>.py` | `presentation/api/dependencies/users.py` |
| Versioned router | `presentation/api/v1/<noun>.py` | `presentation/api/v1/users.py` |
| Wire the router | add `app.include_router(<noun>_v1.router)` in `presentation/api/app.py`, after `app.include_router(health_router)` | already there for users |

## 9. Error → HTTP mapping

If the use case raises a **new** `DomainError`, register it in `presentation/api/error_handlers.py::ERROR_HTTP_MAPPING`. The unit test `tests/unit/presentation/test_error_mapping.py` auto-discovers via `DomainError.__subclasses__()` and fails otherwise — no test to write.

If the use case raises an **existing** `DomainError` and you want a different HTTP status, that means you actually want a new error type — extract one. Don't override `ERROR_HTTP_MAPPING` per-use-case.

## 10. E2E test

`tests/e2e/api/test_<verb>_<noun>_endpoint.py` — **1 happy + 1 critical error**. Do NOT re-test use case branches here; they are already covered at the unit level. The `client` fixture from `tests/e2e/conftest.py` gives a `TestClient` with the in-memory Fakes pre-wired.

User reference: `tests/e2e/api/test_create_user_endpoint.py`.

## 11. Verify

```bash
just lint        # ruff + ty + 4 architectural lints + format
just test-all    # unit + integration + e2e (Docker required for integration)
just mutate      # mutmut on domain + application; CI enforces ≥ 90 % kill rate
```

Open the PR. CI runs the same checks plus `ci-image-scan` (Trivy + SBOM), `ci-helm` (lint + kubeconform + polaris) and `ci-migration-drift` (autogenerate diff).
