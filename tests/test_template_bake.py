"""Bake the cookiecutter and verify the produced project is sane.

Phase A ships smoke-level checks: the bake completes, the expected files are
present, and the produced pyproject is valid TOML referencing the chosen
package name. Phase K will extend this with three full combos
(postgres+helm+otel, sqlite+no-helm+otel, sqlite+no-helm+no-otel) plus
running ruff / ty / pytest on the baked output.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

import pytest


@pytest.mark.unit
def test_given_default_inputs_when_baking_then_creates_expected_layout(cookies) -> None:  # type: ignore[no-untyped-def]
    # GIVEN
    extra_context = {"project_name": "Acme Service"}

    # WHEN
    result = cookies.bake(extra_context=extra_context)

    # THEN
    assert result.exit_code == 0, f"bake failed: {result.exception}"
    assert result.exception is None
    assert result.project_path.is_dir()

    project = Path(result.project_path)
    assert (project / "pyproject.toml").is_file()
    assert (project / "README.md").is_file()
    assert (project / "CLAUDE.md").is_file()
    assert (project / ".env.example").is_file()
    assert (project / "src" / "acme_service" / "__init__.py").is_file()
    assert (project / "src" / "acme_service" / "presentation" / "api" / "app.py").is_file()


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
