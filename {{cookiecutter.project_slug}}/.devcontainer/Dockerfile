# Devcontainer base image. The Microsoft devcontainer image already provides
# the vscode user, git, sudo, common-utils, UID/GID auto-mapping support and
# regular security updates. We only add uv on top.

FROM mcr.microsoft.com/devcontainers/python:{{ cookiecutter.python_version }}

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

USER vscode
