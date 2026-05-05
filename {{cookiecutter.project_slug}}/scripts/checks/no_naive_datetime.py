"""Forbid naive ``datetime.now()`` / ``datetime.utcnow()`` calls outside tests.

Naive datetimes break determinism (FIRST) and conflate time zones. The
domain and application layers must use the ``Clock`` abstraction; the
infrastructure and presentation layers must pass an explicit ``tz=`` argument.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path


def _scan(file: Path) -> list[str]:
    issues: list[str] = []
    tree = ast.parse(file.read_text(encoding="utf-8"), filename=str(file))
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Attribute):
            if func.attr == "utcnow":
                issues.append(f"{file}:{node.lineno}: 'datetime.utcnow()' is forbidden (naive). Use 'datetime.now(tz=UTC)' or the Clock abstraction.")
            elif func.attr == "now":
                # datetime.now() with no kwargs and no tz positional arg is naive.
                has_tz = any(kw.arg == "tz" for kw in node.keywords) or bool(node.args)
                if not has_tz:
                    issues.append(f"{file}:{node.lineno}: naive 'datetime.now()' is forbidden. Pass 'tz=UTC' or use the Clock abstraction.")
    return issues


def main(argv: list[str]) -> int:
    targets = [Path(p) for p in argv[1:]] or [Path("src")]
    files: list[Path] = []
    for t in targets:
        if t.is_dir():
            files.extend(p for p in t.rglob("*.py") if "tests" not in p.parts)
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
