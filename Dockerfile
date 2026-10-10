# syntax=docker/dockerfile:1

# ─────────────────────────────────────────────────────────────────────────────
# Stage 1: Build Episteme Studio Frontend (Vite / React / TypeScript)
# ─────────────────────────────────────────────────────────────────────────────
FROM node:20-slim AS frontend-builder
WORKDIR /app/packages/episteme-studio/frontend

# Install package dependencies first for layer caching
COPY packages/episteme-studio/frontend/package*.json ./
RUN npm ci

# Copy full frontend sources and compile static bundle into static/
COPY packages/episteme-studio/frontend ./
RUN npm run build

# ─────────────────────────────────────────────────────────────────────────────
# Stage 2: Episteme Studio Runtime (Python 3.13 + uv)
# ─────────────────────────────────────────────────────────────────────────────
FROM python:3.13-slim

WORKDIR /app

# Install runtime system packages, build tools, and certificates
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    ca-certificates \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv from official image
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

# Copy workspace pyproject declarations
COPY pyproject.toml uv.lock README.md ./
COPY packages/epistemetrics packages/epistemetrics
COPY packages/episteme-pipeline packages/episteme-pipeline
COPY packages/episteme-studio packages/episteme-studio

# Copy pre-compiled frontend assets from Stage 1 into studio static dir
COPY --from=frontend-builder /app/packages/episteme-studio/src/episteme_studio/static /app/packages/episteme-studio/src/episteme_studio/static

# Install workspace dependencies in production mode
ENV UV_COMPILE_BYTECODE=1
RUN uv sync --frozen --no-dev

# Prepare persistent data directories
RUN mkdir -p /app/.pipeline_runs /app/.pipeline_artifacts /app/evaluation/reports /app/data/uploads

# Configure unprivileged user
RUN groupadd -g 10001 episteme && \
    useradd -u 10001 -g episteme -m -s /bin/bash episteme && \
    chown -R episteme:episteme /app

USER episteme

ENV HOST=0.0.0.0
ENV PORT=8000
ENV PYTHONUNBUFFERED=1

EXPOSE 8000

# Default entrypoint launches Episteme Studio CLI
ENTRYPOINT ["uv", "run", "episteme-studio"]
CMD ["serve", "--host", "0.0.0.0", "--port", "8000", "--demo"]
