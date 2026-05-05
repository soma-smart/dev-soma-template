---
name: naming-conventions
description: Uncle Bob strict naming, the role-stereotype whitelist, and the banned generic suffixes.
when_to_use: Naming any class, function, module, or test.
---

# Naming conventions (Uncle Bob strict)

## Universal rules

- **Intention-revealing**: no abbreviations (`usr`, `cnt`, `tmp`).
- **No type encodings**: no `I` prefix on interfaces, no Hungarian, no `m_`.
- **One word per concept**: `get_*` (local lookup), `find_*` (may return None), `load_*` (explicit I/O). Don't mix.
- **Class = noun phrase. Method = verb phrase.**
- **Booleans**: `is_*`, `has_*`, `can_*`. Never negative (`is_not_empty` ⇒ negate `is_empty`).
- **Constants**: `SCREAMING_SNAKE_CASE`, in a `constants.py` per module. No magic numbers (ruff `PLR2004`).

## Banned generic class names

`Manager`, `Processor`, `Handler` (except framework types like `RequestHandler`), `Service` (everything is a service in Clean Architecture — too generic), `Helper`, `Util`, `Data`, `Info`, `Common`, `Misc`, `Worker` (allowed only when paired with a job runner).

## Role-stereotype whitelist

When naming an abstract class, prefer one of these stereotype suffixes — they replace the `Port` suffix:

| Stereotype | Use |
|---|---|
| `…Repository` | Persistence of an aggregate (CRUD + queries) |
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

`…Port` is the **last-resort** suffix when no stereotype above fits. Document why in a docstring.

## Concrete implementations

Prefix by mechanism. Examples:

| Abstract | Production | Test fake |
|---|---|---|
| `UserRepository` | `SqlAlchemyUserRepository` | `InMemoryUserRepository` |
| `Clock` | `SystemClock` | `FrozenClock` |
| `IdGenerator` | `Uuid4IdGenerator` | `SequentialIdGenerator` |
| `RandomSource` | `SystemRandomSource` | `SeededRandomSource` |
| `EmailSender` | `SendGridEmailSender` | `InMemoryEmailSender` |

## Specific suffixes that are kept

- **Use cases**: `…UseCase` (deliberate role marker — `CreateUserUseCase`, not `CreateUser`).
- **Errors**: `…Error` (Pythonic). `…Exception` is fine on stdlib subclasses but prefer `…Error`.
- **Pydantic schemas (presentation)**: `…Schema` (`UserCreateSchema`, `ErrorResponseSchema`).
- **SQLAlchemy models (infrastructure)**: `…Model` (`UserModel`).

## File and folder names

- Snake_case Python files.
- **Plural** for collections: `use_cases/`, `entities/`, `repositories/`.
- **Singular** for concept modules: `clock.py`, `container.py`, `app.py`.

## Tests

- File: `test_<sut_name>.py` mirroring the source layout.
- Function: `test_given_<context>_when_<action>_then_<expectation>` (long is fine — the test is its own spec).
