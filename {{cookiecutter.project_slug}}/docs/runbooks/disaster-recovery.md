# Disaster recovery playbooks

One playbook per failure mode. Each follows the same structure so you can scan fast:

* **Signal** — what tells you this is happening (alert name, log pattern, user report)
* **Triage** (~5 min) — immediate diagnosis
* **Mitigation** (~15 min) — stop the bleeding
* **Resolution** — full fix
* **Postmortem** — what to document afterward

Cross-reference: `docs/runbooks/backups-and-restore.md` for anything that needs DB restoration.

---

## API has zero ready replicas

**Signal**: `ApiNoReplicasReady` alert; users see connection refused / timeouts; `kubectl get pods` shows 0/N Ready.

**Triage**:
```bash
kubectl get pods -n {{ cookiecutter.project_slug }} -l app.kubernetes.io/component=api
kubectl describe pod <one-of-them>      # ImagePullBackOff ? CrashLoopBackOff ?
kubectl logs <pod> --tail=100
kubectl logs <pod> --previous --tail=100  # if it just crashed
```

Common root causes, in order of frequency:

1. **ImagePullBackOff** — wrong tag, registry creds rotated. Fix: revert to the previous tag, redeploy.
2. **CrashLoopBackOff** — startup error: bad config, missing secret, DB unreachable, schema mismatch. Logs tell you which.
3. **Readiness probe failing** — app booted but `/health/ready` reports DB unreachable. Jump to "API cannot reach DB" playbook below.
4. **Node pressure** — pods pending because no node has capacity. `kubectl describe pod` mentions `FailedScheduling`.

**Mitigation**:
- If the previous image was healthy: `helm rollback {{ cookiecutter.project_slug }} <previous-revision>` (find with `helm history`).
- If it's a config issue: revert the values overlay and `helm upgrade`.

**Resolution**: fix the root cause, ship a corrected release.

**Postmortem**: if the bad image passed `ci-quality`, the gap was in the integration tests or the migration drift check — add the missing test.

---

## API cannot reach DB

**Signal**: `/health/ready` returns 503; logs show `OperationalError: could not connect to server`; `ApiHigh5xxRate` alert.

**Triage**:
```bash
# Is the DB pod up?
kubectl get pods -l app=postgres
# Or cloud-managed: check the cloud console / `aws rds describe-db-instances ...`

# Can the API resolve the DB host from inside the pod?
kubectl exec deploy/{{ cookiecutter.project_slug }} -- nc -vz $DB_HOST 5432

# Did the credentials change?
kubectl get secret {{ cookiecutter.project_slug }}-secrets -o jsonpath='{.data.DB_URL}' | base64 -d
```

Common root causes:

1. **DB connection pool exhausted** — too many requests, pool maxed out. Symptom: intermittent timeouts. Fix: scale up `DB_POOL_SIZE`, redeploy.
2. **NetworkPolicy regression** — a recent change blocked the namespace's egress to the DB. `kubectl get networkpolicies`.
3. **DB instance restarted** (cloud maintenance window). Usually self-heals in 1-2 min.
4. **DNS issue** — cluster CoreDNS hiccup. `kubectl exec` and `nslookup`.

**Mitigation**:
- Restart the API pods so they re-open the pool: `kubectl rollout restart deployment/{{ cookiecutter.project_slug }}`.
- If DB is truly down and ETA is long: post a status banner; consider a maintenance page via the Ingress.

**Resolution**: depends on the root cause; the cloud DB console gives the events history.

---

## Migration failed mid-deploy

**Signal**: `helm upgrade` job hook fails; pods stuck in `Init`; logs from the migration job show an Alembic error.

**Triage**:
```bash
kubectl logs job/{{ cookiecutter.project_slug }}-migrations
kubectl exec deploy/{{ cookiecutter.project_slug }} -- uv run alembic current
```

**Mitigation** (decide based on what got applied):

