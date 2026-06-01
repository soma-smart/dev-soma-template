"""Export the FastAPI OpenAPI schema as a JSON file.

Usage:
    uv run python scripts/export_openapi.py [output_path]
    just openapi

Defaults to ``openapi.json`` at the project root. Used by:
- the typescript SDK generation workflow
- documentation site builders that consume the schema

The script avoids touching the database: it sets a placeholder ``DB_URL``
before importing the app so Pydantic Settings validation succeeds without
actually connecting (``create_app`` only inspects routes; the lifespan that
opens the engine never runs).
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

os.environ.setdefault("DB_URL", "sqlite+aiosqlite:///:memory:")

from {{ cookiecutter.package_name }}.presentation.api.app import create_app

DEFAULT_OUTPUT = Path("openapi.json")


def main(argv: list[str]) -> int:
    """Write the OpenAPI schema to ``argv[1]`` (or ``openapi.json``)."""
    output = Path(argv[1]) if len(argv) > 1 else DEFAULT_OUTPUT
    app = create_app()
    schema = app.openapi()
    output.write_text(json.dumps(schema, indent=2, sort_keys=True), encoding="utf-8")
    sys.stdout.write(f"Wrote OpenAPI schema to {output}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
