---
name: using-the-di-container
description: How to add a new factory in infrastructure/container.py and the matching Depends wrapper in presentation/api/dependencies/.
when_to_use: Adding a use case that needs new collaborators; introducing a new abstract dependency.
---

# Using the DI container

The container is **pure functions** in `infrastructure/container.py`. No DI framework. FastAPI `Depends` wraps these functions in `presentation/api/dependencies/`.

## Add a factory

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
    return <Action><Noun>UseCase(<noun>s=<noun>s, clock=clock, ids=ids)
```

Factories must be:

- **Pure**: no I/O, no globals (settings come in as a parameter when needed).
- **Synchronous unless they have to be async** (the session factory yields async).
- **Composable**: a use case factory takes the repo factory's output, not a raw session.

## Add a `Depends` wrapper

`presentation/api/dependencies/<noun>.py`:

```python
def get_<noun>_repository(session: AsyncSession = Depends(get_session)) -> <Noun>Repository:
    return build_<noun>_repository(session)

def get_<action>_<noun>_use_case(
    <noun>s: <Noun>Repository = Depends(get_<noun>_repository),
    clock: Clock = Depends(get_clock),
    ids: IdGenerator = Depends(get_id_generator),
) -> <Action><Noun>UseCase:
    return build_<action>_<noun>_use_case(<noun>s=<noun>s, clock=clock, ids=ids)
```

Use it in a route:

```python
@router.post("")
async def <verb>_<noun>(
    payload: <Noun>Schema,
    use_case: <Action><Noun>UseCase = Depends(get_<action>_<noun>_use_case),
) -> <Noun>ReadSchema:
    ...
```

## Test override

E2E tests override the use case dependency with a hand-built one wired with Fakes:

```python
app.dependency_overrides[get_<action>_<noun>_use_case] = lambda: <Action><Noun>UseCase(
    <noun>s=InMemory<Noun>Repository(),
    clock=FrozenClock(at=...),
    ids=SequentialIdGenerator(),
)
```