* **Migration didn't start** (e.g. lock conflict): re-run the deploy after fixing the conflict.
* **Migration partially applied**: roll back the schema using the matching downgrade.
  ```bash
  # From a pod with the new image (the previous image may not know the new downgrade):
  kubectl run -it --rm migrate-fix --image=$NEW_IMAGE -- \
    sh -c 'DB_URL=$DB_URL uv run alembic downgrade -1'
  ```
* **Migration applied but app crashes on the new schema** (rare): `helm rollback` to the previous release; the schema is one step ahead. Either ship a no-op migration to bring the model in line, or write a corrective migration.

**Resolution**: fix the migration, run the upgrade/downgrade/upgrade roundtrip locally (the `database-and-migrations` skill describes this), ship the fixed migration.

**Postmortem**: a failed migration on prod usually means the migration was not tested against prod-shaped data. Update the integration tests with a fixture that mirrors prod-volume + prod-distribution.

---

## Outbox backlog growing / lag too high

**Signal**: `OutboxBacklog` or `OutboxLag` alert; `outbox_oldest_pending_age_seconds` gauge in Grafana.

**Triage**:
```bash
# Is the relay alive?
kubectl get pods -l app.kubernetes.io/component=relay
kubectl logs deploy/{{ cookiecutter.project_slug }}-relay --tail=200

# What is the backlog shape?
psql $DB_URL <<'SQL'
SELECT status, COUNT(*), MIN(created_at) AS oldest
FROM outbox_events
GROUP BY status;
SQL
```

Common root causes:

1. **Relay is not running** (zero pods, crashloop) — fix the relay first; consume the backlog.
2. **All handlers are failing** on the head-of-line row — `last_error` column tells you the cause. Fix the handler / downstream, redeploy.
3. **Producer is outpacing the relay** — scale up `relay.replicaCount`. `SELECT FOR UPDATE SKIP LOCKED` makes this safe.
4. **Single poison row at the head** blocking the order — see "outbox poisoned rows" playbook below.

**Mitigation**:
- Scale up the relay: `kubectl scale deploy/{{ cookiecutter.project_slug }}-relay --replicas=3`.
- If a poison row is blocking: manual replay or quarantine (see below).

**Resolution**: address the handler regression or the downstream outage.

---

## Outbox poisoned rows present

**Signal**: `OutboxPoisoned` alert (critical).

**Triage**:
```sql
SELECT id, event_name, last_error, attempts, last_attempt_at
FROM outbox_events
WHERE status = 'poisoned'
ORDER BY last_attempt_at DESC
LIMIT 10;
```

For each row, decide:

* **Bad payload** (the producer wrote a malformed event): emit a compensating action manually, then delete the poison row.
* **Transient downstream outage** (now resolved): manual replay.
  ```sql
  UPDATE outbox_events
  SET status='pending', attempts=0, next_attempt_at=NULL, last_error=NULL
  WHERE id = '<row-uuid>';
  ```
* **Permanent incompatibility** (handler will always fail on this payload): archive to a side table and delete.
  ```sql
  CREATE TABLE IF NOT EXISTS outbox_poison_archive AS TABLE outbox_events WITH NO DATA;
  INSERT INTO outbox_poison_archive SELECT * FROM outbox_events WHERE id = '<row-uuid>';
  DELETE FROM outbox_events WHERE id = '<row-uuid>';
  ```

**Resolution**: if the poison was caused by a handler regression, ship the fix AND replay the affected rows.

See `building-a-feature` § "Transactions and events" for the lifecycle and compensating-event pattern (Saga).

---

## Accidental data loss (DELETE / UPDATE on too many rows)

**Signal**: a user / engineer reports rows disappeared; the audit log shows a `DELETE` they did not intend.

**Triage** (fast):
1. **Stop writes**: `kubectl scale deploy/{{ cookiecutter.project_slug }} --replicas=0`. Damage in progress means each second adds rows to the loss.
2. Note the UTC timestamp just before the bad operation. The structured logs have it.

