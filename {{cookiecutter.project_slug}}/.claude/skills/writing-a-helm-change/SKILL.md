---
name: writing-a-helm-change
description: Edits to the Helm chart (templates, values, schema). Validate locally before pushing.
when_to_use: Editing helm/{{ cookiecutter.project_slug }}/**.
---

{% raw %}# Writing a Helm change

## Edit checklist

1. **Templates** are Go templates inside cookiecutter raw blocks. Inside a template file, use Helm Go template syntax `{{ .Values.X }}` and `{{ include "app.name" . }}` for runtime values. Do NOT introduce cookiecutter `{{ cookiecutter.X }}` interpolations in templates — those are baked once and cannot vary per environment.
2. **Add the field to `values.yaml` AND `values.schema.json`.** The schema is enforced by Helm — any value not described will be rejected.
3. **Update each environment overlay** if the new field has a meaningful per-environment default (`values-dev.yaml`, `values-staging.yaml`, `values-prod.yaml`).
4. **Probes**: changes to readiness/liveness behaviour require a local round trip with `helm template ... | kubectl apply --dry-run=server`.

## Validate locally

```bash
helm lint helm/<project_slug>
helm template t helm/<project_slug> -f helm/<project_slug>/values-prod.yaml --set secrets.dbUrl=postgresql+asyncpg://test/test > /tmp/manifest.yaml
kubeconform -strict -ignore-missing-schemas /tmp/manifest.yaml
polaris audit --audit-path /tmp/manifest.yaml --format=pretty
```

CI runs the same in `ci-helm.yml`.

## Common patterns

- **New env var for the app**: add to `values.yaml::config.<name>`, schema, and `templates/configmap.yaml`. Then read it from `Settings` in `infrastructure/config/settings.py`.
- **New secret**: extend `values.yaml::secrets`, schema, and `templates/secret.yaml`. Inject via `envFrom: - secretRef:` in the deployment.
- **New Helm hook job** (besides migrations): copy the structure from `migration-job.yaml`. Set `helm.sh/hook-weight` so order is deterministic.

## Things to avoid

- Hard-coded namespaces — use `{{ .Release.Namespace }}` if the chart needs to know.
- `latest` image tags — pin via `appVersion` in `Chart.yaml` or `image.tag` in values.
- Privileged or root pods — `podSecurityContext.runAsNonRoot: true` is already set; do not remove it.
- Deleting `migrations.enabled` from values.yaml without replacing the schema management strategy.
{% endraw %}
