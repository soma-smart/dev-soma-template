# Backup verification log

Quarterly restore-drill record — see `backups-and-restore.md` § "Backup verification".

| Date (UTC) | Operator | Restore source | Restore target | `alembic current` | `pytest -m integration` | Anomalies / time-to-restore |
|---|---|---|---|---|---|---|
| _example_ 2026-04-15 | alice@soma | prod backup 2026-04-14 23:59 | side instance `psql-restore-20260415` | `0003_outbox_retry_columns` | 16 passed | ~12 min total; no anomalies |

## Process reminder

1. Provision a throw-away DB instance.
2. Restore the latest backup per the cloud's procedure in `backups-and-restore.md`.
3. Run `DB_URL=<restored-url> uv run alembic current` — must report the latest revision.
4. Run `DB_URL=<restored-url> uv run pytest -m integration` — must be green (the integration tests roll back, so they don't pollute the restored data).
5. Append a row to the table above.
6. Decommission the throw-away DB.

If the drill fails, that is a P1 incident — backups are not actually restorable until the gap is fixed.
