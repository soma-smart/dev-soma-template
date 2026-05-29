#!/usr/bin/env bash
# Aggregator invoked by:
#   - .pre-commit-config.yaml (local)
#   - .claude/hooks/pre-commit-gate.sh (Claude Code)
#   - CI ci-quality.yml
#
# Fails fast on the first non-zero step. Each step is a single source of truth.

set -euo pipefail

step() {
  printf '\n>> %s\n' "$1"
}

step "ruff check"
uv run ruff check src/ tests/ scripts/

step "ruff format --check"
uv run ruff format --check src/ tests/ scripts/

step "ty check"
uv run ty check src/

step "no_third_party_in_domain"
uv run python scripts/checks/no_third_party_in_domain.py src/

step "no_naive_datetime"
uv run python scripts/checks/no_naive_datetime.py src/

step "test_naming"
uv run python scripts/checks/test_naming.py tests/

echo
echo "All quality checks passed."
