# Backups & restore

Operational reference for the persistent state of {{ cookiecutter.project_name }}. Read this **before** an incident — at 3 AM the bandwidth for learning is low.

## Scope

| What | Persisted ? | Backed up by this runbook ? |
|---|---|---|
| Postgres data (users, outbox_events, idempotency_records, …) | yes | **yes** |
| Application code | yes (in git) | covered by git |
| Container images | yes (in registry) | covered by registry retention |
| Helm values + secrets | yes (in the cluster) | depends on your secrets manager (SealedSecrets, ExternalSecrets) |
| OTel traces + Prometheus metrics | observability stack | not in scope — ephemeral by design |
| Structured logs | log aggregator (Loki / Cloud Logging) | not in scope — log aggregator's retention |

The only thing this service owns and that **cannot be reconstructed** is the Postgres data. Everything else either lives in git, in a registry, or is observability data that is OK to lose.

## Strategy: prefer cloud-managed Postgres

Cloud-managed Postgres ships with continuous point-in-time recovery (PITR) and a tested restore path. Reinventing this on Kubernetes with pg_dump + a bucket is rarely worth it. The shipped Helm chart works with both.

### AWS RDS for PostgreSQL

* **Automated backups**: enable `BackupRetentionPeriod >= 7` on the DB instance.
* **PITR window**: 1 second granularity within the retention period.
* **Restore command**:
  ```bash
  aws rds restore-db-instance-to-point-in-time \
    --source-db-instance-identifier {{ cookiecutter.project_slug }}-prod \
    --target-db-instance-identifier {{ cookiecutter.project_slug }}-restore-$(date +%Y%m%d-%H%M) \
    --restore-time 2026-05-12T13:00:00Z
  ```
* **Cost note**: snapshots + transaction logs typically add 10-20% to the DB cost.

### GCP Cloud SQL for PostgreSQL

* **Automated backups**: enable in the instance settings; default retention 7 days, configurable up to 365.
* **PITR**: enable `binaryLogEnabled` (transaction logs).
* **Restore command**:
  ```bash
  gcloud sql backups restore <BACKUP_ID> \
    --restore-instance={{ cookiecutter.project_slug }}-restore-$(date +%Y%m%d-%H%M) \
    --backup-instance={{ cookiecutter.project_slug }}-prod
  ```
* **PITR clone** (preferred for accidental data loss):
  ```bash
  gcloud sql instances clone {{ cookiecutter.project_slug }}-prod \
    {{ cookiecutter.project_slug }}-restore-$(date +%Y%m%d-%H%M) \
    --point-in-time=2026-05-12T13:00:00Z
  ```

### Azure Database for PostgreSQL — Flexible Server

* **Automated backups**: enabled by default. Retention 7-35 days.
* **PITR window**: same as AWS, 1 second granularity within retention.
* **Restore command**:
  ```bash
  az postgres flexible-server restore \
    --resource-group {{ cookiecutter.project_slug }} \
    --name {{ cookiecutter.project_slug }}-restore-$(date +%Y%m%d-%H%M) \
    --source-server {{ cookiecutter.project_slug }}-prod \
    --restore-time 2026-05-12T13:00:00Z
  ```

## Strategy: self-managed Postgres (only when cloud is not an option)

If you must run Postgres in your own cluster (regulatory constraint, air-gapped env, …), the recommended setup is **pgBackRest** or **WAL-G** with continuous WAL archiving to object storage (S3 / GCS / Azure Blob / MinIO).

This template does **not** ship a `pg_dump` CronJob: a daily logical dump trades 24 hours of RPO and a multi-hour RTO against ~2 minutes of operator cleverness. Use pgBackRest or move to cloud-managed before going to prod.

If you absolutely must use `pg_dump` for an interim setup, the manual recipe is:

```bash
# Daily, from a cluster-internal pod or operator host:
kubectl exec -n {{ cookiecutter.project_slug }} postgres-0 -- \
  pg_dump -U app -d {{ cookiecutter.package_name }} -Fc \
  > {{ cookiecutter.package_name }}-$(date +%Y%m%d).dump

# Upload to your object store; lifecycle policy on the bucket
# handles retention.
aws s3 cp {{ cookiecutter.package_name }}-*.dump s3://my-backups/db/
```

