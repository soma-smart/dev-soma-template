---
name: orchestrating-feature-dev
description: Routes work between the main agent (architect) and the eight custom sub-agents. The main agent designs contracts (Protocols, DTOs, events, errors) and dispatches feature-level builders (use-case / persistence / route) that produce vertical slices from a business intent brief. Tech-narrow agents (migration / helm / event-sourcing / test-writers) remain for surgical tasks.
when_to_use: User asks for a feature ("crée CreateTodoList qui refuse les doublons par owner"); the main agent finishes the design phase and is ready to dispatch builders; a surgical task arises (one migration, one alert, one regression test); you need to clarify which agent owns a given concern before dispatching.
---

# Orchestrating feature dev

## The mental model

The **main agent is an architect**. It designs the feature: Protocol shape, DTO fields, event names + payloads, domain exceptions, status codes. It then dispatches **feature-level builders** that produce the vertical slice for one layer each:

```
User: "Crée CreateTodoList qui refuse les doublons par owner."
                            │
                            ▼
              ┌──────────────────────────┐
              │ MAIN AGENT (architect)   │
              │ - reads this skill       │
              │ - designs Protocol shape │
              │   + DTO + events + errors│
              │ - writes briefs          │
              └──────────────┬───────────┘
                             ▼
           ┌─────────────────┴─────────────────┐
           │                                   │
  ┌────────▼─────────┐                ┌────────▼──────────┐
  │ soma-use-case-   │  (sequential,  │ soma-persistence- │  } parallel
  │ builder          │   in first)    │ builder           │  } once use-case-
  │ domain + applic. │                │ infra/persistence │  } builder done
  │ + Fake + unit T  │                │ + migration + integ│
  └──────────────────┘                └───────────────────┘
                                       ┌───────────────────┐
                                       │ soma-route-       │
                                       │ builder           │
                                       │ schema + route +  │
                                       │ wiring + e2e      │
                                       └───────────────────┘
```

The main agent does **NOT** write production code (use case body, repository impl, route handler). It writes the briefs that let the builders do it. It only touches production code for **cross-cutting** concerns (`adding-a-new-abstraction` for a new Protocol like `EmailSender`, `error_handlers.py` mapping that the route-builder defers).

## Agent catalog

### Feature-level (vertical-slice builders)

| Agent | Owns | Input from main agent |
|---|---|---|
| `soma-use-case-builder` | domain/, application/, tests/unit/, tests/fakes/ | business intent (what does this use case do?), Protocol method shapes (business-named), event payload, exceptions+codes |
| `soma-persistence-builder` | infrastructure/persistence/, alembic/versions/, tests/integration/ | the Protocol (the builder reads docstrings as contract), column schema, soft-delete strategy |
| `soma-route-builder` | presentation/api/, container.py (additions), tests/e2e/ | HTTP method+path, auth requirement, idempotency flag, status-code mapping per outcome |

### Tech-narrow (surgical tasks)

| Agent | Owns | Use case |
|---|---|---|
| `soma-migration-writer` | alembic/versions/ | schema change INDEPENDENT of a new repo (alter column, add index, data migration) |
| `soma-helm-engineer` | helm/ | chart edits |
| `soma-event-sourcing-bootstrapper` | scaffolds 4 ES files for one entity | architect has decided an entity goes ES |
| `soma-unit-test-writer` | tests/unit/ only | fill coverage gap on EXISTING code, regression for a bug fix |
| `soma-integration-test-writer` | tests/integration/ only | fill coverage gap on EXISTING repo |

## Routing — what does the user want?

