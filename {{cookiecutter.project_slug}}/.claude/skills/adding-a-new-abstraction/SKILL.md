---
name: adding-a-new-abstraction
description: Decide whether a new abstraction is justified, then ship it across application/, infrastructure/, tests/fakes/ and tests/integration/. Use BEFORE writing the abstract class — most "I need a new port" turns out to be a use of an existing one.
when_to_use: A use case wants a collaborator that does not exist yet (an external SaaS, a crypto primitive, a storage backend, an email sender, a scheduler, a feature-flag source, …). Editing application/<role>.py for what would be a new abstraction.
---

# Adding a new abstraction

## STOP — check the existing ones first

The hardest part is **not** creating a new abstraction. Most "I need a new port" is a use of an existing one. Walk this list before adding anything:

| Existing abstraction | Already covers — common mistakes |
|---|---|
| `Clock` (`application/clock.py`) | "What time is it?" Anything time-based. Never `datetime.now()` instead. |
| `IdGenerator` (`application/id_generator.py`) | New identifier generation (UUID4 in prod, sequential in tests). Don't write a `TokenGenerator` for opaque IDs — wrap or extend `IdGenerator`. |
| `RandomSource` (`application/random_source.py`) | Any random draw (uniform float, integer in range). Don't write a separate `JitterSource`. |
| `EventBus` (`application/event_bus.py`) | **Any** domain event leaving the use case asynchronously. Default binding `SqlOutboxEventBus` writes to the outbox. Don't write a `MessagePublisher` next to it. |
| `AuditLog` (`application/audit_log.py`) | Business-meaningful events ops/end-users will read (not techlogs). Tied to an `actor_id`. Don't write a `UserActivityRecorder`. |
| `<Entity>Repository` (`application/repositories/`) | All persistence for an entity. Add a method (`find_by_status`, `archive`, `count_active`) to the existing repo before writing a new abstraction. |

If the new collaborator fits one of these, the answer is: **add a method to the existing one**. Do not create a new class.

## When a new abstraction IS justified

The collaborator must satisfy all three:

1. **Real external dependency or system primitive.** Calls out of the process (network, disk, kernel-backed crypto) **OR** a non-deterministic primitive you must fake in tests.
2. **Not a refinement of an existing role.** "Send a password-reset email" is the existing `EmailSender`, not a new abstraction. "Hash a password with Argon2" *is* new — it is unrelated to messaging.
3. **The use case would survive a swap.** If you replaced the production binding tomorrow (SendGrid → Mailgun, Redis → DynamoDB), the use cases must not change. If only one implementation will ever exist and it is library-specific, keep the code concrete in `infrastructure/` — no abstraction needed.

Common legitimate new abstractions:

| Need | Stereotype | Class name |
|---|---|---|
| Send email / SMS / Slack | `Sender` | `EmailSender`, `SmsSender` |
| Call a paid SaaS (Stripe, Mailgun) | `Gateway` | `StripeGateway` |
| Hash / sign / verify | primitive (single word) | `PasswordHasher`, `TokenSigner` |
| Read or write blobs | `Reader` / `Writer` | `BlobReader`, `BlobWriter` |
| Cache lookup | `Cache` | `<Entity>Cache` |
| Run something later | `Scheduler` | `Scheduler` |
| Read a feature flag | `Source` | `FeatureFlagSource` |

`…Port` is the **last-resort** suffix — use it only when no stereotype fits, and document why in the docstring. See `naming-conventions`.

## How to add one — checklist

The walkthrough below follows the pattern with `EmailSender`. Replace `EmailSender` with your role and you're done.

### 1. Abstract — `application/<role>.py`

Pure Python, no third-party imports. The contract is a `typing.Protocol` — structural typing keeps the application layer dependency-free and avoids ABC ceremony. Concrete bindings may inherit explicitly for documentation; Fakes that quack the right shape are accepted by the type checker either way.

