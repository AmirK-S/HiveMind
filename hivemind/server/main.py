"""HiveMind MCP server entry point.

Starts a FastMCP server with Streamable HTTP transport at /mcp.
Lifespan initialises the PII pipeline (GLiNER model) and embedding provider
at startup so the first agent request is not penalised with a cold-start delay.

Entry point:
    uvicorn hivemind.server.main:app --host 0.0.0.0 --port 8000

Or run directly:
    python -m hivemind.server.main
"""

from __future__ import annotations

import datetime
import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastmcp import FastMCP
from fastmcp.tools import Tool

from hivemind.db.models import DeploymentConfig
from hivemind.db.session import engine, get_session
from hivemind.pipeline.embedder import get_embedder
from hivemind.pipeline.pii import PIIPipeline
from hivemind.server.tools.add_knowledge import add_knowledge
from hivemind.server.tools.search_knowledge import search_knowledge

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Stub tools — Plan 04 will replace these with full implementations
# ---------------------------------------------------------------------------


async def list_knowledge(
    category: str | None = None,
    limit: int = 10,
    cursor: str | None = None,
) -> dict:
    """List knowledge items (stub — implemented in Plan 04)."""
    return {"error": "Not yet implemented"}


async def delete_knowledge(id: str) -> dict:
    """Delete a knowledge item (stub — implemented in Plan 04)."""
    return {"error": "Not yet implemented"}


# ---------------------------------------------------------------------------
# Lifespan: warm-up expensive models and store deployment config
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(server: FastMCP) -> AsyncIterator[None]:
    """Lifespan context manager: startup init and shutdown cleanup.

    Startup order:
    1. Initialize PIIPipeline singleton — triggers GLiNER model load (~400 MB)
    2. Initialize EmbeddingProvider singleton — loads sentence-transformers model
    3. Store or verify deployment config (embedding model name + revision, KM-08)
    4. Yield — server handles requests

    Shutdown:
    5. Dispose the async engine and close all pooled connections
    """
    logger.info("HiveMind server starting up...")

    # 1. PII pipeline (blocks until GLiNER is loaded)
    logger.info("Loading PII pipeline (GLiNER model)...")
    PIIPipeline.get_instance()
    logger.info("PII pipeline ready.")

    # 2. Embedding provider
    logger.info("Loading embedding provider...")
    embedder = get_embedder()
    logger.info(
        "Embedding provider ready: %s (dims=%d)",
        embedder.model_id,
        embedder.dimensions,
    )

    # 3. Store deployment config — KM-08 model drift detection
    await _store_deployment_config(embedder)

    yield

    # 5. Cleanup: dispose async engine
    logger.info("HiveMind server shutting down — disposing database engine...")
    await engine.dispose()
    logger.info("Database engine disposed.")


async def _store_deployment_config(embedder) -> None:
    """Store or verify embedding model deployment config in the database.

    On first startup: INSERT model_name and model_revision.
    On subsequent startups: SELECT and compare — log a warning if the model
    changed (but don't block startup; an operator should handle the drift).
    """
    model_name_key = "embedding_model_name"
    model_revision_key = "embedding_model_revision"

    current_name = embedder.model_id
    current_revision = embedder.model_revision or "unknown"

    from sqlalchemy import select  # noqa: PLC0415

    async with get_session() as session:
        # Try to read existing deployment config
        result = await session.execute(
            select(DeploymentConfig).where(
                DeploymentConfig.key.in_([model_name_key, model_revision_key])
            )
        )
        rows = {row.key: row.value for row in result.scalars().all()}

        if not rows:
            # First startup — insert both keys
            now = datetime.datetime.now(datetime.timezone.utc)
            session.add(DeploymentConfig(
                key=model_name_key,
                value=current_name,
                created_at=now,
                updated_at=now,
            ))
            session.add(DeploymentConfig(
                key=model_revision_key,
                value=current_revision,
                created_at=now,
                updated_at=now,
            ))
            await session.commit()
            logger.info(
                "Deployment config stored: %s @ %s", current_name, current_revision
            )
        else:
            # Subsequent startup — compare and warn on drift
            stored_name = rows.get(model_name_key, "")
            stored_revision = rows.get(model_revision_key, "")

            if stored_name != current_name:
                logger.warning(
                    "Embedding model changed! Stored: %s, Current: %s. "
                    "Vectors from old model are incompatible — consider re-embedding.",
                    stored_name,
                    current_name,
                )
            elif stored_revision != current_revision and stored_revision != "unknown":
                logger.warning(
                    "Embedding model revision changed! Stored: %s, Current: %s. "
                    "Verify vectors are still compatible.",
                    stored_revision,
                    current_revision,
                )
            else:
                logger.info(
                    "Deployment config verified: %s @ %s", current_name, current_revision
                )


# ---------------------------------------------------------------------------
# FastMCP server instance
# ---------------------------------------------------------------------------

mcp = FastMCP(
    "HiveMind",
    lifespan=lifespan,
)

# Register tools using Tool.from_function() — the correct FastMCP v2 API.
# mcp.add_tool() expects a Tool instance, not a raw function.
mcp.add_tool(Tool.from_function(add_knowledge))
mcp.add_tool(Tool.from_function(search_knowledge))
mcp.add_tool(Tool.from_function(list_knowledge))
mcp.add_tool(Tool.from_function(delete_knowledge))

# ---------------------------------------------------------------------------
# ASGI app: Streamable HTTP at /mcp
# ---------------------------------------------------------------------------

# Create the Starlette ASGI app from FastMCP with Streamable HTTP transport.
# stateless_http=True allows horizontal scaling — no per-session state is held.
# json_response=True returns JSON instead of SSE streams for compatibility.
_mcp_app = mcp.http_app(
    path="/mcp",
    transport="streamable-http",
    stateless_http=True,
    json_response=True,
)

# Wrap in a FastAPI app to add the /health endpoint and any future REST routes.
# We mount the MCP Starlette app under the FastAPI instance.
app = FastAPI(
    title="HiveMind",
    description="Shared memory system for AI agents — MCP server",
    version="0.1.0",
    lifespan=_mcp_app.lifespan if hasattr(_mcp_app, "lifespan") else None,
)


@app.get("/health")
async def health() -> JSONResponse:
    """Simple health check endpoint for load balancers and readiness probes."""
    return JSONResponse({"status": "ok", "service": "hivemind"})


# Mount the MCP ASGI app at /mcp
app.mount("/mcp", _mcp_app)
