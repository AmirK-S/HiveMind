# ============================================================================
# HiveMind: multi-stage Docker build
# ============================================================================
# Stage 1 (builder): install Python dependencies with uv into .venv
# Stage 2 (runtime): copy .venv plus application code, migrate, run uvicorn
#
# Usage:
#   docker build -t hivemind .
#   docker run -p 8000:8000 --env-file .env hivemind
# ============================================================================

# ---------------------------------------------------------------------------
# Stage 1: builder
# ---------------------------------------------------------------------------
FROM python:3.12-slim AS builder

RUN pip install uv --no-cache-dir

WORKDIR /app

# Dependency files first, so the layer is reused until they change.
COPY pyproject.toml .
COPY uv.lock .

# --frozen: respect uv.lock exactly (reproducible builds)
# --no-dev: skip the test tooling
# --no-install-project: the application is copied as source below, not installed
# --group models: the spaCy model presidio loads at startup, pinned in uv.lock,
# so it lands in .venv here and the runtime image never downloads it.
RUN uv sync --frozen --no-dev --no-install-project --group models

# ---------------------------------------------------------------------------
# Stage 2: runtime
# ---------------------------------------------------------------------------
FROM python:3.12-slim AS runtime

WORKDIR /app

# The virtual environment only; the runtime image carries neither pip nor uv.
COPY --from=builder /app/.venv /app/.venv

COPY hivemind/ hivemind/
COPY alembic/ alembic/
COPY alembic.ini .
COPY docker/entrypoint.sh /app/entrypoint.sh

# The application is not installed in the venv: make it importable by path.
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONPATH="/app" \
    PYTHONUNBUFFERED=1

EXPOSE 8000

# python:3.12-slim ships no curl; probe /health with the interpreter.
# start-period covers migrations, the first-run model download and the warm-up.
HEALTHCHECK --interval=30s --timeout=5s --start-period=240s --retries=3 \
    CMD ["python", "-c", "import urllib.request, sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=4).status == 200 else 1)"]

LABEL org.opencontainers.image.source="https://github.com/AmirK-S/HiveMind"
LABEL org.opencontainers.image.description="HiveMind: shared memory for AI agents, served over MCP"
LABEL org.opencontainers.image.licenses="MIT"

# Migrations first, then uvicorn (see docker/entrypoint.sh).
ENTRYPOINT ["/app/entrypoint.sh"]
