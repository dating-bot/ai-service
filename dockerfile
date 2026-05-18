FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim AS python3

RUN apt update && apt upgrade -y && apt install -y \
    build-essential \
    curl \
    tzdata \
    && curl -L https://github.com/grpc-ecosystem/grpc-health-probe/releases/download/v0.4.33/grpc_health_probe-linux-amd64 -o /usr/local/bin/grpc_health_probe \
    && chmod +x /usr/local/bin/grpc_health_probe

WORKDIR /app

ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy
ENV TZ=Europe/Moscow

RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --frozen --no-install-project

ADD . /app
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen

ENV PATH="/app/.venv/bin:$PATH"
ENTRYPOINT []