## Retention policy (recommended baseline)

| Tier | Frequency | Retention |
|---|---|---|
| Continuous WAL / transaction log | continuous | 7 days |
| Daily full | daily | 7 days |
| Weekly full | weekly | 4 weeks |
| Monthly full | monthly | 12 months |

Tune to your industry's regulatory needs (HIPAA, GDPR right-to-erasure, etc.).

## Restore procedures

### Full restore from PITR (cloud-managed)

Use case: accidental `DELETE FROM users` or schema corruption.

1. **Stop writes immediately**: scale the API deployment to 0 to prevent more damage.
   ```bash
   kubectl scale deployment/{{ cookiecutter.project_slug }} --replicas=0
   ```
2. **Identify the restore point**: typically just before the bad transaction. The application logs should give you a UTC timestamp.
3. **Create the restore DB instance** (per-cloud command above). Use a distinct name (e.g. `-restore-YYYYMMDD-HHMM`).
4. **Verify the data**: connect to the restored DB and check the affected table(s) match expected state.
   ```bash
   psql $RESTORED_DB_URL -c "SELECT COUNT(*) FROM users WHERE created_at < '2026-05-12T13:00:00Z'"
   ```
5. **Swap DB URLs**: update the Helm release's `DB_URL` secret to point at the restored instance.
   ```bash
   helm upgrade {{ cookiecutter.project_slug }} ./helm/{{ cookiecutter.project_slug }} \
     --reuse-values --set secrets.dbUrl=$RESTORED_DB_URL
   ```
6. **Scale the API back up**:
   ```bash
   kubectl scale deployment/{{ cookiecutter.project_slug }} --replicas=2
   ```
7. **Decommission the broken DB** only after monitoring shows the restore was successful (give it 24 hours).

### Partial restore (one table, one row)

Use case: accidental `UPDATE` on a few rows; the rest of the DB is fine.

1. Restore to a side instance using PITR (steps 1-4 above).
2. Pull the affected rows out via `pg_dump --data-only --table=...`.
3. Apply to the production DB inside a transaction.
4. Drop the side instance.

This is faster than a full swap but riskier — keep a SQL transcript of what you did.

### Restore from `pg_dump` (self-managed fallback)

```bash
# 1. Provision a fresh DB.
# 2. Apply migrations to bootstrap the schema:
DB_URL=$NEW_DB_URL uv run alembic upgrade head
# 3. Load the dump:
pg_restore -U app -d {{ cookiecutter.package_name }} --no-owner -j 4 {{ cookiecutter.package_name }}-20260512.dump
# 4. Sanity check:
psql $NEW_DB_URL -c "SELECT COUNT(*) FROM users"
```

## Backup verification (mandatory quarterly)

A backup that was never restored is a hope. Every quarter, an engineer must:

1. Provision a throw-away DB instance.
2. Restore the latest backup using the appropriate procedure above.
3. Run `uv run alembic current` against the restored DB — must show the latest revision.
4. Run `uv run pytest -m integration` against the restored DB (the integration tests do not destroy data, they roll back).
5. Add a line to `docs/runbooks/verification-log.md` with the date, operator, and any anomalies.
6. Decommission the throw-away DB.

A team that has never run a restore drill **does not have backups**.

## Things to NOT do

* **Run pg_dump in production peak hours**: it acquires read locks; on a busy DB this blocks writes. Prefer cloud-managed PITR which uses replication, not dumps.
* **Use `pg_dump --clean`** on restore unless you really mean to drop the public schema first. Surprising number of incidents start here.
* **Forget the WAL retention**: PITR depends on transaction logs. If the WAL bucket has a 1-day lifecycle, your PITR window is 1 day, regardless of what you set on full backups.
* **Restore over the live DB**: always restore to a SIDE instance, verify, then swap. Never `psql $PROD < backup.sql`.
* **Skip step 7 (decommission)**: leftover restore instances are an attack surface (often less hardened, often forgotten in secrets rotation).
