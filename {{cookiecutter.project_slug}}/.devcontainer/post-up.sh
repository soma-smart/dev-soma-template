#!/bin/bash
# Configure docker.sock access for the vscode user.
# Runs at container startup. Idempotent. Safe to re-run.
#
# This is needed when the devcontainer stack is brought up via plain
# `docker compose up` (i.e. NOT via the devcontainer CLI). The
# docker-outside-of-docker:1 Feature in devcontainer.json normally
# detects the host's docker.sock GID and adds the vscode user to a
# matching group, but the Feature only runs through the CLI flow.
# Plain `docker compose up` bypasses it, so this script is the fallback
# that the compose `command:` invokes via sudo before sleeping.
#
# Without this, integration tests that use testcontainers will skip
# silently because the vscode user cannot reach /var/run/docker.sock.
set -euo pipefail

if [ ! -S /var/run/docker.sock ]; then
    echo "[post-up] docker.sock not mounted; nothing to configure."
    exit 0
fi

SOCK_GID="$(stat -c '%g' /var/run/docker.sock)"

# If a group with that GID doesn't exist yet, create one named docker-host.
if ! getent group "$SOCK_GID" > /dev/null 2>&1; then
    groupadd -g "$SOCK_GID" docker-host
    echo "[post-up] Created group docker-host (GID $SOCK_GID)."
fi

GROUP_NAME="$(getent group "$SOCK_GID" | cut -d: -f1)"

# Idempotent: usermod -aG is a no-op if vscode is already in the group.
if ! id -nG vscode | tr ' ' '\n' | grep -qx "$GROUP_NAME"; then
    usermod -aG "$GROUP_NAME" vscode
    echo "[post-up] Added vscode to $GROUP_NAME (GID $SOCK_GID)."
else
    echo "[post-up] vscode already in $GROUP_NAME; nothing to change."
fi

echo "[post-up] Docker socket access ready for vscode."
