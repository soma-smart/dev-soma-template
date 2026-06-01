## Summary

[What does this PR do and why? Reference the issue/use case it addresses.]

## Type of change

- [ ] `feat` — New feature (use case, endpoint, value object…)
- [ ] `fix` — Bug fix
- [ ] `refactor` — Internal refactor without behaviour change
- [ ] `docs` — Documentation only
- [ ] `test` — Tests only
- [ ] `ci` — CI/CD pipeline
- [ ] `chore` — Maintenance / dependency upgrade

## Test plan

- [ ] Unit tests added (Fakes only, GIVEN/WHEN/THEN)
- [ ] Integration tests added if a new infrastructure piece was wired
- [ ] E2E tests added if a new endpoint was added (1 happy + 1 critical error)
- [ ] `uv run mutmut run` passes the 90% threshold on `domain` + `application`
- [ ] `uv run pre-commit run --all-files` passes locally

## Architecture self-check

- [ ] No third-party imports in `src/<pkg>/domain/`
- [ ] No `datetime.now()` outside `infrastructure/`/`presentation/` boundaries
- [ ] No `float` in `domain/` (use `Decimal` for monetary or precise quantities)
- [ ] New `DomainError` subclasses have an entry in `presentation/api/error_handlers.py::ERROR_HTTP_MAPPING`
- [ ] No log calls inside `domain/` or `application/`
- [ ] Conventional commit messages

## AI assistance

- [ ] Part of this code was AI-assisted
  - If yes, list: [tool / parts / human review notes]

## Linked issues

Closes #
