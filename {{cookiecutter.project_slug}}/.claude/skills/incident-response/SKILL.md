---
name: incident-response
description: Route an alert / symptom / on-call question to the matching playbook in docs/runbooks/. Always cite the playbook section the user should read, then summarise the triage steps and stop — do not speculate beyond the runbook.
when_to_use: User mentions an alert name (OutboxPoisoned, ApiHigh5xxRate, RelayNoReplicasReady, …), a symptom ("DB unreachable", "deploy stuck", "data deleted by mistake"), or asks "what do I do if X". Also when the user pastes a stack trace or kubectl output that screams a known operational failure mode.
---

# Incident response

This service ships two operator runbooks. Your job during an incident is to route the user to the right section, then **stay close to what is written** — runbooks reflect what the team has rehearsed; ad-hoc advice during an incident is how data gets lost.

## The two documents

| File | What it covers |
|---|---|
| `docs/runbooks/backups-and-restore.md` | Backups strategy, retention, restore procedures (PITR per cloud + pg_dump fallback), quarterly verification drill |
| `docs/runbooks/disaster-recovery.md` | Per-scenario playbooks (8 of them, see table below) with Signal / Triage / Mitigation / Resolution / Postmortem |

## Alert → playbook routing

| Alert / Symptom | Playbook section |
|---|---|
| `ApiNoReplicasReady`, "0/N Ready", "ImagePullBackOff", "CrashLoopBackOff" | `disaster-recovery.md` § *API has zero ready replicas* |
| `ApiHigh5xxRate`, "OperationalError", "/health/ready 503", "could not connect to server" | `disaster-recovery.md` § *API cannot reach DB* |
| Helm post-install hook failed, "alembic upgrade" error during deploy | `disaster-recovery.md` § *Migration failed mid-deploy* |
| `OutboxBacklog`, `OutboxLag`, `outbox_oldest_pending_age_seconds` rising | `disaster-recovery.md` § *Outbox backlog growing / lag too high* |
| `OutboxPoisoned`, "status='poisoned' rows" | `disaster-recovery.md` § *Outbox poisoned rows present* |
| "DELETE went too far", "wrong UPDATE in prod", row count dropped | `disaster-recovery.md` § *Accidental data loss* + `backups-and-restore.md` |
| `helm status FAILED`, stuck upgrade, mixed pod versions | `disaster-recovery.md` § *Helm release stuck in failed upgrade* |
| Leaked secret, credentials in a public commit, partner-rotation notification | `disaster-recovery.md` § *Secrets compromised* |
| Cloud provider status page red | `disaster-recovery.md` § *Region / AZ outage* |
| "I need to restore the DB", "we lost data and need backup" | `backups-and-restore.md` § *Restore procedures* |

## What to do in the conversation

1. **Identify the matching playbook section** from the user's signal. If two playbooks could apply (e.g. DB unreachable AND migration failure), name both and ask which one the symptoms match better.
2. **Quote the Triage block verbatim** (it's a checklist; do not paraphrase).
3. **Wait for the triage output** before suggesting mitigation. The Mitigation step depends on which root cause the triage uncovered.
4. **Do not improvise destructive actions.** If the runbook does not have the command the user needs, say so — propose the closest documented command and flag that this is a deviation that should be added to the runbook post-incident.
5. **After the incident**, remind the user to:
   - Add a row to `docs/runbooks/verification-log.md` if a backup restore happened.
   - Update the relevant playbook if the runbook gap caused friction.
   - Add an integration test for the regression that triggered the incident.

## Things NOT to do during an incident

* **Do not run `helm rollback` without checking `helm history`** first. The "last revision" might also be broken.
* **Do not `kubectl delete pod` blindly** — that's just a slower `kubectl rollout restart deployment/...` and skips the deployment's grace period.
* **Do not restore over the live DB** — always restore to a side instance, verify, then swap.
* **Do not suggest "let's check the logs"** without specifying *which* logs. Use the kubectl commands from the matching Triage block.
* **Do not silence the alert before resolving the cause.** The alert is the only signal the service is unhealthy; a silenced alert is a dropped page.

## What to do AFTER

A clean incident leaves three deliverables:

1. **The fix** in code, tested, deployed.
2. **A regression test** that would have caught it (`tests/integration/` or `tests/e2e/`).
3. **A runbook update** if the playbook was incomplete or wrong.

If the team skips #3, the next on-call relives the same incident.
