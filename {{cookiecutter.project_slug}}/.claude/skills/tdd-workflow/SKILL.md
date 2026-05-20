---
name: tdd-workflow
description: Outside-in TDD + test pyramid + Fakes-only at unit + GIVEN/WHEN/THEN + writing a Fake + mutation testing. The single source of truth for everything that lives under tests/ and for the red-green-refactor loop.
when_to_use: Adding a feature, fixing a bug, writing or reviewing any test under tests/. Adding a new Fake under tests/fakes/. Designing the test suite for a new feature.
---

# TDD workflow — outside-in

The discipline is **outside-in**: the first failing test you write describes the **feature behaviour**, not an implementation detail. The compiler then tells you what to build — domain pieces emerge as the test demands them, never preemptively.

Cycle:
1. Red — outer feature test
2. Green — minimum to pass
3. Refactor under green
4. Add the next branch as a new red — repeat
5. When the use case is behaviourally complete: mutate

---

## Where the first red goes

| Change | First red test |
|---|---|
| New feature ("create a todolist", "complete a task") | `tests/unit/application/test_<verb>_<noun>_use_case.py` — outer test with Fakes for the use case |
| New rule on an existing entity ("a closed order cannot be shipped") | `tests/unit/application/test_<verb>_<noun>_use_case.py` — outer test exercising the rule via the use case that triggers it |
| Pure-domain invariant that does NOT involve a use case (rare — e.g. an `Email` rejects malformed strings) | `tests/unit/domain/test_<value_object>.py` — inside-out drill, the value object alone |
| Bug fix | The test that REPRODUCES the bug. Usually at the level where the bug was observed. |

Default for a feature is **outer at the use case level**. Don't drop to the entity level unless the rule is genuinely independent of any use case context.

---

## 1. Red — write the outer test as if everything existed

Write the test imagining that the use case, the DTO, the repository Protocol, the entity, the value object — ALL already exist. The compiler's import errors will guide the build order.

```python
# tests/unit/application/test_<verb>_<noun>_use_case.py

@pytest.mark.unit
async def test_given_<context>_when_<action>_then_<expectation>() -> None:
    # GIVEN
    repo = InMemory<Entity>Repository()
    use_case = <Action><Noun>UseCase(<collab>=..., ...)

    # WHEN
    output = await use_case.execute(<Action><Noun>Input(...))

    # THEN
    assert <observable outcome>
```

Run the test. Expected first reaction: **ImportError or NameError**. That's correct — that import is the next class to build.

---

## 2. Green — let the imports drive the build order

Build the missing classes in the order the failures expose them. For each one, write the MINIMUM surface that turns the next failure green:

1. `<Action><Noun>UseCase` + `<Action><Noun>Input` + `<Action><Noun>Output` (probably empty bodies / placeholder fields).
2. `<Entity>Repository` Protocol + `InMemory<Entity>Repository` Fake (the Fake is what the test passes in; the Protocol is the type).
3. `<Entity>` domain entity — minimum fields the test references.
4. `<Entity>Id` value object (or any other typed wrapper the entity needs).
5. Wire the use case body until the assertions pass.

The principle: **the test stays the only specification**. Don't add a `priority` field on the entity if no test mentions priority. Don't add a `find_by_email` Protocol method if the current test doesn't need it.

Re-run the test between each step. Eventually it goes green.

---

## 3. Refactor under green

While the bar is green: rename, extract, inline, deduplicate. After each change, re-run the test. A red bar during refactor means **undo**, not push through.

---

## 4. Add the next branch — back to red

Each new business rule is a NEW outer test, which forces the next domain piece to emerge:

- "Refuses duplicates per owner" → new test → adds `find_active_by_owner_and_name(...)` to the Protocol + a `<Entity>AlreadyExistsError` domain exception.
- "Emits `<aggregate>.<verb_past>` after creation" → new test asserting `event_bus.published` → wires `await events.publish(...)` in the use case.
- "Refuses an invalid `<field>`" → new test → adds the validation to the value object or entity factory.

NEVER pre-build a Protocol method or an entity field that no test demands.

---

## 5. Mutate — let mutmut grade the suite

When the use case is behaviourally complete:

```bash
just mutate           # mutmut on domain + application
just mutate-results   # latest report
```

