"""Forbid ``float`` annotations in the ``domain/`` layer.

Use ``decimal.Decimal`` for monetary or precise quantities. Floats silently
lose precision and are the root cause of countless rounding bugs.

Scope rationale: the spec originally targeted both ``domain/`` and
``application/``, but the ``RandomSource`` primitive abstraction in
``application/`` legitimately exposes ``float`` (uniform [0,1) draws). The
lint therefore restricts to ``domain/``; reviewers and the
``writing-domain-code`` skill remind contributors not to push floats into
application use cases for monetary or business quantities.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

PROHIBITED_LAYERS = {"domain"}


def _under_protected_layer(file: Path) -> bool:
    parts = set(file.parts)
    return bool(parts & PROHIBITED_LAYERS)


def _scan(file: Path) -> list[str]:
    """Return the float-violation messages found in ``file``."""
    if "tests" in file.parts:
        return []
    issues: list[str] = []
    tree = ast.parse(file.read_text(encoding="utf-8"), filename=str(file))
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id == "float" and isinstance(getattr(node, "ctx", None), ast.Load):
            issues.append(f"{file}:{node.lineno}: 'float' is forbidden in the domain layer. Use decimal.Decimal.")
    return issues


def main(argv: list[str]) -> int:
    """CLI entry point. Returns 0 when no violation, 1 when violations found."""
    src_root = Path(argv[1]) if len(argv) > 1 else Path("src")
    files = [p for p in src_root.rglob("*.py") if _under_protected_layer(p)]
    issues: list[str] = []
    for file in files:
        issues.extend(_scan(file))
    if issues:
        sys.stderr.write("\n".join(issues) + "\n")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
