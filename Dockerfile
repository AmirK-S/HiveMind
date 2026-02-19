# ============================================================================
# HiveMind — Multi-stage Docker build
# ============================================================================
# Stage 1 (builder): Install Python dependencies via uv into .venv
# Stage 2 (runtime): Copy .venv + application code, run uvicorn
#
# Usage:
#   docker build -t hivemind .
#   docker run -p 8000:8000 --env-file .env hivemind
# ============================================================================

# ---------------------------------------------------------------------------
# Stage 1: builder — install dependencies with uv
# ---------------------------------------------------------------------------
FROM python:3.12-slim AS builder

# Install uv for fast, reproducible dependency installation
RUN pip install uv --no-cache-dir

WORKDIR /app

# Copy dependency files first (layer cache: only re-run uv sync on changes)
COPY pyproject.toml .
COPY uv.lock .

# Install production dependencies only (no dev extras) into .venv
# --frozen: respect uv.lock exactly (reproducible builds)
# --no-dev: exclude dev dependencies (pytest, openapi-python-client, etc.)
RUN uv sync --frozen --no-dev

# ---------------------------------------------------------------------------
# Stage 2: runtime — minimal image with application code only
# ---------------------------------------------------------------------------
FROM python:3.12-slim AS runtime

WORKDIR /app

# Copy the virtual environment from the builder stage (no pip/uv in runtime)
COPY --from=builder /app/.venv /app/.venv

# Copy application source code
COPY hivemind/ hivemind/

# Copy Alembic migration config (run migrations at startup or via separate job)
COPY alembic/ alembic/
COPY alembic.ini .

# Add .venv binaries to PATH so uvicorn/alembic are found directly
ENV PATH="/app/.venv/bin:$PATH"

# Expose the uvicorn port
EXPOSE 8000

# Health check for container orchestrators (Docker Swarm, Kubernetes, etc.)
# Polls /health every 30s — must respond within 5s or container is marked unhealthy
HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# OCI standard labels
LABEL org.opencontainers.image.source="https://github.com/your-org/hivemind"
LABEL org.opencontainers.image.description="HiveMind — shared memory system for AI agents"
LABEL org.opencontainers.image.licenses="MIT"

# Start the FastAPI server
# --host 0.0.0.0: bind all interfaces (required inside container)
# --port 8000: must match EXPOSE above
CMD ["uvicorn", "hivemind.server.main:app", "--host", "0.0.0.0", "--port", "8000"]
