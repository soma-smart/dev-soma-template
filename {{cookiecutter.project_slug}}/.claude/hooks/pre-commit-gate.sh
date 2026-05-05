#!/usr/bin/env bash
# Claude PreToolUse(git commit): runs the same quality script as pre-commit
# would on a developer's machine. exit 2 blocks the commit.

set -euo pipefail

cd "$CLAUDE_PROJECT_DIR"

if ! bash scripts/checks/quality.sh > /tmp/soma-quality.log 2>&1; then
  echo ""
  echo "Quality checks failed. Commit blocked."
  echo "Tail of the log:"
  tail -25 /tmp/soma-quality.log
  echo ""
  echo "Full log: /tmp/soma-quality.log"
  exit 2
fi

exit 0
