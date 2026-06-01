"""Forbid non-stdlib imports in ``src/<package>/domain/``.

The domain layer must remain pure: zero third-party dependencies. This script
parses every ``.py`` file under ``src/<package>/domain/`` and reports any
``import`` statement that resolves to a non-stdlib top-level package.

Exit codes:
    0  no violation
    1  violations found, paths listed on stderr
    2  invocation error (no files, broken AST)
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

DOMAIN_DIR_NAME = "domain"

# Standard library names available in Python 3.13. We reuse ``sys.stdlib_module_names``
# rather than maintain our own list.
STDLIB = set(sys.stdlib_module_names)
# The package being tested is always allowed (relative imports + absolute self-imports).
PROJECT_FIRST_PARTY: set[str] = set()


def _iter_domain_files(src_root: Path) -> list[Path]:
    return [p for p in src_root.rglob("*.py") if DOMAIN_DIR_NAME in p.parts]


def _project_top_level(src_root: Path) -> str | None:
    for child in src_root.iterdir():
        if child.is_dir() and (child / "__init__.py").exists():
            return child.name
    return None


def _imports(file: Path) -> list[tuple[int, str]]:
    tree = ast.parse(file.read_text(encoding="utf-8"), filename=str(file))
    imports: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append((node.lineno, alias.name.split(".")[0]))
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            imports.append((node.lineno, node.module.split(".")[0]))
    return imports


def main(argv: list[str]) -> int:
    """CLI entry point."""
    src_root = Path(argv[1]) if len(argv) > 1 else Path("src")
    if not src_root.is_dir():
        sys.stderr.write(f"src directory not found: {src_root}\n")
        return 2

    top_level = _project_top_level(src_root)
    if top_level:
        PROJECT_FIRST_PARTY.add(top_level)

    files = _iter_domain_files(src_root)
    if not files:
        return 0

    violations: list[str] = []
    for file in files:
        for lineno, top in _imports(file):
            if top in STDLIB or top in PROJECT_FIRST_PARTY:
                continue
            violations.append(f"{file}:{lineno}: forbidden third-party import in domain layer: '{top}'")

    if violations:
        sys.stderr.write("\n".join(violations) + "\n")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