| The user says / asks for… | Main agent does… |
|---|---|
| « Crée une feature X » (intent métier nouveau) | Designs Protocol shape + DTO + event names + errors. Dispatches `soma-use-case-builder` first, then `soma-persistence-builder` + `soma-route-builder` in parallel. |
| « Ajoute un endpoint qui expose X » (use case déjà existant) | Dispatches `soma-route-builder` seul. |
| « Implémente le repo de X » (Protocol existe déjà) | Dispatches `soma-persistence-builder` seul. |
| « Ajoute un test sur Y existant » | Dispatches `soma-unit-test-writer` ou `soma-integration-test-writer` selon la couche. |
| « Migre la table Z » (changement de schéma indépendant) | Dispatches `soma-migration-writer`. |
| « Change la conf Helm » | Dispatches `soma-helm-engineer`. |
| « Event-source W » | Confirms with the user via the decision table in `event-sourcing-pattern`, then dispatches `soma-event-sourcing-bootstrapper`. |
| « Ajoute un EmailSender / NotificationSender / Hasher » | Inline (main agent reads `adding-a-new-abstraction`, writes the Protocol + Fake + null impl). |
| « Fais une review de cette PR » | Anthropic `pr-review-toolkit:*` + main agent reads `reviewing-a-pr-soma-style`. |

## The main agent's design phase — what to produce before dispatching

For a feature dispatch (`soma-use-case-builder` + `soma-persistence-builder` + `soma-route-builder`), the main agent first writes (in its own context, in this conversation) a **design brief** with:

