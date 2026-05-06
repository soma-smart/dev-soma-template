"""Cookiecutter post-generation hook.

Runs after the project is generated to:
  1. Conditionally remove optional directories (helm/, presentation/cli/, etc.)
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
INCLUDE_CLI = "{{ cookiecutter.include_cli }}" == "yes"
FRONTEND_SDK = "{{ cookiecutter.frontend_sdk }}"
DATABASE = "{{ cookiecutter.database }}"
PACKAGE_NAME = "{{ cookiecutter.package_name }}"


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


def remove_optional_components() -> None:
    if not INCLUDE_HELM:
        remove_path("helm")
    if not INCLUDE_CLI:
        remove_path(f"src/{PACKAGE_NAME}/presentation/cli")
    if not INCLUDE_OTEL:
        info("OTel disabled: kept the observability module so you can wire it later.")
    if FRONTEND_SDK == "none":
        remove_path("scripts/export_openapi.py")
        remove_path(".github/workflows/sdk-typescript.yml")
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
    """Best-effort ``alembic upgrade head`` against the configured DB.

    Loads ``.env`` so ``DB_URL`` is available to alembic, then attempts the
    upgrade. Succeeds for the SQLite default (creates ``local.db`` in the
    project root). For Postgres, succeeds only when the DB is already up
    (e.g. inside the devcontainer); otherwise the failure is logged and
    silenced — the devcontainer ``postStartCommand`` reapplies it once the
    Postgres service is healthy.
    """
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
            timeout=30,
        )
        info("applied initial migration")
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired) as exc:
        warn(f"alembic upgrade head skipped (DB not reachable yet?): {exc}")


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