**Mitigation**:
- Restore via PITR to a SIDE instance — see `backups-and-restore.md` § "Partial restore".
- Copy the affected rows back to production inside a transaction.
- Scale back up.

**Resolution**: add a `DELETE` audit guard (an integration test that asserts no use case ever issues a `DELETE` without a `WHERE id = ...`), or move the affected entity behind a soft-delete column.

**Postmortem**: 99% of these come from a missing `WHERE` in an ad-hoc SQL session. Add a `BEGIN; ... ROLLBACK; -- inspect first` policy in the team handbook.

---

## Helm release stuck in failed upgrade

**Signal**: `helm status {{ cookiecutter.project_slug }}` shows `FAILED`; pods are mixed (some new, some old) or all crashing.

**Triage**:
```bash
helm history {{ cookiecutter.project_slug }}
helm get values {{ cookiecutter.project_slug }} --revision <last-good>
```

**Mitigation**:
```bash
helm rollback {{ cookiecutter.project_slug }} <last-good-revision>
```

If `rollback` itself fails (rare):
```bash
# Force-clear the lock by deleting the stuck Helm secret (use with care).
kubectl get secrets -l owner=helm,name={{ cookiecutter.project_slug }} -o name | tail -1 | xargs kubectl delete
# Then redeploy from the last-good revision values:
helm upgrade --install {{ cookiecutter.project_slug }} ./helm/{{ cookiecutter.project_slug }} -f <last-good-values.yaml>
```

**Resolution**: the rollback gets you back to a known state. Fix the failed upgrade in a feature branch, run `helm template + kubeconform + polaris` locally before re-trying.

---

## Secrets compromised

**Signal**: an alert from your secrets manager, a leaked-credentials notification from a partner, or a developer reporting they pushed a secret to a public repo.

**Triage**:
- Identify which secrets are affected: `DB_URL`, `AUTH_JWT_SECRET`, broker credentials, …
- Determine the blast radius: was the secret used for read-only access or write?

**Mitigation** (in this order):
1. **Rotate** the secret at the source (cloud console / IdP).
2. **Update** the Kubernetes secret:
   ```bash
   kubectl create secret generic {{ cookiecutter.project_slug }}-secrets \
     --from-literal=DB_URL=<new-value> \
     --from-literal=AUTH_JWT_SECRET=<new-value> \
     --dry-run=client -o yaml | kubectl apply -f -
   ```
3. **Restart** the API + relay pods to pick up the new secret:
   ```bash
   kubectl rollout restart deploy/{{ cookiecutter.project_slug }}
   kubectl rollout restart deploy/{{ cookiecutter.project_slug }}-relay
   ```
4. **Revoke** any tokens issued under the compromised JWT secret (force re-login).
5. **Audit** the logs for the time window the secret was exposed: any suspicious activity?

**Postmortem**: the compromise vector — was it a leaked .env, a CI log, a developer laptop ? Fix the leak channel, not just the secret. Document the incident in `docs/runbooks/verification-log.md`.

---

## Region / AZ outage (multi-region setups only)

**Signal**: the cloud provider's status page reports a regional outage; multiple unrelated alerts firing simultaneously.

This template ships single-region by default. The playbook applies only if the project has wired multi-region. If it has:

**Mitigation**:
- Switch the load balancer / global DNS to the secondary region.
- Ensure the secondary's Postgres replica is promoted to primary if the outage is sustained (>30 min).
- Communicate the status banner to clients.

**Resolution**: cloud outages are out of your control. Document RPO/RTO actuals vs target.

---

## What does NOT belong in this runbook

* **Application bugs** — those go in the code, the tests, and the post-incident write-up. The runbook is for *operational* failures, not bad business logic.
* **Performance tuning** — see `onboarding-soma` § "Observability patterns" and the Grafana dashboards.
* **Cost incidents** — separate budget / FinOps runbook.

When you add a new playbook here, keep the 5-section structure and link from the corresponding PrometheusRule alert annotation.
