#!/usr/bin/env bash
# Claude PostToolUse(Edit/Write): observer hook that flags structural
# violations after a file change. Non-blocking: prints warnings to stderr
# so Claude sees them in the next turn and self-corrects, while pre-commit
# and CI provide the hard enforcement.

set -uo pipefail

cd "$CLAUDE_PROJECT_DIR"

WARN=0

# Read the edited path from the tool input (PostToolUse stdin is JSON).
if ! command -v jq >/dev/null 2>&1; then
  exit 0
fi

PAYLOAD=$(cat)
FILE=$(printf '%s' "$PAYLOAD" | jq -r '.tool_input.file_path // empty')
[ -z "$FILE" ] && exit 0
[ ! -f "$FILE" ] && exit 0

# Strip absolute prefix to get a path relative to the project root.
REL=${FILE#"$CLAUDE_PROJECT_DIR/"}

# 1. Third-party imports in domain.
if [[ "$REL" == src/*/domain/* ]]; then
  if ! uv run python scripts/checks/no_third_party_in_domain.py src/ >/tmp/audit-1.log 2>&1; then
    echo "WARN: domain layer purity violated:" >&2
    cat /tmp/audit-1.log >&2
    WARN=1
  fi
fi

# 2. Naive datetime in src/.
if [[ "$REL" == src/* ]]; then
  if ! uv run python scripts/checks/no_naive_datetime.py "$FILE" >/tmp/audit-2.log 2>&1; then
    echo "WARN: naive datetime detected:" >&2
    cat /tmp/audit-2.log >&2
    WARN=1
  fi
fi

# 3. Test naming and GIVEN/WHEN/THEN body.
if [[ "$REL" == tests/* && "$(basename "$REL")" == test_*.py ]]; then
  if ! uv run python scripts/checks/test_naming.py "$FILE" >/tmp/audit-3.log 2>&1; then
    echo "WARN: test naming/format violation:" >&2
    cat /tmp/audit-3.log >&2
    WARN=1
  fi
fi

# 4. Auto-format + lint Python files (ruff check --fix + ruff format).
#    Surfaces remaining unfixable issues on stderr so Claude self-corrects on
#    the next turn. Skipped on non-Python paths and on deleted files.
if [[ "$REL" == *.py ]]; then
  uv run ruff check --fix "$FILE" >/tmp/audit-ruff-check.log 2>&1
  if [ $? -ne 0 ]; then
    echo "WARN: ruff issues remaining after auto-fix on $REL:" >&2
    cat /tmp/audit-ruff-check.log >&2
    WARN=1
  fi
  uv run ruff format "$FILE" >/tmp/audit-ruff-format.log 2>&1 || true
fi

# 5. New DomainError without HTTP mapping.
if [[ "$REL" == src/*/domain/exceptions/* ]] && grep -q "class .*Error" "$FILE"; then
  ERROR_HANDLERS=$(find src -path "*/presentation/api/error_handlers.py" | head -1)
  if [ -n "$ERROR_HANDLERS" ]; then
    NEW_CLASS=$(grep -oE "class [A-Za-z_]+Error" "$FILE" | awk '{print $2}' | head -1)
    if [ -n "$NEW_CLASS" ] && ! grep -q "$NEW_CLASS" "$ERROR_HANDLERS"; then
      echo "WARN: '$NEW_CLASS' is not registered in $ERROR_HANDLERS::ERROR_HTTP_MAPPING — add an entry or the test will fail." >&2
      WARN=1
    fi
  fi
fi

# Always exit 0; observers do not block.
exit 0
