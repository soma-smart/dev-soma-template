# Production image — used by the Helm chart.
# Multi-stage Pattern 1: builder installs deps, runtime ships only the venv +
# the application code. The development image lives separately under
# .devcontainer/ to keep this file focused on prod concerns.

ARG PYTHON_VERSION={{ cookiecutter.python_version }}

# ─── builder ────────────────────────────────────────
FROM python:${PYTHON_VERSION}-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# ─── runtime ────────────────────────────────────────
FROM python:${PYTHON_VERSION}-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH"

RUN apt-get update \
    && apt-get install -y --no-install-recommends tini ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --system --gid 1001 app \
    && useradd --system --uid 1001 --gid app --no-create-home app

WORKDIR /app
COPY --from=builder /app/.venv /app/.venv
COPY --chown=app:app src/ /app/src/
COPY --chown=app:app alembic/ /app/alembic/
COPY --chown=app:app alembic.ini /app/

USER app
EXPOSE 8000

ENTRYPOINT ["tini", "--"]
# --timeout-graceful-shutdown 30 lets uvicorn drain in-flight requests for up
# to 30s after SIGTERM. The Helm chart's terminationGracePeriodSeconds MUST
# stay strictly greater than 30 for the drain to complete before SIGKILL.
CMD ["uvicorn", "{{ cookiecutter.package_name }}.presentation.api.app:app", \
     "--host", "0.0.0.0", "--port", "8000", \
     "--timeout-graceful-shutdown", "30"]