Each surviving mutant is a free hole. For each one:

1. Read the mutation that survived.
2. Write a new failing outer test (or a focused inner test if the mutation is inside an entity method) that would die against that mutation.
3. Re-run the green-red-green cycle.

CI floor: 90% kill rate on `ci-mutation.yml`.

### Kill the obvious survivors before reading the report

Mutmut routinely flags the same three patterns whenever a new use case
is wired up. Adding ~5 targeted tests **before** the first mutmut run
gets the suite to ~90% naturally and lets the report focus on the real
gaps. Pattern check-list for any new ``…UseCase``:

1. **Boundary off-by-one on length / count checks.** For every
   ``if len(x) > N`` (or ``>=``, ``<``, ``<=``), add one test at exactly
   the boundary (``len(x) == N``) that confirms the OTHER side of the
   inequality. Otherwise mutmut flips ``>`` to ``>=`` and survives.

   ```python
   async def test_given_name_exactly_255_chars_when_creating_then_succeeds(...):
       # WHEN length == NAME_MAX_LENGTH, the use case must accept it.
   ```

2. **Context kwargs in ``raise DomainError(...)``.** Every
   ``raise SomeError(key=value)`` mutates to ``raise SomeError(key=None)``
   without changing observable behaviour from the test's
   ``pytest.raises``. Catch them by asserting on ``.context[key]``:

   ```python
   with pytest.raises(InvalidTodoListNameError) as excinfo:
       await use_case.execute(...)
   assert excinfo.value.context["length"] == len(too_long_name)
   ```

   These mutations are semantically benign (the context only feeds the
   structured log), but they count toward the kill rate. Choose
   consistency: either assert systematically, or document that the
   context kwargs are excluded from the kill-rate target — don't mix.

3. **DTO Output fields.** Every ``return SomeOutput(field=value)``
   mutates each ``field=value`` to ``field=None``. Add one assertion
   per field on the return value, or one assertion that compares the
   whole Output to a literal:

   ```python
   output = await use_case.execute(...)
   assert output.id == persisted.id.value
   assert output.name == "Shopping"
   assert output.created_at == frozen_clock.now()
   ```

Run mutmut after these are in place. Real holes (e.g., a missing branch
on the use case body) become much easier to spot in the report once
the routine survivors are gone.

---

## Worked example — "create a todolist" (outside-in)

### Red 1 — outer test, happy path

```python
# tests/unit/application/test_create_todo_list_use_case.py

@pytest.mark.unit
async def test_given_authenticated_owner_when_creating_todolist_then_persists_and_returns_output(
    create_todo_list_use_case: CreateTodoListUseCase,
    todo_list_repository: InMemoryTodoListRepository,
) -> None:
    # GIVEN
    payload = CreateTodoListInput(name="Shopping", owner_id=alice_id)

    # WHEN
    output = await create_todo_list_use_case.execute(payload)

    # THEN
    assert output.name == "Shopping"
    assert len(todo_list_repository.lists) == 1
```

`just test` → `ImportError: cannot import CreateTodoListUseCase`.

### Green 1 — build minimum

In order, until the test goes green:
1. `application/dtos/todo_list.py` with `CreateTodoListInput`, `CreateTodoListOutput`.
2. `application/repositories/todo_list.py` with `class TodoListRepository(Repository[TodoList, TodoListId], Protocol): pass`.
3. `tests/fakes/repositories/todo_list.py` with `InMemoryTodoListRepository` storing `dict[TodoListId, TodoList]`.
4. `domain/value_objects/todo_list_id.py` with `TodoListId` (frozen dataclass around UUID).
5. `domain/entities/todo_list.py` with `TodoList(Entity[TodoListId])` minimum fields: `id`, `name`, `owner_id`.
6. `application/use_cases/create_todo_list.py` with `execute` that adds via repo and returns the output.

`just test` → green.

### Red 2 — refuses duplicates

```python
async def test_given_existing_list_with_same_owner_and_name_when_creating_then_raises_already_exists(
    create_todo_list_use_case,
    todo_list_repository,
) -> None:
    # GIVEN: already a list named "Shopping" for alice
    ...

    # WHEN / THEN
    with pytest.raises(TodoListAlreadyExistsError):
        await create_todo_list_use_case.execute(CreateTodoListInput(name="Shopping", owner_id=alice_id))
```

