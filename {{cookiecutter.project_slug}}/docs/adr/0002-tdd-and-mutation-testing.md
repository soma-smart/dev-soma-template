# 2. TDD red-green-refactor + mutation testing

Date: 2026-05-05

## Status

Accepted.

## Context

Coverage % is a misleading proxy for test quality: 100% line coverage with weak assertions still ships bugs. We need a discipline that produces tests strong enough to fail when the production behaviour is wrong, not just "exercised".

## Decision

We follow **strict TDD** (red → green → refactor) with **mutation testing** as a mandatory fourth step on `domain/` and `application/` changes:

1. **Red**: write a failing unit test for the smallest behaviour. The test must fail for the right reason (assertion, not import error).
2. **Green**: write the minimum production code to pass.
3. **Refactor**: clean up while the bar is green.
4. **Mutate**: `uv run mutmut run --paths-to-mutate src/<pkg>/<paths>` on the touched code. Mutants surviving ⇒ tests too lax ⇒ back to step 1 with a new failing test.

CI enforces:
- Coverage ≥ 95% on `domain/` and `application/`.
- Mutation score ≥ 90% on the same.
- A weekly Monday cron that re-runs mutmut on `main` and opens an issue if the score drifts.

The skill `tdd-workflow` describes the loop and is referenced from `CLAUDE.md`.

## Consequences

**Positive**:
- Tests describe behaviour, not implementation. Refactors stay safe.
- The 90% mutation floor catches assertion gaps that pure coverage cannot.
- Onboarding new developers and AI assistants is easier — the rule is explicit and machine-checked.

**Negative**:
- Mutation testing is slow on large code bases. We mitigate by:
  - Scoping `paths_to_mutate` to `domain` + `application` (the layers with logic worth mutating).
  - Excluding `infrastructure/` and `presentation/` (mostly glue / serialisation, low signal).
- The discipline has a learning curve. We compensate with the reference feature in `examples/feature_user_signup/` and the `tdd-workflow` skill.
