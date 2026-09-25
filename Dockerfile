# Multi-architecture base images support linux/arm64 (64-bit Raspberry Pi OS).
FROM python:3.12-alpine@sha256:4c47124a8391cb7a9f571164147d154777cf012a4ece5f86097130d7a4478111 AS builder
COPY --from=ghcr.io/astral-sh/uv:0.9.25@sha256:13e233d08517abdafac4ead26c16d881cd77504a2c40c38c905cf3a0d70131a6 /uv /usr/local/bin/uv
WORKDIR /app
COPY pyproject.toml uv.lock ./
COPY src ./src
RUN uv sync --frozen --no-dev --extra server --no-editable

FROM python:3.12-alpine@sha256:4c47124a8391cb7a9f571164147d154777cf012a4ece5f86097130d7a4478111
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    HUE_DATA_DIR=/data \
    HUE_SEED_FILE=/app/config/library.seed.json
LABEL org.opencontainers.image.source="https://github.com/Griggum/hue-gaming"
WORKDIR /app
COPY --from=builder /app/.venv /app/.venv
COPY config/library.seed.json /app/config/library.seed.json
RUN mkdir /data && chown 10001:10001 /data
USER 10001:10001
EXPOSE 8080
CMD ["hue-portal"]