This adds:
- `TodoListAlreadyExistsError` (domain exception with `code = "TODO_LIST_ALREADY_EXISTS"`).
- `find_active_by_owner_and_name(owner_id, name) -> TodoList | None` on the Protocol AND the Fake.
- The check in the use case body.

`just test` → green again.

### Red 3 — emits `todo_list.created`

```python
async def test_given_valid_input_when_creating_then_publishes_todo_list_created_event(
    create_todo_list_use_case,
    event_bus: InMemoryEventBus,
) -> None:
    await create_todo_list_use_case.execute(CreateTodoListInput(...))
    name, payload = event_bus.published[0]
    assert name == "todo_list.created"
    assert payload["id"] == str(<expected id>)
```

This adds:
- `EventBus` collaborator on `CreateTodoListUseCase.__init__`.
- `await self._events.publish("todo_list.created", {...})` AFTER the write.

`just test` → green.

### Mutate

`just mutate` flips the uniqueness check from `is None` to `is not None`, the event name from `todo_list.created` to `todo_list.creates`, etc. Each surviving mutant is a missing test.

---

## Inside-out drill — for pure-domain invariants

When a rule has no use case context — for example, `Email("not-an-email")` must raise — the test is at the value object level:

```python
# tests/unit/domain/test_email.py
def test_given_malformed_input_when_constructing_email_then_raises_invalid_email() -> None:
    with pytest.raises(InvalidEmailError):
        Email("not-an-email")
```

Same red-green-refactor-mutate cycle, just no use case in scope. This is the inside-out path; it's rare.

---

# Test layout and rules

## Pyramid

```
tests/
├── unit/                  # Fakes only, no I/O. Mutation testing target.
│   ├── domain/            # entities, value objects, exceptions
│   ├── application/       # use cases — the bulk of branches
│   └── presentation/      # invariants on the HTTP mapping, schema parsing
├── integration/           # testcontainers Postgres / Redis. Real systems.
│   └── infrastructure/    # repositories, http clients, mappers
└── e2e/                   # FastAPI booted via TestClient.
    └── api/
```

Per-layer conftests under `tests/conftest.py` (root primitives) + `tests/unit/conftest.py` + `tests/integration/conftest.py` (testcontainers PG) + `tests/e2e/conftest.py` (`app`, `client`, `StubAsyncSession`).

## Hard rules

### 0. Outer drives inner

For a new feature, the **first** failing test is at the use case level (`tests/unit/application/`) with Fakes. Domain-level tests (`tests/unit/domain/`) are added afterwards, only for invariants that the use case test cannot express well on its own. The use case test is the **specification**; the domain test is **drill**. Never the opposite order.

### 1. Fakes-only at unit

Pass an in-memory implementation from `tests/fakes/` to the system under test. **Forbidden** in `tests/unit/`: `unittest.mock`, `Mock`, `MagicMock`, `Spy`, `Stub`, `patch`.

Rationale: a Mock asserts *which* method got called with *which* arguments — that couples the test to the implementation. A Fake asserts that *observable behaviour* happened — the test stays valid through any refactor that preserves behaviour.

If you need to verify a side-effect, the Fake exposes inspectable state. The canonical example is `tests.fakes.repositories.user.InMemoryUserRepository.users` — a dict you read directly to assert "this user was persisted".

### 2. Real systems at integration

Use `testcontainers` (Postgres, Redis) to run actual instances. The `pg_session` fixture in `tests/integration/conftest.py` spawns Postgres 17 once per test session and yields a transaction-rolled-back session per test. **Mock only** what you genuinely cannot self-host (a paid SaaS sandbox API).

Integration tests prove the contract that unit-level Fakes cannot:
- INSERT propagates the unique constraint as a `DomainError`
- `find_by_email` round-trips the entity ↔ ORM model mapping
- the transaction rollback semantics actually rollback

### 3. E2E proves wiring, not branches

For each endpoint: **1 happy path + 1 critical error**. No more.

If a use case has 12 branches, those are 12 unit tests; only 1-2 e2e. Duplicating branches at e2e level is a smell — the right fix is adding a unit test, not adding an e2e.

