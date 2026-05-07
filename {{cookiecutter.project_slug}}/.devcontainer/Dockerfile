# Devcontainer base image. The Microsoft devcontainer image already provides
# the vscode user, git, sudo, common-utils, UID/GID auto-mapping support and
# regular security updates. We add uv and just on top.
#
# Note: just is also available as a devcontainer Feature
# (ghcr.io/guiyomh/features/just) but Features are only applied by the
# devcontainer CLI (VSCode "Reopen in Container", Codespaces). Baking just
# directly into the image makes plain `docker compose up` produce a fully
# usable environment too — same image, both flows.

FROM mcr.microsoft.com/devcontainers/python:{{ cookiecutter.python_version }}

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

# Pin just via its official install script. The script is signed by the
# project; it picks the right prebuilt binary for the target arch.
RUN curl --proto '=https' --tlsv1.2 -sSf https://just.systems/install.sh \
    | bash -s -- --to /usr/local/bin

USER vscode
