#!/usr/bin/env bash
# Claude UserPromptSubmit: injects a short reminder pointing to the right
# skill based on intent keywords detected in the user's prompt. Helps Claude
# pick the correct skill before acting.

set -uo pipefail

if ! command -v jq >/dev/null 2>&1; then
  exit 0
fi

PAYLOAD=$(cat)
PROMPT=$(printf '%s' "$PAYLOAD" | jq -r '.prompt // empty' | tr '[:upper:]' '[:lower:]')

if [ -z "$PROMPT" ]; then
  exit 0
fi

emit() {
  jq -n --arg context "$1" '{ "hookSpecificOutput": { "additionalContext": $context } }'
}

# Order matters: most specific first.
if echo "$PROMPT" | grep -Eq "(migration|alembic|schema change|new table)"; then
  emit "Reminder: use the database-and-migrations skill. Always read the autogenerate output, ensure downgrade() is non-empty, and add a round-trip migration test."
elif echo "$PROMPT" | grep -Eq "(new endpoint|add a feature|new use case|new api|create.*endpoint)"; then
  emit "Reminder: use the building-a-feature skill, paired with tdd-workflow (failing test first). It walks plan -> use case -> persistence -> route -> wiring. The reference feature is the User signup flow."
elif echo "$PROMPT" | grep -Eq "(fix|bug|regression)"; then
  emit "Reminder: use the tdd-workflow skill. Write a failing unit test that reproduces the bug before changing production code."
elif echo "$PROMPT" | grep -Eq "(domain error|new error|exception)"; then
  emit "Reminder: use the writing-domain-code skill (exceptions section). New DomainError subclasses MUST be registered in presentation/api/error_handlers.py::ERROR_HTTP_MAPPING."
elif echo "$PROMPT" | grep -Eq "(helm|chart|deployment)"; then
  emit "Reminder: use the writing-a-helm-change skill. Verify with helm lint + helm template -f values-prod.yaml | kubeconform."
elif echo "$PROMPT" | grep -Eq "(test|tdd|mutation)"; then
  emit "Reminder: use the tdd-workflow skill. Unit tests use Fakes only (zero mocks); GIVEN/WHEN/THEN naming and body. E2E: 1 happy + 1 critical error per endpoint, do not duplicate use case branches."
fi

exit 0
