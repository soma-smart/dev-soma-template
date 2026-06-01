"""Cookiecutter pre-generation hook.

Validates user inputs before the project is generated. Aborts with a clear
error message when constraints are violated.
"""

from __future__ import annotations

import re
import sys

PACKAGE_NAME_RE = re.compile(r"^[a-z][a-z0-9_]*$")
PROJECT_SLUG_RE = re.compile(r"^[a-z][a-z0-9-]*$")
SUPPORTED_PYTHON = {"3.13", "3.14"}

PACKAGE_NAME = "{{ cookiecutter.package_name }}"
PROJECT_SLUG = "{{ cookiecutter.project_slug }}"
PYTHON_VERSION = "{{ cookiecutter.python_version }}"
DATABASE = "{{ cookiecutter.database }}"


def fail(message: str) -> None:
    sys.stderr.write(f"\nERROR: {message}\n")
    sys.exit(1)


def main() -> None:
    if not PACKAGE_NAME_RE.match(PACKAGE_NAME):
        fail(
            f"package_name '{PACKAGE_NAME}' is invalid. Must match {PACKAGE_NAME_RE.pattern} "
            "(lowercase, start with a letter, only letters/digits/underscores)."
        )

    if not PROJECT_SLUG_RE.match(PROJECT_SLUG):
        fail(
            f"project_slug '{PROJECT_SLUG}' is invalid. Must match {PROJECT_SLUG_RE.pattern} "
            "(lowercase, start with a letter, only letters/digits/hyphens)."
        )

    if PYTHON_VERSION not in SUPPORTED_PYTHON:
        fail(f"python_version '{PYTHON_VERSION}' is not supported. Choose one of: {sorted(SUPPORTED_PYTHON)}.")

    if DATABASE == "none":
        fail(
            "database=none is not supported in template v2: the reference feature in examples/ "
            "requires persistence. Choose 'postgres' or 'sqlite' instead."
        )


if __name__ == "__main__":
    main()
