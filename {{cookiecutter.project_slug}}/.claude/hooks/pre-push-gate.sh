#!/usr/bin/env bash
# Claude PreToolUse(git push): runs unit + integration tests. exit 2 blocks
# the push. CI catches everything else (mutation, e2e, helm, security).

set -euo pipefail

cd "$CLAUDE_PROJECT_DIR"

if ! uv run pytest -m "unit or integration" -q > /tmp/soma-prepush.log 2>&1; then
  echo ""
  echo "Tests failed. Push blocked."
  tail -40 /tmp/soma-prepush.log
  echo ""
  echo "Full log: /tmp/soma-prepush.log"
  exit 2
fi

exit 0
