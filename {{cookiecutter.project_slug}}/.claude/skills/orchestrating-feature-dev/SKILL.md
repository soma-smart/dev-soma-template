---
name: orchestrating-feature-dev
description: Routes work between the main agent (architect) and the eight custom sub-agents. The main agent designs contracts (Protocols, DTOs, events, errors) and dispatches feature-level builders (use-case / persistence / route) that produce vertical slices from a business intent brief. Tech-narrow agents (migration / helm / event-sourcing / test-writers) remain for surgical tasks.
when_to_use: User asks for a feature ("crée CreateTodoList qui refuse les doublons par owner"); the main agent finishes the design phase and is ready to dispatch builders; a surgical task arises (one migration, one alert, one regression test); you need to clarify which agent owns a given concern before dispatching.
---

# Orchestrating feature dev

## The enrichment pattern — short user prompt, behavioral plan, short brief

The user typically asks for features in one line:

> *« Je veux pouvoir créer une TodoList, une seule par personne, avec un nom et une description »*

That single line is NOT a brief you forward to a builder verbatim. The main agent **enriches it into a behavioural plan** the user can validate — but the enrichment is strictly **outside-in**: it lists what's **testable** and what's **externally observable**, never what classes/methods will exist inside the domain.

### What goes in the enriched plan

The plan contains exactly these five sections:

1. **Tests that will be written** — the behavioural cases that drive the implementation, expressed in GIVEN/WHEN/THEN at the use case level (e.g. "given an authenticated user with no list, when they create one with a valid name, then the list is persisted and an event is emitted"). One bullet per branch the user cares about. This is the **specification**.

2. **Abstractions needed — by role, never by name** — list the *roles* of the collaborators the use case will lean on (e.g. "a repository for the new entity", "an event bus", "the existing Clock and IdGenerator"). Do **NOT** write `TodoListRepository` or `find_active_by_owner_and_name`. The builder names everything.

3. **API surface — one line unless it gets weird** — `<METHOD> <path>`, the auth scheme (`authenticated`, `public`, `role:<x>`), the status codes for each outcome, and the idempotency flag. Elaborate **only** when something non-obvious is at play: a non-trivial translation between request body and use case input, a custom auth flow, a multi-aggregate orchestration that affects status codes, etc. In the default boring case, the API line is 30 seconds of reading.

4. **External contracts that ARE pre-decided** — event name (the `<aggregate>.<verb_past>` literal), event payload semantics ("the consumer must be able to identify the new list, its owner, …"), HTTP status code per outcome, error code mapping. These are observable by third parties (consumers, clients) and must be stable, so the main agent commits to them BEFORE the builder fires.

5. **Behavioural questions to clarify** — anything the prompt left ambiguous that changes observable behaviour: soft-delete vs hard-delete (affects "can I recreate after deletion?"), validation bounds, how the actor identity arrives in the use case, multi-tenancy scope, retry semantics. Each question is a fork the user must answer before dispatch.

### What does NOT go in the plan

- Class names (no "TodoList entity", no "TodoListId VO")
- Protocol method signatures (no "find_active_by_owner_and_name")
- Exception names or codes (the builder picks them per `naming-conventions`)
- Entity field lists (the builder adds a field when a test demands it)
- DTO field lists (same)

These are **internal** and emerge from the tests during implementation. If the main agent pre-decides them, it has committed to a shape before any test red, which is anti-TDD and defeats the discipline the builder is supposed to apply.

### The flow

1. Read the skills you need (`adding-a-use-case`, `tdd-workflow`, `naming-conventions`, `transactions-and-events`, …).
2. Produce the five-section enriched plan above. Keep it under one page.
3. Show the plan to the user and wait for validation. Address the behavioural questions explicitly.
4. On the user's OK, dispatch the builder with a **short brief** (~10 lines): the user story, the available collaborators, the wrapper for commands, the external contracts (event name + payload semantics + status codes), and what to report. The builder runs in a fresh context, applies its outside-in skills, and emerges the rest.

Why this layering: the user can correct the **behaviour** BEFORE expensive builder work fires; the builder receives only what it needs to act and is free to apply the discipline its skills prescribe; the main agent absorbs the conversation history (the builder must not).

## The mental model

The **main agent is the behaviour-and-contract negotiator**. It clarifies WHAT must be true, names the EXTERNAL contracts (event names, status codes), and dispatches builders that produce the vertical slice via strict outside-in TDD. The main agent does **NOT** design the internal shape (class names, Protocol methods, exception names, entity fields) — that emerges from the tests the builder writes.

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

### Brief pour `soma-use-case-builder` (short — ~10 lines)

The builder has TDD outside-in, naming, mutation, and file placement in its own skills. The brief states the feature in business terms and points to the existing collaborators. No need to spell out the deliverable list — the builder's `.md` covers that.

```
Build the "<short feature title>" feature.

User story:
<2-3 sentences of feature behaviour and rules — duplicates, validation,
events, etc. Phrased from the user's POV. The builder picks the names.>

Available collaborators (Protocols already shipped in application/):
Clock, IdGenerator, EventBus, CurrentUser, and the existing
<reference feature> entity/repository for naming conventions.

Run Python tooling via /tmp/<bake-dir>/run.sh <cmd>.

Report: files touched, mutation rate, Protocol methods added (with
business intent), domain exceptions created (with codes), anything
outstanding for the persistence-builder or route-builder.
```

The user story is the ONLY contract — the builder derives the DTO shape, the entity fields, the Protocol method names, and the exception names from there. You as the main agent will have already validated those choices via the enriched plan you showed the user.

### Brief pour `soma-persistence-builder` (short)

```
Implement the SQLAlchemy persistence for the <Entity> aggregate.

The Repository Protocol is at application/repositories/<entity>.py —
implement EVERY method as its docstring prescribes (the docstring is
the WHERE-clause contract; do not invent semantics).

Schema:
- <one-line column summary: types, NOT NULL, soft-delete column>
- Unique constraint: <if any, e.g. "(owner_id, name) WHERE deleted_at IS NULL">
- Foreign keys: <if any, with ON DELETE behaviour>

On IntegrityError from a uniqueness violation, raise <Entity>AlreadyExistsError.

Run Python tooling via /tmp/<bake-dir>/run.sh <cmd>.

Report: migration roundtrip status, Protocol methods implemented,
integration tests written, anything outstanding.
```

The builder has the rest in its own skills.

### Brief pour `soma-route-builder` (short)

```
Expose <Name>UseCase over HTTP.

HTTP semantics:
- <METHOD> <path>
- Auth: <authenticated | public | role-restricted: <roles>>
- Idempotency: <yes (POST/PUT) | no>

Status codes per outcome:
- 201/200 happy: <one line on the response shape>
- <status> on <ExceptionClass> (add to ERROR_HTTP_MAPPING if missing)
- <repeat per error>

The use case lives at application/use_cases/<verb>_<noun>.py; its
Input/Output DTOs are in application/dtos/<entity>.py.

Run Python tooling via /tmp/<bake-dir>/run.sh <cmd>.

Report: files touched, mapping additions, e2e tests written.
```

The builder has Pydantic schema patterns, container factory style, dependency wiring, and e2e fixture usage in its own skill.

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
