---
name: adding-a-new-abstraction
description: Decide whether a new abstraction is justified, then add it cleanly through application/, infrastructure/ and tests/fakes/. Use this BEFORE writing a new abstract class.
when_to_use: A use case needs a collaborator that does not exist yet (an external SaaS, a crypto primitive, a storage backend, an email sender, a scheduler, ...). Editing application/<role>.py for a new abstraction.
---

# Adding a new abstraction

## STOP — check the existing ones first

The hardest part is **not creating a new abstraction**. Most "I need a new port" turns out to be a use of an existing one.

Walk the list before adding anything new:

| Existing abstraction | Already covers |
|---|---|
| `Clock` (`application/clock.py`) | Anything that asks "what time is it?". TZ-aware UTC. **Never** use `datetime.now()` instead of this. |
| `IdGenerator` (`application/id_generator.py`) | Generation of new identifiers (UUID4 in prod, sequential in tests). Don't write a `TokenGenerator` for opaque IDs — extend `IdGenerator` or wrap it. |
| `RandomSource` (`application/random_source.py`) | Any random draw (uniform float, integer in range). Crypto-strength in prod, seeded in tests. Don't write a separate `JitterSource`. |
| `EventBus` (`application/event_bus.py`) | **Any** domain event leaving the use case asynchronously. The default binding (`SqlOutboxEventBus`) writes to the outbox table; a worker forwards. Don't write a `MessagePublisher` next to it. |
| `AuditLog` (`application/audit_log.py`) | User-meaningful events that ops or end users will read (not just techlogs). Tied to a `actor_id`. Don't write a `UserActivityRecorder`. |
| `<Entity>Repository` (`application/repositories/`) | All persistence for an aggregate. Add a method on the existing repo (`find_by_status`, `archive`) before writing a new abstraction. |

If the new collaborator fits one of those, the answer is: **add a method to the existing abstraction**, do not create a new one.

## When a new abstraction IS justified

The collaborator must be:

1. **A real external dependency** that calls out of the process (network, disk, crypto primitive backed by hardware) **OR** a system primitive whose behaviour you need to fake in tests for determinism.
2. **Not a refinement** of an existing role. (E.g., "send password-reset email" is **not** a new abstraction; it is a method on the same `EmailSender` that sends every other email. "Hash a password with Argon2" **is** new — it is unrelated to messaging.)
3. **Replaceable** by a different mechanism without rewriting use cases. If it is so specific to one library that no other implementation makes sense, it is infrastructure code, not an abstraction — keep it concrete.

Common legitimate new abstractions and their stereotype:

| Need | Stereotype | Class name |
|---|---|---|
| Send email / SMS / Slack | `Sender` | `EmailSender`, `SmsSender` |
| Call a paid SaaS (Stripe, SendGrid) | `Gateway` | `StripeGateway` |
| Hash / sign / verify | (none — primitive) | `PasswordHasher`, `TokenSigner` |
| Read or write blobs | `Reader` / `Writer` | `BlobReader`, `BlobWriter` |
| Cache lookup | `Cache` | `<Entity>Cache` |
| Run something later | `Scheduler` | `Scheduler` |
| Read a feature flag | `Source` | `FeatureFlagSource` |

`…Port` is the **last-resort** suffix — only when no role stereotype fits, and document why in the docstring.

## How to add one (when justified)

1. **Abstract** in `application/<role>.py`. Pure Python, no third-party imports.

   ```python
   # application/email_sender.py
   from abc import ABC, abstractmethod

   from {{ cookiecutter.package_name }}.domain.value_objects.email import Email


   class EmailSender(ABC):
       """Sends transactional and notification emails on behalf of a user."""

       @abstractmethod
       async def send(self, *, to: Email, subject: str, body_html: str) -> None:
           """Deliver one email. Idempotent: a retried send must be safe."""
   ```

2. **Production binding** in `infrastructure/<role>.py`, prefixed by the mechanism.

   ```python
   # infrastructure/email_sender.py
   import httpx

   from {{ cookiecutter.package_name }}.application.email_sender import EmailSender
   from {{ cookiecutter.package_name }}.domain.value_objects.email import Email


   class SendGridEmailSender(EmailSender):
       """Production binding backed by SendGrid REST."""

       def __init__(self, *, api_key: str, http: httpx.AsyncClient) -> None:
           ...

       async def send(self, *, to: Email, subject: str, body_html: str) -> None:
           ...
   ```

3. **Fake** in `tests/fakes/<role>.py`. The Fake doubles as Spy via its public state.

   ```python
   # tests/fakes/email_sender.py
   from dataclasses import dataclass, field

   from {{ cookiecutter.package_name }}.application.email_sender import EmailSender
   from {{ cookiecutter.package_name }}.domain.value_objects.email import Email


   @dataclass
   class SentEmail:
       to: Email
       subject: str
       body_html: str


   class InMemoryEmailSender(EmailSender):
       """Records sends in ``self.sent`` for assertion."""

       def __init__(self) -> None:
           self.sent: list[SentEmail] = []

       async def send(self, *, to: Email, subject: str, body_html: str) -> None:
           self.sent.append(SentEmail(to=to, subject=subject, body_html=body_html))
   ```

4. **Container factory** in `infrastructure/container.py`.

   ```python
   def build_email_sender(settings: Settings) -> EmailSender:
       return SendGridEmailSender(api_key=settings.sendgrid_api_key.get_secret_value(), http=...)
   ```

5. **FastAPI dependency** in `presentation/api/dependencies/<noun>.py` (or `common.py` if shared).

   ```python
   def get_email_sender(settings: Settings = Depends(get_settings_dependency)) -> EmailSender:
       return build_email_sender(settings)
   ```

6. **Settings entry** in `infrastructure/config/settings.py` (env var, `SecretStr` for credentials).

7. **Conftest fixture** if any test needs the Fake by default — see the existing `user_repository`, `frozen_clock` patterns.

8. **ADR** (`docs/adr/NNNN-<title>.md`) when the abstraction commits the project to a particular pattern (an outbox-backed `Sender`, a multi-tenant `Cache`, etc.). Skip the ADR for standard cases.

## Self-check before opening the PR

- [ ] I read the table at the top and confirmed no existing abstraction covers this.
- [ ] The class name uses a role stereotype, not `Port`.
- [ ] The abstract has zero third-party imports.
- [ ] The production binding lives in `infrastructure/`, named after the mechanism.
- [ ] A Fake exists in `tests/fakes/` and exposes inspectable state.
- [ ] At least one unit test on the use case exercises the new collaborator through the Fake.
