---
name: adding-a-use-case
description: End-to-end walkthrough for adding a new feature — domain types → application use case → infrastructure concretes → presentation route → tests at three levels. Cross-references the User feature shipped in the template as the canonical reference.
when_to_use: User asks for "a new endpoint", "let's implement <verb> <noun>", "add a feature to do X". Pair with tdd-workflow at every step that produces logic.
---

# Adding a use case

A new feature crosses all four layers. The order below matches the dependency direction (domain first, presentation last) and matches what the shipped **User** feature demonstrates file-by-file. Read every step alongside its `User` counterpart — that file IS the worked example.

## 0. Pair with `tdd-workflow`

Every step that produces logic in `domain/` or `application/` is preceded by a failing unit test. The mutation testing step at the end is non-negotiable. See `tdd-workflow` for the loop and `writing-tests` for the test format.

## 1. Domain types

| Need | Where | Base class | User reference |
|---|---|---|---|
| New value object (Email, Money, an ID type, …) | `domain/value_objects/<name>.py` | `ValueObject` + `@dataclass(frozen=True, slots=True)` | `domain/value_objects/email.py`, `domain/value_objects/user_id.py` |
| New entity (User, Order, …) | `domain/entities/<name>.py` | `Entity[<Name>Id]` | `domain/entities/user.py` |
| New business exception | `domain/exceptions/<bounded_context>.py` | `DomainError` (`code` + `default_message`) | `domain/exceptions/user.py` |

For the rules domain code must follow (no third-party, no `datetime.now()`, no `float`, no log), see `writing-domain-code`.

## 2. Application abstractions

| Need | Where | Base | User reference |
|---|---|---|---|
| Persistence for the new entity | `application/repositories/<entity>.py` | `Repository[<Entity>, <Entity>Id]` Protocol — extend it as a sub-Protocol and declare only entity-specific finders; `add` and `find_by_id` are inherited. | `application/repositories/user.py` |
| New cross-cutting collaborator (`EmailSender`, `Cache`, …) | `application/<role>.py` | `typing.Protocol` | none in the User feature |

**Before declaring a new collaborator**, read `adding-a-new-abstraction`. The existing protocols (`Clock`, `IdGenerator`, `RandomSource`, `EventBus`, `AuditLog`, `Repository`) cover most "I need a new port" thoughts.

### Extending a Repository Protocol with business-named methods

The base `Repository[TEntity, TId]` Protocol ships only `add` and `find_by_id`. **Every other method is added by the use case that needs it**, named after the business question being asked, not the SQL operation.

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

## 3. The use case

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

## 4. Unit tests (written FIRST, see step 0)

* `tests/unit/application/test_<action>_<noun>_use_case.py` — exhaustive branch coverage with Fakes from `tests/fakes/`.
* `tests/unit/domain/test_<entity>.py`, `test_<value_object>.py` — invariants of the new domain types.
* Format: GIVEN / WHEN / THEN, see `writing-tests`.
* Run `just test` after each green step.

User reference: `tests/unit/application/test_create_user_use_case.py`, `tests/unit/domain/test_email.py`, `test_user.py`.

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
