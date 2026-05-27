FROM mcr.microsoft.com/devcontainers/base:bookworm

RUN curl -LsSf https://astral.sh/uv/install.sh | UV_INSTALL_DIR=/usr/local/bin sh

RUN curl --proto '=https' --tlsv1.2 -sSf https://just.systems/install.sh \
    | bash -s -- --to /usr/local/bin

USER vscode

RUN uv python install {{ cookiecutter.python_version }}
