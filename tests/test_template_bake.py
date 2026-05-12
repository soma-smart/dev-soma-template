"""Bake the cookiecutter and verify the produced project is sane.

Smoke checks (always-on):
  - bake completes for the default combo
  - expected files are present
  - produced pyproject is valid TOML

Combo checks (also always-on, fast):
  - postgres + helm + otel
  - sqlite  + no-helm + otel
  - sqlite  + no-helm + no-otel

Tooling checks on the baked project (marked `integration` — opt-in via
``pytest -m integration``): runs ``ruff check``, the four custom lints, and
``pytest -m unit`` against the freshly baked tree. Slower because each combo
re-installs deps.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tomllib
from pathlib import Path

import pytest

EXPECTED_TOP_FILES = (
    "pyproject.toml",
    "README.md",
    "CLAUDE.md",
    "LICENSE",
    "SECURITY.md",
    ".env.example",
    "Dockerfile",
    ".pre-commit-config.yaml",
    "alembic.ini",
    ".github/CODEOWNERS",
)


@pytest.mark.unit
def test_given_default_inputs_when_baking_then_creates_expected_layout(cookies) -> None:  # type: ignore[no-untyped-def]
    # GIVEN
    extra_context = {"project_name": "Acme Service"}

    # WHEN
    result = cookies.bake(extra_context=extra_context)

    # THEN
    assert result.exit_code == 0, f"bake failed: {result.exception}"
    assert result.exception is None
    project = Path(result.project_path)
    for name in EXPECTED_TOP_FILES:
        assert (project / name).exists(), f"missing top-level {name}"
    assert (project / "src" / "acme_service" / "__init__.py").is_file()
    assert (project / "src" / "acme_service" / "presentation" / "api" / "app.py").is_file()
    assert (project / "docs" / "runbooks" / "backups-and-restore.md").is_file()
    assert (project / "docs" / "runbooks" / "disaster-recovery.md").is_file()
    assert (project / "docs" / "runbooks" / "verification-log.md").is_file()
    assert (project / ".claude" / "skills").is_dir()
    assert (project / ".claude" / "skills" / "incident-response" / "SKILL.md").is_file()
    assert (project / ".claude" / "skills" / "orchestrating-feature-dev" / "SKILL.md").is_file()
    agents_dir = project / ".claude" / "agents"
    assert agents_dir.is_dir()
    for agent_file in (
        "soma-unit-test-writer.md",
        "soma-integration-test-writer.md",
        "soma-migration-writer.md",
        "soma-helm-engineer.md",
        "soma-event-sourcing-bootstrapper.md",
        "soma-use-case-builder.md",
        "soma-persistence-builder.md",
        "soma-route-builder.md",
    ):
        assert (agents_dir / agent_file).is_file(), f"missing agent {agent_file}"
    assert (project / ".claude" / "skills" / "event-sourcing-pattern" / "SKILL.md").is_file()
    assert (project / "helm" / "acme-service" / "Chart.yaml").is_file()
    assert (project / ".devcontainer" / "devcontainer.json").is_file()


@pytest.mark.unit
def test_given_baked_project_when_reading_pyproject_then_has_correct_name(cookies) -> None:  # type: ignore[no-untyped-def]
    # GIVEN
    result = cookies.bake(extra_context={"project_name": "Acme Service"})
    pyproject_path = Path(result.project_path) / "pyproject.toml"

    # WHEN
    pyproject = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))

    # THEN
    assert pyproject["project"]["name"] == "acme-service"
    assert pyproject["project"]["requires-python"].startswith(">=")


@pytest.mark.unit
def test_given_database_none_when_baking_then_aborts(cookies) -> None:  # type: ignore[no-untyped-def]
    # GIVEN / WHEN
    result = cookies.bake(extra_context={"project_name": "Bad", "database": "none"})

    # THEN
    assert result.exit_code != 0


@pytest.mark.unit
@pytest.mark.parametrize(
    ("license_value", "marker"),
    [
        ("proprietary", "All rights reserved"),
        ("MIT", "MIT License"),
        ("Apache-2.0", "Apache License"),
    ],
)
def test_given_license_choice_when_baking_then_license_file_matches(  # type: ignore[no-untyped-def]
    cookies, license_value: str, marker: str
) -> None:
    # GIVEN / WHEN
    safe_name = license_value.replace(".", "").replace("-", "")
    result = cookies.bake(extra_context={"project_name": f"Lic {safe_name}", "license": license_value})

    # THEN
    assert result.exit_code == 0, result.exception
    license_text = (Path(result.project_path) / "LICENSE").read_text(encoding="utf-8")
    assert marker in license_text


@pytest.mark.unit
@pytest.mark.parametrize(
    ("combo_id", "context"),
    [
        ("postgres-helm-otel", {"database": "postgres", "include_helm": "yes", "include_otel": "yes"}),
        ("sqlite-no-helm-otel", {"database": "sqlite", "include_helm": "no", "include_otel": "yes"}),
        ("sqlite-no-helm-no-otel", {"database": "sqlite", "include_helm": "no", "include_otel": "no"}),
        ("ts-sdk", {"database": "postgres", "frontend_sdk": "typescript"}),
    ],
)
def test_given_combo_when_baking_then_succeeds(cookies, combo_id: str, context: dict[str, str]) -> None:  # type: ignore[no-untyped-def]
    # GIVEN
    extra = {"project_name": f"Combo {combo_id}"} | context

    # WHEN
    result = cookies.bake(extra_context=extra)

    # THEN
    assert result.exit_code == 0, f"bake failed for {combo_id}: {result.exception}"
    project = Path(result.project_path)
    assert (project / "pyproject.toml").is_file()
    if context.get("include_helm") == "no":
        assert not (project / "helm").exists()
    elif context.get("include_helm") == "yes":
        assert (project / "helm").is_dir()
        helm_templates = next(iter((project / "helm").iterdir())) / "templates"
        for relay_template in ("relay-deployment.yaml", "relay-service.yaml", "relay-servicemonitor.yaml"):
            assert (helm_templates / relay_template).is_file(), f"missing relay template {relay_template}"
        assert (helm_templates / "prometheusrule.yaml").is_file(), "missing prometheusrule.yaml"
    if context.get("frontend_sdk") == "typescript":
        assert (project / "scripts" / "export_openapi.py").is_file()
        assert (project / ".github" / "workflows" / "sdk-typescript.yml").is_file()
    else:
        assert not (project / "scripts" / "export_openapi.py").exists()
        assert not (project / ".github" / "workflows" / "sdk-typescript.yml").exists()


@pytest.mark.integration
def test_given_default_bake_when_running_quality_pipeline_then_passes(cookies) -> None:  # type: ignore[no-untyped-def]
    # GIVEN
    if shutil.which("uv") is None:
        pytest.skip("uv not available")
    result = cookies.bake(extra_context={"project_name": "Quality Check"})
    assert result.exit_code == 0
    project = Path(result.project_path)
    env = {**os.environ, "DB_URL": "sqlite+aiosqlite:///./local.db"}

    # WHEN
    sync = subprocess.run(["uv", "sync", "--group", "dev"], cwd=project, env=env, capture_output=True)
    ruff = subprocess.run(
        ["uv", "run", "ruff", "check", "src/", "tests/", "scripts/"],
        cwd=project, env=env, capture_output=True,
    )
    lint_domain = subprocess.run(
        ["uv", "run", "python", "scripts/checks/no_third_party_in_domain.py", "src/"],
        cwd=project, env=env, capture_output=True,
    )
    test_naming = subprocess.run(
        ["uv", "run", "python", "scripts/checks/test_naming.py", "tests/"],
        cwd=project, env=env, capture_output=True,
    )
    pytest_unit = subprocess.run(
        ["uv", "run", "pytest", "-m", "unit", "-q"],
        cwd=project, env=env, capture_output=True,
    )

    # THEN
    assert sync.returncode == 0, sync.stderr.decode()
    assert ruff.returncode == 0, ruff.stdout.decode()
    assert lint_domain.returncode == 0, lint_domain.stderr.decode()
    assert test_naming.returncode == 0, test_naming.stderr.decode()
    assert pytest_unit.returncode == 0, pytest_unit.stdout.decode()
