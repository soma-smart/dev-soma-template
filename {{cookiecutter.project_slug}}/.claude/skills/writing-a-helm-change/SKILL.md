---
name: writing-a-helm-change
description: Editing the Helm chart (templates, values, schema, overlays). What ships, how to add a value, how to validate locally, what CI catches.
when_to_use: Editing anything under helm/{{ cookiecutter.project_slug }}/; adding a new env var or secret that the app needs in cluster; reviewing a chart change.
---

{% raw %}# Writing a Helm change

## What ships in the chart

```
helm/<project_slug>/
├── Chart.yaml
├── values.yaml                # default values, documented inline
├── values.schema.json         # JSON Schema — Helm rejects unknown keys
├── values-dev.yaml            # per-environment overlays
├── values-staging.yaml
├── values-prod.yaml
└── templates/
    ├── _helpers.tpl           # name, fullname, labels, selectorLabels, serviceAccountName
    ├── configmap.yaml         # non-sensitive env (LOG_FORMAT, SERVICE_NAME, OTEL_*, CORS_*)
    ├── deployment.yaml        # probes, resources, securityContext, terminationGracePeriodSeconds
    ├── hpa.yaml               # HorizontalPodAutoscaler (opt-in via autoscaling.enabled)
    ├── ingress.yaml           # opt-in via ingress.enabled
    ├── migration-job.yaml     # Helm pre-install / pre-upgrade Job running 'alembic upgrade head'
    ├── pdb.yaml               # PodDisruptionBudget (opt-in)
    ├── prometheusrule.yaml    # alert rules (opt-in via metrics.alerts.enabled)
    ├── relay-deployment.yaml  # outbox relay worker (opt-in via relay.enabled)
    ├── relay-service.yaml     # ClusterIP exposing the relay's /metrics on 9100
    ├── relay-servicemonitor.yaml # Prometheus scrape of the relay
    ├── secret.yaml            # rendered iff secrets.dbUrl is set; otherwise external secrets fill it
    ├── service.yaml
    ├── serviceaccount.yaml
    ├── servicemonitor.yaml    # Prometheus ServiceMonitor (opt-in via metrics.enabled)
    └── tests/
        └── test-connection.yaml  # 'helm test' smoke check on /health/live
```

Every template wraps its Go syntax inside a Jinja `raw` block because the file lives in a Cookiecutter template tree — see the existing files for the pattern.

## Edit checklist

1. **Templates are Go templates wrapped in cookiecutter raw blocks.** Inside a template file, use Helm Go template syntax `{{ .Values.X }}`, `{{ include "app.name" . }}`, `{{ .Release.Namespace }}`. Do NOT introduce cookiecutter `{{ cookiecutter.X }}` inside the raw block — those are baked once and cannot vary per environment.
2. **Add the field to BOTH `values.yaml` AND `values.schema.json`.** Helm rejects values not described in the schema. Most "my override was silently ignored" bugs come from a missing schema entry.
3. **Update each environment overlay** if the new field has a meaningful per-environment default (`values-dev.yaml`, `values-staging.yaml`, `values-prod.yaml`).
4. **Probes and shutdown alignment.** Changes to readiness / liveness paths or `terminationGracePeriodSeconds` need to stay coherent with `Dockerfile`'s `--timeout-graceful-shutdown` value (currently 30s); `terminationGracePeriodSeconds` MUST stay strictly greater so K8s never SIGKILLs before uvicorn drains.

## Validate locally

```bash
just helm-lint
just helm-render            # default: prod overlay
just helm-render dev        # any of dev / staging / prod
# Pipe into kubeconform if installed:
just helm-render prod | kubeconform -strict -ignore-missing-schemas -
# Pipe into polaris if installed:
just helm-render prod | polaris audit --audit-path -
```

CI runs the same checks in `ci-helm.yml`: `helm lint`, `helm template` on default + prod overlays, `kubeconform -strict`, `polaris audit`.

## Common patterns

* **New env var the app reads.** Add it under `values.yaml::config.<name>`, declare it in `values.schema.json`, render it in `templates/configmap.yaml` as a key under `data:`. Then read it from `Settings` in `infrastructure/config/settings.py`. The Deployment already pulls `envFrom: configMapRef: <fullname>-config`, no template change needed.
* **New secret.** Extend `values.yaml::secrets`, declare in the schema, render in `templates/secret.yaml` under `stringData:`. The Deployment is already wired to `envFrom: secretRef:` (rendered conditionally on the secret existing).
* **Enable metrics scraping.** Flip `metrics.enabled: true` in the overlay — the `ServiceMonitor` template renders (for the API on port `http` and the relay on port `metrics`), a Prometheus Operator picks them up. The `/metrics` endpoint is always exposed by the app and the relay regardless; the gate is on cluster-side scraping.
* **Enable alert rules.** Set `metrics.alerts.enabled: true`. Renders a `PrometheusRule` with 4 outbox alerts (backlog, lag, poisoned, handler error rate), 3 API alerts (5xx rate, p99 latency, no replicas), and 1 relay availability alert (no replicas). Tune thresholds under `metrics.alerts.thresholds.*` per env. Use `metrics.alerts.labels` to inject routing labels (e.g. `team: backend`) for Alertmanager.
* **Add a new alert.** Append a `rule` entry under the right group in `templates/prometheusrule.yaml`. Each rule needs `alert`, `expr`, `for`, `labels.severity` (`warning` or `critical`), `annotations.summary` and `annotations.description`. If the alert references a threshold, declare a default in `values.yaml::metrics.alerts.thresholds` and add it to `values.schema.json`. Cross-link the runbook procedure in the description (most outbox runbooks live in the `transactions-and-events` skill).
* **New Helm hook Job (besides migrations).** Copy the structure from `templates/migration-job.yaml`. Set `helm.sh/hook-weight` to control ordering relative to the migrations job (which is at weight `-5`, so it runs first).
* **Tune resources / replicas / autoscaling per env.** Edit the overlay (`values-<env>.yaml`), not the base `values.yaml`. The base carries safe defaults; overlays carry the env-specific tuning.

## Things to avoid

* **Hard-coded namespaces.** Use `{{ .Release.Namespace }}` if the template needs to know.
* **`latest` image tags.** Production deployments must be deterministic — `image.tag` is set per-release via CI or values overlay, defaults to `.Chart.AppVersion`.
* **Privileged or root pods.** `podSecurityContext.runAsNonRoot: true` is the shipped default; do not remove it. Same for the dropped capabilities in `securityContext.capabilities.drop`.
* **Removing `migrations.enabled`.** If the project moves away from Alembic, replace the schema management strategy in the same PR — do not just delete the gate.
* **Shrinking `terminationGracePeriodSeconds` below 30.** The Dockerfile gives uvicorn 30 seconds to drain; anything less will SIGKILL in-flight requests.
* **Adding a value without a schema entry.** Helm will accept the override silently in some versions and reject it in others — always update `values.schema.json` in the same diff.
{% endraw %}
