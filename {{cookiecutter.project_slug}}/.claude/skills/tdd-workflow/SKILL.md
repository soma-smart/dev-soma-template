---
name: tdd-workflow
description: Outside-in TDD — the first failing test sits at the OUTER edge (use case with Fakes), and domain pieces emerge from what the test demands. Strict red-green-refactor with mutmut as the fourth step. Mandatory for any change that affects behaviour in domain/ or application/.
when_to_use: User asks to add a feature, fix a bug, or change logic. Skip this skill only when the change is a pure-refactor (rename, extract, inline) that does not change observable behaviour.
---

# TDD workflow — outside-in

The discipline is **outside-in**: the first failing test you write describes the **feature behaviour**, not an implementation detail. The compiler then tells you what to build — domain pieces emerge as the test demands them, never preemptively.

Cycle stays four steps:
1. Red — outer feature test
2. Green — minimum to pass
3. Refactor under green
4. Add the next branch as a new red — repeat
5. When the use case is behaviourally complete: mutate

## Where the first red goes

| Change | First red test |
|---|---|
| New feature ("create a todolist", "complete a task") | `tests/unit/application/test_<verb>_<noun>_use_case.py` — outer test with Fakes for the use case |
| New rule on an existing entity ("a closed order cannot be shipped") | `tests/unit/application/test_<verb>_<noun>_use_case.py` — outer test exercising the rule via the use case that triggers it |
| Pure-domain invariant that does NOT involve a use case (rare — e.g. an `Email` rejects malformed strings) | `tests/unit/domain/test_<value_object>.py` — inside-out drill, the value object alone |
| Bug fix | The test that REPRODUCES the bug. Usually at the level where the bug was observed. |

The default for a feature is **outer at the use case level**. Don't drop to the entity level unless the rule is genuinely independent of any use case context.

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

## 2. Green — let the imports drive the build order

Build the missing classes in the order the failures expose them. For each one, write the MINIMUM surface that turns the next failure green:

1. `<Action><Noun>UseCase` + `<Action><Noun>Input` + `<Action><Noun>Output` (probably empty bodies / placeholder fields).
2. `<Entity>Repository` Protocol + `InMemory<Entity>Repository` Fake (the Fake is what the test passes in; the Protocol is the type).
3. `<Entity>` domain entity — minimum fields the test references.
4. `<Entity>Id` value object (or any other typed wrapper the entity needs).
5. Wire the use case body until the assertions pass.

The principle: **the test stays the only specification**. Don't add a `priority` field on the entity if no test mentions priority. Don't add a `find_by_email` Protocol method if the current test doesn't need it.

Re-run the test between each step. Eventually it goes green.

## 3. Refactor under green

While the bar is green: rename, extract, inline, deduplicate. After each change, re-run the test. A red bar during refactor means **undo**, not push through.

## 4. Add the next branch — back to red

Each new business rule is a NEW outer test, which forces the next domain piece to emerge:

- "Refuses duplicates per owner" → new test → adds `find_active_by_owner_and_name(...)` to the Protocol + a `<Entity>AlreadyExistsError` domain exception.
- "Emits `<aggregate>.<verb_past>` after creation" → new test asserting `event_bus.published` → wires `await events.publish(...)` in the use case.
- "Refuses an invalid `<field>`" → new test → adds the validation to the value object or entity factory.

NEVER pre-build a Protocol method or an entity field that no test demands.

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

## Inside-out drill — for pure-domain invariants

When a rule has no use case context — for example, `Email("not-an-email")` must raise — the test is at the value object level:

```python
# tests/unit/domain/test_email.py
def test_given_malformed_input_when_constructing_email_then_raises_invalid_email() -> None:
    with pytest.raises(InvalidEmailError):
        Email("not-an-email")
```

Same red-green-refactor-mutate cycle, just no use case in scope. This is the inside-out path; it's rare.

## Hard rules

- **The first failing test is at the OUTER edge** (use case test for a feature). Drop to a domain-level test only for invariants that have no use case context.
- **No production code without a failing test first.** Includes value objects, entities, Protocol methods, Fake methods. The compiler's `ImportError` is your guide.
- **Build minimum.** Don't add a field, a method, or a branch that no test demands.
- **Never disable a failing test to make CI green.** Fix the test or fix the code.
- **Bug fixes follow the same loop.** A bug = a missing outer test. Reproduce it (red), fix it (green), mutate.
- **Mutation step is non-negotiable** when `domain/` or `application/` logic was touched. Line coverage without mutation kill rate is a comforting lie.