```python
# application/email_sender.py
from typing import Protocol

from {{ cookiecutter.package_name }}.domain.value_objects.email import Email


class EmailSender(Protocol):
    """Sends transactional and notification emails."""

    async def send(self, *, to: Email, subject: str, body_html: str) -> None:
        """Deliver one email. Must be idempotent — a retried send is safe."""
        ...
```

### 2. Production binding — `infrastructure/<role>.py`

Prefix the class by mechanism. Real third-party calls happen here.

```python
# infrastructure/email_sender.py
class SendGridEmailSender(EmailSender):
    """Production binding backed by SendGrid REST."""

    def __init__(self, *, api_key: str, http: httpx.AsyncClient) -> None: ...
    async def send(self, *, to, subject, body_html) -> None: ...
```

### 3. Fake — `tests/fakes/<role>.py`

The Fake doubles as Spy via inspectable state. Read `writing-tests` for the full Fake rules.

```python
# tests/fakes/email_sender.py
class InMemoryEmailSender(EmailSender):
    """Records sends in ``self.sent`` for assertion."""

    def __init__(self) -> None:
        self.sent: list[SentEmail] = []

    async def send(self, *, to, subject, body_html) -> None:
        self.sent.append(SentEmail(to=to, subject=subject, body_html=body_html))
```

### 4. Container factory — `infrastructure/container.py`

```python
def build_email_sender(settings: Settings) -> EmailSender:
    return SendGridEmailSender(
        api_key=settings.sendgrid_api_key.get_secret_value(),
        http=httpx.AsyncClient(timeout=10.0),
    )
```

### 5. FastAPI dependency — `presentation/api/dependencies/<noun>.py`

```python
def get_email_sender(settings: Settings = Depends(get_settings_dependency)) -> EmailSender:
    return build_email_sender(settings)
```

Use cases that need it then take it as a constructor parameter; their use-case-specific factory injects it via `Depends(get_email_sender)`.

### 6. Settings — `infrastructure/config/settings.py`

Add the env var. Use `SecretStr` for credentials so they never leak into logs.

```python
sendgrid_api_key: SecretStr = Field(...)
```

### 7. Conftest fixture (if reused)

If more than one test will use the Fake, register it in `tests/conftest.py` so tests can take it as a parameter:

```python
@pytest.fixture
def email_sender() -> InMemoryEmailSender:
    return InMemoryEmailSender()
```

### 8. Integration test for the production binding (if it does I/O)

If the production binding makes real network calls or hits a self-hostable service, write an integration test that exercises it:

* `tests/integration/infrastructure/test_<role>.py`
* Use testcontainers if the dependency is self-hostable; mock only for SaaS sandboxes that cannot be reproduced locally.
* Format: GIVEN / WHEN / THEN, one test per edge case.

For pure-CPU primitives (a `PasswordHasher` backed by `argon2-cffi`), the unit-level tests on the production class itself are enough.

### 9. ADR (only when the choice is committing)

Write `docs/adr/NNNN-<title>.md` only when the abstraction commits the project to a particular pattern that is hard to undo:

* "Outbox-backed `EventBus` rather than direct broker call" → ADR.
* "Argon2id over bcrypt for `PasswordHasher`" → no ADR (impl detail, swappable).
* "All `Cache` reads go through Redis with a write-through pattern" → ADR.

## Self-check before opening the PR

- [ ] I walked the existing-abstractions table at the top — none cover this.
- [ ] The role passes all three justification criteria (external + not a refinement + survivable swap).
- [ ] The class name uses a role stereotype, not `Port`.
- [ ] The abstract has zero third-party imports.
- [ ] The production binding lives in `infrastructure/`, named by mechanism.
- [ ] A Fake exists in `tests/fakes/` and exposes inspectable state.
- [ ] At least one unit test on a use case exercises the new collaborator through the Fake.
- [ ] If the production binding does I/O, an integration test exercises it against a real (testcontainers / sandbox) target.
- [ ] If the choice is structurally committing, an ADR is in flight.
