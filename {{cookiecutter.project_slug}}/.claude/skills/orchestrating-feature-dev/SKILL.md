---
name: orchestrating-feature-dev
description: Routes feature work between the main agent and the four custom sub-agents (unit-test, integration-test, migration, helm). Used to keep token usage scoped and to enforce that each sub-task runs against its dedicated skill instead of dragging the full skill set into one context.
when_to_use: User asks for a feature touching more than one layer ("add an endpoint that persists X"); the main agent has finished a chunk and wants to delegate the next sub-task; you're about to run mutation testing, helm validation, or alembic round-trip and want to keep that noise out of the main conversation.
---

# Orchestrating feature dev

## When to dispatch vs. do it inline

Dispatch to a sub-agent when **all three** hold:

1. The work has a narrow file scope that maps to one of the four agents.
2. The work will produce noisy tool output (mutmut, alembic, helm render).
3. The sub-agent's skill is the primary reference, not a side concern.

Stay inline when the work is short, cross-cutting, or a quick fix that does
not benefit from a fresh context.

## Agent routing

| The change touches…                                                  | Agent                          | Skills the agent will load          |
| -------------------------------------------------------------------- | ------------------------------ | ----------------------------------- |
| `tests/unit/`, `tests/fakes/`                                        | `soma-unit-test-writer`        | `writing-tests`, `tdd-workflow`     |
| `tests/integration/`                                                 | `soma-integration-test-writer` | `writing-tests`, `database-and-migrations` |
| `alembic/versions/`, `infrastructure/persistence/models.py`          | `soma-migration-writer`        | `database-and-migrations`           |
| `helm/`                                                              | `soma-helm-engineer`           | `writing-a-helm-change`             |
| `domain/`, `application/use_cases/`, `presentation/`                 | **main agent** (this conv)     | `adding-a-use-case`, `writing-domain-code` |
| PR review                                                            | Anthropic `pr-review-toolkit:code-reviewer` + main agent reads `reviewing-a-pr-soma-style` inline | — |

## Standard feature flow

For the canonical SOMA feature ("add an endpoint that persists X"):

1. **Main agent**: design the entity, value objects, use case signature. Write
   the domain code + use case + presentation wiring (router, schema,
   dependencies, error-handler entry, container factory).
2. **Dispatch `soma-migration-writer`** if the entity needs a new table or
   column. Wait for it to finish; it returns the migration file path.
3. **Dispatch `soma-unit-test-writer`** for the use case branches. Brief it
   with: use case name, input/output DTO, branches to cover, Fakes already
   shipped vs. a new Fake required.
4. **Dispatch `soma-integration-test-writer`** if a new repository concrete
   was added. Brief it with the repository class name and the invariants it
   claims.
5. **Main agent**: write the 1 happy + 1 critical e2e test for the endpoint.
6. **Dispatch `soma-helm-engineer`** if the endpoint needs a new env var,
   secret, or probe path change.
7. **Main agent**: run `just lint && just test-all`, draft the commit
   message, confirm CI green.

## Briefing template

Each dispatch MUST include:

```
Context: <1-2 sentences on the feature>
Files you may touch: <explicit scope>
Files you may read (not edit): <list>
Skill to consult first: <name>
Definition of done: <bullet list, measurable>
```

A sub-agent runs in a fresh context: anything not in the briefing is invisible
to it. Skimping on the briefing produces wrong work — overshoot rather than
undershoot.

## Sequential vs. parallel

| Dependency                                                       | Mode               |
| ---------------------------------------------------------------- | ------------------ |
| migration → integration tests of the new repo                    | sequential (migration first) |
| unit tests of the use case ⫫ helm value rename                   | parallel           |
| integration tests ⫫ helm change                                  | parallel           |
| migration ⫫ helm change touching the migration job               | sequential (migration first) |
| any two agents that would edit overlapping files                 | sequential         |

When in doubt, sequential.

## Anti-patterns

- Dispatching `soma-unit-test-writer` for a one-line test fix — orchestration
  overhead beats the gain.
- Dispatching `soma-helm-engineer` for a value rename when no template logic
  changes — main agent edits the value and runs `just helm-lint` in two tool
  calls.
- Asking a sub-agent to do work outside its scope ("write the unit test AND
  fix the use case bug") — the sub-agent will refuse or do it wrong. Split
  the work.
- Running sub-agents in parallel when their work overlaps —
  `soma-migration-writer` and `soma-integration-test-writer` on the same
  repository will conflict; chain them.
- Treating the orchestrator as a way to skip designing the feature — the
  main agent still owns the design. Sub-agents execute scoped sub-tasks; they
  do not architect.
