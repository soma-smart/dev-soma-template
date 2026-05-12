---
name: naming-conventions
description: Uncle Bob strict naming applied to classes, functions, variables, modules and tests — including the role-stereotype whitelist, the banned generic suffixes, and a verb cheat sheet for the "one word per concept" rule.
when_to_use: Naming any class, function, variable, module, file or test. Reviewing names in a PR.
---

# Naming conventions (Uncle Bob strict)

## Universal rules

* **Intention-revealing.** No abbreviations: `usr`, `cnt`, `tmp`, `repo` (in identifiers), `cfg`, `mgr`. The exception is well-known short forms: `db`, `id`, `url`, `http`.
* **No type encodings.** No `I` prefix on interfaces. No Hungarian (`strName`). No `m_` prefix.
* **One word per concept** — pick a verb and stick with it project-wide. See the cheat sheet below.
* **Booleans**: `is_*`, `has_*`, `can_*`. Never negative (`is_not_empty` → negate `is_empty` at the call site).
* **Names should not lie.** A field called `users` returns a `list[User]`, not a `dict[UserId, User]`. A method `get_user` returns one user, not raises if missing — `find_user` is the one that may return `None`.

## Verb cheat sheet (one word per concept)

| Concept | Verb | Counter-examples (avoid mixing) |
|---|---|---|
| Local lookup, must succeed | `get_<noun>` | `fetch_user`, `retrieve_user` |
| Lookup that may miss | `find_<noun>` | `lookup_user`, `try_get_user` |
| I/O-bound load (DB, HTTP) | `load_<noun>` | `read_user_from_db` |
| Add a new entity to a collection / store | `add(<entity>)` | `insert_user`, `register_user` (when "register" carries no business meaning) |
| Domain registration with a process | `register_<noun>` | use only when registration is a real domain step |
| Create-and-return a fresh instance | `create_<noun>` | use cases follow this for `CreateUserUseCase` |
| Persist-then-fire-events on a new entity | `<verb>_<noun>` use case | the `…UseCase` carries the orchestration, the repo's `add` is plain |
| Remove without history | `delete_<noun>` | |
| Mark inactive while keeping the row | `archive_<noun>` / `deactivate_<noun>` | |
| Pull collection by criterion | `find_<noun>s_by_<field>` | not `get_users_where`, not `list_users_for` |
| Test exists | `<noun>_exists(...)` returning `bool` | not `has_user` if it implies ownership |

Pick one across the whole project. If two terms feel synonymous (`get` and `fetch`), only one is allowed.

## Banned generic class names

`Manager`, `Processor`, `Handler` (except framework types like `RequestHandler`), `Service` (everything is a service in Clean Architecture — too generic), `Helper`, `Util`, `Data`, `Info`, `Common`, `Misc`, `Worker` (allowed only when paired with a job runner: `OutboxRelayWorker`).

If you find yourself reaching for one of these, the actual role is hiding under it — pick a stereotype below.

## Role-stereotype whitelist

When naming a **Protocol** (the application-layer contract), prefer one of these suffixes — they replace the `Port` suffix:

| Stereotype | Use |
|---|---|
| `…Repository` | Persistence of an entity (CRUD + queries) |
| `…Gateway` | Façade over an external SaaS (Stripe, SendGrid, …) |
| `…Bus` | Pub/sub or message routing |
| `…Sender` / `…Publisher` / `…Subscriber` | Outbound / inbound message roles |
| `…Generator` | Produces values (often unique) |
| `…Source` | Pure data provider (random, config, time series) |
| `…Provider` | Lazy resource provider |
| `…Reader` / `…Writer` | I/O over a medium |
| `…Factory` | Builds complex objects |
| `…Strategy` | Interchangeable algorithm |
| `…Validator` | Input validation |
| `…Cache` | Cache storage |
| `…Log` | Writes structured log entries |
| `Clock` / `Lock` / `Mutex` | System primitives (single word) |

`…Port` is the **last-resort** suffix when none of the above fits. Document why in the docstring.

## Concrete implementations

Prefix by mechanism. Reads as "this is the X-flavoured implementation of role Y":

| Abstract role | Production binding | Test Fake |
|---|---|---|
| `UserRepository` | `SqlAlchemyUserRepository` | `InMemoryUserRepository` |
| `Clock` | `SystemClock` | `FrozenClock` |
| `IdGenerator` | `Uuid4IdGenerator` | `SequentialIdGenerator` |
| `RandomSource` | `SystemRandomSource` | `SeededRandomSource` |
| `EmailSender` | `SendGridEmailSender` | `InMemoryEmailSender` |
| `EventBus` | `SqlOutboxEventBus` | `InMemoryEventBus` (when written) |

## Suffixes that ARE kept on purpose

* **Use cases** — `…UseCase` (`CreateUserUseCase`, not `CreateUser`). Deliberate role marker, makes the layer obvious.
* **Errors** — `…Error` (`UserAlreadyExistsError`). `…Exception` only on stdlib subclasses.
* **Pydantic schemas (presentation)** — `…Schema` (`UserCreateSchema`, `ErrorResponseSchema`).
* **SQLAlchemy models (infrastructure)** — `…Model` (`UserModel`). Disambiguates from the domain `User`.