E2E uses the `client` fixture from `tests/e2e/conftest.py`, which gives a `TestClient` with `dependency_overrides` already wired to the in-memory Fakes. The Fake repository doubles as a Spy: assert against `user_repository.users` after the request.

### 4. GIVEN/WHEN/THEN strict

```python
async def test_given_<context>_when_<action>_then_<expectation>() -> None:
    # GIVEN
    <setup>

    # WHEN
    <single action>

    # THEN
    <assertions>
```

Tolerance: `# WHEN / THEN` combined is allowed only when the WHEN is `pytest.raises`. Enforced by `scripts/checks/test_naming.py`. Annotation form `# GIVEN: <inline note>` is accepted for fixture-driven tests where the GIVEN is fully composed by fixtures.

**One assertion per test, no `@pytest.mark.parametrize`.** A test failure must point to a single behaviour. If you're tempted to parametrize, split into N named tests — the test name carries more meaning that way.

### 5. FIRST principles

- **F**ast — a unit test runs in milliseconds.
- **I**solated — `frozen_clock`, `sequential_ids`, `seeded_random` are the conftest fixtures that buy this.
- **R**epeatable — same input, same output, on any machine.
- **S**elf-validating — a single `assert` line tells you pass/fail.
- **T**imely — write the test before the production code.

---

## Common Fakes shipped with the template

| Abstraction | Production | Fake |
|---|---|---|
| `Clock` | `SystemClock` | `FrozenClock(at=datetime(...))` |
| `IdGenerator` | `Uuid4IdGenerator` | `SequentialIdGenerator(start=1)` |
| `RandomSource` | `SystemRandomSource` | `SeededRandomSource(seed=0)` |
| `UserRepository` | `SqlAlchemyUserRepository` | `InMemoryUserRepository(seed=[...])` |

The root conftest exposes them as fixtures (`frozen_clock`, `sequential_ids`, `seeded_random`, `user_repository`, `create_user_use_case`).

---

## Writing a new Fake

A Fake is a **working** in-memory implementation of an abstraction. It must be:

- **Deterministic** — no clock drift, no random without a seed.
- **Cheap** — no network, no disk.
- **Inspectable** — tests assert on `fake.<state>`.
- **Faithful** — enforces the same invariants as the real binding (uniqueness constraints, validation). A Fake that always returns the happy answer is useless.

### File layout

- `tests/fakes/<name>.py` for primitives (`clock.py`, `id_generator.py`, `random_source.py`).
- `tests/fakes/repositories/<entity>.py` for repositories.

Mirror the production structure under `tests/fakes/`.

### Skeleton

```python
from {{ cookiecutter.package_name }}.application.<module> import <Abstraction>


class InMemory<Abstraction>(<Abstraction>):
    """In-memory fake for tests. Acts as Spy via its public state."""

    def __init__(self, seed: <SeedType> = ()) -> None:
        self.<state>: <Container> = ...

    async def <abstract_method>(self, ...) -> ...:
        # smallest faithful implementation
        ...
```

### Acting as a Spy

```python
fake_email_sender = InMemoryEmailSender()
await use_case.execute(...)
assert fake_email_sender.sent == [Email("alice@example.com")]
```

The assertion is on **observable behaviour** (a message was queued for that recipient), not on implementation details.

### Mistakes to avoid

- Importing from `infrastructure/` in a Fake — couples Fakes to concretes.
- Using `random.*` without a seed.
- Using `datetime.now()` — Fakes of `Clock` accept the time as a parameter.
- Implementing only the happy path — without the uniqueness / validation invariants the real production code enforces, unit tests pass on impossible scenarios.
- Adding a Fake without registering it as a conftest fixture if more than one test will use it.

---

## Hard rules — the loop

- **The first failing test is at the OUTER edge** (use case test for a feature). Drop to a domain-level test only for invariants that have no use case context.
- **No production code without a failing test first.** Includes value objects, entities, Protocol methods, Fake methods. The compiler's `ImportError` is your guide.
- **Build minimum.** Don't add a field, a method, or a branch that no test demands.
- **Never disable a failing test to make CI green.** Fix the test or fix the code.
- **Bug fixes follow the same loop.** A bug = a missing outer test. Reproduce it (red), fix it (green), mutate.
- **Mutation step is non-negotiable** when `domain/` or `application/` logic was touched. Line coverage without mutation kill rate is a comforting lie.
