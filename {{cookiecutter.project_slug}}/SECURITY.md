# Security policy

## Reporting a vulnerability

If you have found a security issue in {{ cookiecutter.project_name }}, **please do not open a public GitHub issue**. Send a private report instead:

- **Email**: {{ cookiecutter.author_email }} (subject: `SECURITY: <short description>`)
- Or use the GitHub *"Report a vulnerability"* button on this repository's *Security* tab (Private vulnerability reporting).

Include in your report:

- A clear description of the vulnerability and the impact you observed.
- A minimal reproducer (request payload, sequence of operations, environment).
- The commit hash or release version where you discovered the issue.
- Optional: a proposed mitigation, if you have one in mind.

## Coordinated disclosure

We commit to:

1. **Acknowledge** receipt within **3 business days**.
2. Provide a **first technical assessment** within **10 business days** — severity, affected versions, expected fix timeline.
3. Coordinate a **fix and disclosure date**. We aim to ship a fix within **30 days** of assessment for high-severity issues; we will keep you informed of any delay.
4. **Credit** you in the changelog and the GitHub Security Advisory unless you ask to remain anonymous.

Please give us a reasonable opportunity to fix the issue before any public disclosure. We do not have a bug bounty programme, but we are happy to discuss recognition on a case-by-case basis.

## Supported versions

| Version | Status |
| --- | --- |
| `main` | Actively supported. Security patches are released as soon as a fix is ready. |
| Tagged releases | Only the latest tagged minor (`vX.Y.*`) receives security patches. Older minors require an upgrade. |

## Out of scope

The following are intentionally **not** treated as security issues by this project:

- Vulnerabilities in dependencies that already have a published fix and a Dependabot PR open against this repo (please review the open PR rather than file a new report).
- Self-inflicted misconfigurations (e.g. running with `DB_URL` pointing to a public Postgres without network restrictions).
- Findings on a fork that has materially diverged from upstream.

## Hardening checklist for downstream operators

- Run only signed images (verify with `cosign verify` — see `docs/architecture.md`).
- Pin to specific release tags, never `:latest`, in production.
- Subscribe to GitHub *Security advisories* for this repository.
- Rotate all secrets injected via `Settings` (DB credentials, API tokens) regularly.
- Keep the Helm chart's `securityContext` defaults intact (`runAsNonRoot`, dropped capabilities, read-only root filesystem).