1. **Entity** : nom, fields, value objects nécessaires.
2. **Domain rules** : invariants, state machine, exceptions à raise (avec leur `code` SCREAMING_SNAKE).
3. **Repository Protocol skeleton** : nom de classe + méthodes business-named que le use case va demander (avec une ligne décrivant l'intent business de chaque méthode). Voir `naming-conventions` § "Repository method naming".
4. **DTO** : Input et Output shape.
5. **Event** : nom (`<aggregate>.<verb_past>`) + payload exact si le use case publie.
6. **HTTP** : method + path + auth + status codes par outcome.

Cette design phase est **dans la conversation**, pas en fichiers. Elle sert de base pour les briefs des builders.

## Briefing template — un brief par builder

Chaque brief est **self-contained** : aucun « comme on en a parlé », aucune référence implicite à la conversation. Le builder runs in a fresh context.

### Brief pour `soma-use-case-builder`

```
Build the <Name>UseCase.

Business intent:
- <one paragraph: what the use case does, in business terms>

Input DTO fields:
- field_a: <type>, <constraints> (e.g. "1-255 chars")
- field_b: ...

Output DTO shape:
- <fields>

Domain rules to enforce (each raises a named DomainError):
- <rule 1> → <ExceptionClass> (code: SCREAMING_SNAKE)
- <rule 2> → ...

Event emitted (if any):
- name: <aggregate>.<verb_past>
- payload: <flat dict shape>

Repository methods you'll need (extend the Protocol with business-named methods):
- TodoListRepository.add(todo_list) — inherited
- TodoListRepository.find_active_by_owner_and_name(owner_id, name) → TodoList | None
  - Used for: <one-line intent>
  - Filter contract: ignores soft-deleted lists
- ... (one per business question the use case asks)

Other collaborators:
- Clock, IdGenerator, EventBus (and any cross-cutting Protocol that exists)

Skills to read first: adding-a-use-case, tdd-workflow, writing-tests,
writing-domain-code, naming-conventions (section "Repository method naming"),
adding-a-domain-exception, transactions-and-events (if events).

Deliverables: domain entity (if new), value objects (if new), exceptions (if new),
application/repositories/<entity>.py (Protocol skeleton if new + business methods),
application/dtos/<entity>.py, application/use_cases/<verb>_<noun>.py,
tests/fakes/repositories/<entity>.py, tests/unit/application/test_<verb>_<noun>_use_case.py.

Verify: pytest -m unit green; mutmut on touched paths ≥ 90%;
scripts/checks/no_third_party_in_domain.py + test_naming.py clean.
```

### Brief pour `soma-persistence-builder`

```
Implement the SQLAlchemy persistence for <Name>Repository.

Read application/repositories/<entity>.py first — implement EVERY method
the Protocol declares, exactly as its docstring prescribes (the docstring
is the WHERE-clause contract; do not invent semantics).

Entity domain class: src/<pkg>/domain/entities/<entity>.py (already built).

Schema:
- table <entities>: <column list with types, NOT NULL, default>
- indexes: <list>
- unique constraints: <list, including "WHERE deleted_at IS NULL" for partial>
- foreign keys: <list with ON DELETE behavior>

Soft-delete column: deleted_at TIMESTAMPTZ NULL (SOMA convention).

IntegrityError translation:
- On (owner_id, name) duplicate → raise <Entity>AlreadyExistsError
- ... (one per uniqueness constraint)

Skills to read: database-and-migrations, writing-tests (integration section).

Deliverables: alembic/versions/<NNNN>_init_<entities>.py (curated + roundtrip),
infrastructure/persistence/models/<entity>.py, infrastructure/persistence/
<entity>_repository.py, tests/integration/infrastructure/test_<entity>_
repository.py (one test per Protocol method invariant).

Verify: just migrate → migrate-down → migrate clean; ci-migration-drift
yields empty migration body; pytest -m integration on touched paths green.
```

### Brief pour `soma-route-builder`

```
Expose <Name>UseCase over HTTP.

HTTP semantics:
- Method: <POST/PUT/PATCH/DELETE/GET>
- Path: /v1/<resource>[/{id}[/<sub>]]
- Auth: authenticated (default) | public (justify) | role-restricted: <roles>
- Idempotency: yes (POST/PUT typically) | no (PATCH/DELETE typically)

Request body fields (Pydantic schema):
- <field>: <type>, <Pydantic constraint>
- ...

Response body (Pydantic schema):
- status 201/200: <fields>

Error mapping (DomainError → HTTP):
- <ExceptionClass> → <status> <code>
  (if any are NOT yet in ERROR_HTTP_MAPPING, add them in error_handlers.py)

The use case is at application/use_cases/<verb>_<noun>.py (already built).
Its Input DTO is at application/dtos/<entity>.py.

Skills to read: using-the-di-container, adding-auth, idempotency-and-retries
(if idempotent), writing-tests (e2e section).

Deliverables: presentation/api/schemas/<entity>.py (request + response),
presentation/api/v1/<entity>.py (router), presentation/api/dependencies/
<entity>.py (Depends wrappers), container.py (additions: build_<verb>_<noun>_
use_case), app.py (include_router), error_handlers.py (additions if new
exceptions), tests/e2e/api/test_<resource>_endpoint.py (1 happy + 1 critical).

Verify: pytest -m e2e -k <resource> green; just lint clean.
```

## Sequential vs. parallel between builders

| Dependency | Mode |
|---|---|
| `soma-use-case-builder` → anyone else | sequential (must finish first) |
| `soma-persistence-builder` ⫫ `soma-route-builder` (after use-case-builder) | **parallel** |
| `soma-migration-writer` ⫫ `soma-helm-engineer` (on unrelated targets) | parallel |
| Any two builders editing overlapping files | sequential |
| `soma-route-builder` → `soma-route-builder` (two routes same resource) | sequential |

When in doubt, sequential. The cost of a missed parallelism is 30s; the cost of an overlap is a debugging session.

## Anti-patterns

- **Main agent writing the use case body inline.** That's the use-case-builder's job. Main agent only does cross-cutting (a new shared Protocol, `error_handlers.py` mapping).
- **Brief that says "comme dans CreateUser".** A sub-agent has no memory of CreateUser. State the contract explicitly.
- **Dispatching a builder without designing the Protocol shape first.** The builder will invent method names, drift away from business naming, and you'll re-do the work.
- **Dispatching `soma-unit-test-writer` for a new use case.** That's the use-case-builder's job (tests included). The test-writer is for surgical additions to existing code.
- **Dispatching two builders in parallel on the same files.** They'll conflict. Use case → first; persistence + route → parallel only when use case is done.
- **Asking a builder to do work outside its scope** (e.g., route-builder modifying the use case body). The builder refuses; rebrief or split.
- **Treating the orchestrator as a way to skip designing.** The main agent is the architect; builders execute the design. Skip the design phase and the briefs are nonsense.

## When the user prompt is vague

If the user says « crée CreateTodoList » without specifying the rules, the main agent **asks clarifying questions** before designing. Specifically:

- What fields are on the input?
- What invariants does the use case enforce? (uniqueness scope, validation rules)
- Does it emit an event? Which payload?
- Idempotent endpoint?
- Public or authenticated?

A single short Q&A turn is cheaper than three rounds of misdirected building. The builders are expensive — they should fire on a complete brief.
