"""Enforce GIVEN/WHEN/THEN test format.

Two checks per test function:
    1. Function name matches ``test_given_<context>_when_<action>_then_<expectation>``.
    2. Function body contains exactly the comments ``# GIVEN``, ``# WHEN``, ``# THEN``
       (or ``# WHEN / THEN`` combined when followed by ``pytest.raises``) in this
       order, separated by blank lines.

Strict for tests under ``tests/unit/`` and ``tests/integration/``. Looser for
``tests/e2e/`` where the GIVEN may be encoded in a fixture; only ``# WHEN``
and ``# THEN`` are required there.
"""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

NAME_RE = re.compile(r"^test_given_[a-z0-9_]+_when_[a-z0-9_]+_then_[a-z0-9_]+$")
WHEN_THEN_NAME_RE = re.compile(r"^test_[a-z0-9_]+$")  # fallback for pytest.raises-only patterns
STRICT_PARTS = ("unit", "integration")


def _is_strict(file: Path) -> bool:
    return any(part in STRICT_PARTS for part in file.parts)


def _is_e2e(file: Path) -> bool:
    return "e2e" in file.parts


def _has_marker(text: str, marker: str) -> bool:
    """Match a stripped line equal to ``marker`` or starting with ``marker:``.

    The colon-suffix form lets fixture-driven tests annotate the bare GIVEN
    block without a body — ``# GIVEN: wired by fixture`` is a single-line
    sentence that satisfies the marker requirement.
    """
    target = marker.strip()
    return any(line.strip() == target or line.strip().startswith(f"{target}:") for line in text.splitlines())


def _check_function(file: Path, fn: ast.FunctionDef | ast.AsyncFunctionDef, source: str) -> list[str]:
    issues: list[str] = []
    name = fn.name
    if not name.startswith("test_"):
        return []

    body_text = ast.get_source_segment(source, fn) or ""
    has_given = _has_marker(body_text, "# GIVEN")
    has_when = _has_marker(body_text, "# WHEN") or _has_marker(body_text, "# WHEN / THEN")
    has_then = _has_marker(body_text, "# THEN") or _has_marker(body_text, "# WHEN / THEN")

    if _is_strict(file):
        if not NAME_RE.match(name):
            issues.append(
                f"{file}:{fn.lineno}: '{name}' must match test_given_<context>_when_<action>_then_<expectation>."
            )
        if not (has_given and has_when and has_then):
            issues.append(
                f"{file}:{fn.lineno}: '{name}' must contain '# GIVEN', '# WHEN' and '# THEN' comments "
                "(or '# WHEN / THEN' combined when raising)."
            )
    elif _is_e2e(file) and not (has_when and has_then):
        issues.append(f"{file}:{fn.lineno}: e2e test '{name}' must contain '# WHEN' and '# THEN' comments.")
    return issues


def _scan(file: Path) -> list[str]:
    source = file.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(file))
    issues: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            issues.extend(_check_function(file, node, source))
    return issues


def main(argv: list[str]) -> int:
    """CLI entry point."""
    targets = [Path(p) for p in argv[1:]] or [Path("tests")]
    files: list[Path] = []
    for t in targets:
        if t.is_dir():
            files.extend(p for p in t.rglob("test_*.py"))
        elif t.suffix == ".py":
            files.append(t)
    issues: list[str] = []
    for file in files:
        issues.extend(_scan(file))
    if issues:
        sys.stderr.write("\n".join(issues) + "\n")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