## Repository method naming — methods are business questions

The base `Repository[TEntity, TId]` Protocol ships only the two truly generic methods: `add(entity)` and `find_by_id(id)`. Every other method on a sub-Protocol (e.g. `TodoListRepository`, `UserRepository`) is **added by the use case that needs it**, and its **name must describe a business question, not a SQL operation**. The docstring is the contract — it explains the filter semantics so the persistence binding can implement the right `WHERE` without guessing.

### Anti-pattern table

| ❌ Tech-flat | ✅ Business-shaped | Why |
|---|---|---|
| `get_by_owner(owner_id)` | `list_owned_by(owner_id)` | Verb says "give me all", and `list_*` signals a collection result, not a single row |
| `get_by_id_and_owner(id, owner_id)` | `find_owned_by(owner_id, id)` | The "owned-by" check is the business intent, not a `WHERE owner_id = ? AND id = ?` filter |
| `get_by_name(name)` | `find_active_by_owner_and_name(owner_id, name)` | The active filter is part of the contract (excludes soft-deleted); also scopes by owner because globally unique names rarely make sense |
| `update_email(id, new_email)` | `record_email_change(user, new_email)` | The operation has a business meaning (audit trail, event emission) that the method name should evoke |
| `delete(id)` | `archive(id)` (soft) or `purge(id)` (hard) | Distinguishes two real domain operations under one CRUD verb |
| `check_exists(email)` | `is_email_taken(email)` | Question business, not technical check |
| `count(filter)` | `count_pending_for_owner(owner_id)` | Names the subset being counted; readers don't need to inspect the filter |
| `find_recent(limit)` | `find_recently_active_by_owner(owner_id, since)` | "Recent" without a window is undefined; "by_owner" makes the scope explicit |

### The contract = the docstring

The Protocol's docstring on each method is the **only** brief the persistence binding has. It must explicitly cover:

- What the method returns when the row doesn't exist (`None` vs. empty list vs. raise)
- Which rows are filtered out (soft-deleted? archived? draft state?)
- Whether the result is ordered (and by what)
- Which other Protocol method, if any, this one complements

Example of a complete contract:

```python
class TodoListRepository(Repository[TodoList, TodoListId], Protocol):
    """Persistence contract for the TodoList aggregate.

    Methods carry the ubiquitous language of TodoList ownership and
    lifecycle — names describe business questions, not SQL operations.
    """

    async def find_active_by_owner_and_name(
        self, owner_id: UserId, name: str
    ) -> TodoList | None:
        """Return the non-deleted list named ``name`` owned by ``owner_id``.

        Used by ``CreateTodoListUseCase`` for the uniqueness check before
        creation. Soft-deleted lists are ignored — re-creating a list
        with the same name after deletion is permitted.

        Returns ``None`` when no active list matches.
        """
        ...

    async def list_owned_by(self, owner_id: UserId) -> list[TodoList]:
        """Return all active lists owned by ``owner_id``, oldest first.

        Used by the user's dashboard. Sharee'd lists are NOT included —
        see ``find_shared_with`` for that.
        """
        ...
```

If a use case needs `find_by_id` (without a state filter), use the inherited one. The moment the question carries a state filter ("the active one with this id", "the not-yet-completed one"), prefer a named method.

### Bad smell : a Repository that looks like an ORM

If the Repo has methods like `find_by_X(value)` for every field, you've recreated a generic `Repository[Entity].query(field=value)`. That's a sign the use cases are too thin — they're using the Repo as a "give me a row" facade. The fix is to push the business intent INTO the Repo method names.

## Variables and function arguments

* `email`, not `email_address` — context already says it's an address.
* `user`, not `user_object` — `_object` is noise.
* `user_id` is good; `id` alone is fine inside a class method when the type is clear.
* Plural for collections: `users: list[User]`, never `user_list`.
* Use the **protocol** type for parameters, the **concrete** for locals when the difference matters: `def create(self, repo: UserRepository) -> None:` but `repo = SqlAlchemyUserRepository(session)`.

## File and folder names

* Snake_case Python files.
* **Plural** for collections: `use_cases/`, `entities/`, `repositories/`, `value_objects/`, `dtos/`.
* **Singular** for concept modules: `clock.py`, `container.py`, `app.py`, `outbox.py`.

## Tests

* File: `test_<sut_name>.py` mirroring the source layout (`tests/unit/application/test_create_user_use_case.py`).
* Function: `test_given_<context>_when_<action>_then_<expectation>` — long is fine, the test name is its own spec.
* For the body format (GIVEN / WHEN / THEN comments), see `writing-tests`.

## Constants

* `SCREAMING_SNAKE_CASE` for module-level constants (`DEFAULT_RETENTION_DAYS = 30`).
* Group related constants in a `constants.py` per module (`presentation/api/constants.py`).
* Class-level constants (a `ClassVar`) when they belong to one type — e.g. `DomainError.code`.
* Magic numbers in code are flagged by `ruff PLR2004`. Lift them to a named constant.
