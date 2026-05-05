---
name: adding-a-use-case
description: End-to-end walkthrough for adding a new feature (use case + endpoint) crossing all four layers. Use whenever the user asks to add a feature, endpoint, or use case.
when_to_use: User asks for "a new endpoint", "a feature to do X", "let's implement Y use case".
---

# Adding a use case

Reference: `examples/feature_user_signup/` (or trace `CreateUserUseCase` in the codebase). Follow this order — it matches the dependency direction.

## 0. Pair with `tdd-workflow`

Every step that produces logic in `domain/` or `application/` is preceded by a failing unit test. Skipping this is not allowed.

## 1. Domain types

| Need | Where |
|---|---|
| New value object (Email, Money, …) | `domain/value_objects/<name>.py` |
| New entity (User, Order, …) | `domain/entities/<name>.py` |
| New business exception | `domain/exceptions/<bounded_context>.py` (subclass `DomainError`) |

## 2. Application abstractions

| Need | Where |
|---|---|
| New repository | `application/repositories/<entity>.py` (abstract class, name = `EntityRepository` — no `Port` suffix; see `naming-conventions`) |
| New collaborator | `application/<role>.py` (e.g., `email_sender.py` → class `EmailSender`) |

## 3. The use case itself

`application/use_cases/<verb>_<noun>.py`:

```python
class <Action><Noun>UseCase:
    def __init__(self, *, <collab1>: <Type1>, <collab2>: <Type2>) -> None: ...
    async def execute(self, input: <Action><Noun>Input) -> <Action><Noun>Output: ...
```

DTOs in `application/dtos/<noun>.py` as `@dataclass(frozen=True, slots=True)`.

## 4. Tests (written FIRST, see step 0)

- `tests/unit/application/test_<action>_<noun>_use_case.py` — exhaustive branches with Fakes from `tests/fakes/`.
- Run `uv run pytest -m unit` after each green.

## 5. Infrastructure concretes

- `infrastructure/persistence/models/<noun>.py` — SQLAlchemy `…Model`
- `infrastructure/persistence/<noun>_repository.py` — concrete repo (`SqlAlchemy<Noun>Repository`) with private `_to_entity` / `_to_model`
- New abstract collaborator → concrete in `infrastructure/<role>.py` (e.g., `infrastructure/email_sender.py`)
- Migration: `uv run alembic revision --autogenerate -m "add_<noun>"` — see `database-and-migrations`

## 6. DI container

`infrastructure/container.py`:

```python
def build_<noun>_repository(session: AsyncSession) -> <Noun>Repository: ...
def build_<action>_<noun>_use_case(*, ...) -> <Action><Noun>UseCase: ...
```

## 7. Presentation

- `presentation/api/dependencies/<noun>.py` — `Depends` wrappers around the container factories
- `presentation/api/schemas/<noun>.py` — Pydantic `…Schema`
- `presentation/api/v1/<noun>.py` — router. Wire it in `presentation/api/app.py` via `app.include_router(...)`.

## 8. Error mapping

If you added a new `DomainError`, register it in `presentation/api/error_handlers.py::ERROR_HTTP_MAPPING`. The unit test `tests/unit/presentation/test_error_mapping.py` will fail otherwise.

## 9. E2E

`tests/e2e/api/test_<verb>_<noun>_endpoint.py` — **1 happy + 1 critical error**. Do NOT re-test the use case branches at this level — they are already covered by the unit tests.

## 10. Verify

```bash
bash scripts/checks/quality.sh
uv run pytest
uv run mutmut run --paths-to-mutate src/{{ cookiecutter.package_name }}/domain,src/{{ cookiecutter.package_name }}/application
```
