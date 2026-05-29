"""Cookiecutter post-generation hook.

Runs after the project is generated to:
  1. Conditionally remove optional directories (helm/, openapi exporter, etc.)
  2. Copy .env.example -> .env
  3. Initialize git
  4. uv sync --group dev
  5. Install pre-commit hooks (commit-msg + pre-push)

Failures are reported but do not abort the generation: the project files are
already on disk and the user can fix tooling issues afterwards.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path.cwd()
INCLUDE_HELM = "{{ cookiecutter.include_helm }}" == "yes"
INCLUDE_OTEL = "{{ cookiecutter.include_otel }}" == "yes"
FRONTEND_SDK = "{{ cookiecutter.frontend_sdk }}"
DATABASE = "{{ cookiecutter.database }}"
PACKAGE_NAME = "{{ cookiecutter.package_name }}"
SWAGGER_AUTH_SCHEME = "{{ cookiecutter.swagger_auth_scheme }}"


def info(message: str) -> None:
    sys.stdout.write(f"  -> {message}\n")


def warn(message: str) -> None:
    sys.stderr.write(f"  ! {message}\n")


def remove_path(relative: str) -> None:
    target = PROJECT_ROOT / relative
    if target.is_dir():
        shutil.rmtree(target)
        info(f"removed {relative}/")
    elif target.is_file():
        target.unlink()
        info(f"removed {relative}")


def run(*command: str) -> bool:
    try:
        subprocess.run(command, check=True, cwd=PROJECT_ROOT)
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        warn(f"{' '.join(command)} failed: {exc}")
        return False
    return True


def git_commit_step(message: str, *paths: str) -> None:
    """Stage the listed paths and commit them, no-op when nothing changed.

    Bypasses any installed hooks (-n): bootstrap commits must not be gated by
    linters that haven't even been run on the user's machine yet.
    """
    if not (PROJECT_ROOT / ".git").exists():
        return
    for path in paths:
        if (PROJECT_ROOT / path).exists():
            run("git", "add", "--", path)
    status = subprocess.run(
        ["git", "diff", "--cached", "--quiet"],
        cwd=PROJECT_ROOT,
        check=False,
    )
    if status.returncode == 0:
        return
    run("git", "commit", "-n", "-m", message)


def remove_optional_components() -> None:
    if not INCLUDE_HELM:
        remove_path("helm")
    if not INCLUDE_OTEL:
        info("OTel disabled: kept the observability module so you can wire it later.")
    if FRONTEND_SDK == "none":
        remove_path("scripts/export_openapi.py")
        remove_path(".github/workflows/sdk-typescript.yml")
    if SWAGGER_AUTH_SCHEME != "oauth2_auth_code":
        remove_path(".devcontainer/keycloak")
    if DATABASE == "sqlite":
        info("database=sqlite: docker-compose Postgres service is still provided as opt-in.")


def setup_env_file() -> None:
    src = PROJECT_ROOT / ".env.example"
    dst = PROJECT_ROOT / ".env"
    if src.exists() and not dst.exists():
        shutil.copy(src, dst)
        info("created .env from .env.example")


def git_init() -> None:
    if (PROJECT_ROOT / ".git").exists():
        return
    if not run("git", "init", "--initial-branch=main"):
        return
    run("git", "add", ".")
    run("git", "commit", "-m", "feat: initial commit from soma template v2")


def uv_sync() -> None:
    if not run("uv", "sync", "--group", "dev"):
        warn("uv sync failed. Install uv and run 'uv sync --group dev' manually.")
        return
    git_commit_step("chore: lock dependencies", "uv.lock")


def install_pre_commit() -> None:
    if not run("uv", "run", "pre-commit", "install", "--install-hooks"):
        warn("pre-commit install (default) failed.")
        return
    run(
        "uv",
        "run",
        "pre-commit",
        "install",
        "--hook-type",
        "commit-msg",
        "--hook-type",
        "pre-push",
    )


def apply_initial_migration() -> None:
    """Run ``alembic upgrade head`` for SQLite only.

    SQLite is local-file, deterministic, completes in <1s. For Postgres the
    DB URL points at the in-network ``postgres`` service that is unreachable
    from the host running cookiecutter; the devcontainer's ``postStartCommand``
    (``just migrate``) applies the schema once the service is healthy.
    """
    if DATABASE != "sqlite":
        info("alembic upgrade head deferred to devcontainer postStart (just migrate).")
        return

    env = os.environ.copy()
    env_file = PROJECT_ROOT / ".env"
    if env_file.exists():
        for raw_line in env_file.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            env[key.strip()] = value.strip()

    try:
        subprocess.run(
            ["uv", "run", "alembic", "upgrade", "head"],
            cwd=PROJECT_ROOT,
            env=env,
            check=True,
            capture_output=True,
            timeout=15,
        )
        info("applied initial migration")
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired) as exc:
        warn(f"alembic upgrade head skipped: {exc}")


def print_next_steps() -> None:
    sys.stdout.write(
        "\n"
        "Generated successfully.\n"
        "\n"
        "Next steps:\n"
        "  cd " + PROJECT_ROOT.name + "\n"
        "  code .                                 # then 'Reopen in Container'\n"
        "  uv run uvicorn " + PACKAGE_NAME + ".presentation.api.app:app --reload\n"
        "  uv run pytest -m unit\n"
        "\n"
        "Read CLAUDE.md and docs/architecture.md before adding your first feature.\n"
    )


def main() -> None:
    info("running post-generation hook")
    remove_optional_components()
    setup_env_file()
    git_init()
    uv_sync()
    install_pre_commit()
    apply_initial_migration()
    print_next_steps()


if __name__ == "__main__":
    main()
