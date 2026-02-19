"""SSE streaming endpoint for real-time knowledge feed (DASH-01).

Endpoint:
- GET /stream/feed — Server-Sent Events feed for knowledge published events

Uses PostgreSQL LISTEN/NOTIFY on the 'knowledge_published' channel to push
real-time events to connected clients.

Two event types are emitted:
- "public"  — item is_public=True; delivered to all connected clients
- "private" — item is_public=False; delivered only to the matching org

A "ping" event is sent every 25 seconds to keep the SSE connection alive
through proxies that close idle connections at 60 seconds.

Architecture:
- Dedicated asyncpg connection (NOT SQLAlchemy pool) for LISTEN/NOTIFY
  because LISTEN requires a persistent idle connection, not a transactional one.
- asyncio.Queue bridges the asyncpg listener callback to the async generator.
- EventSourceResponse (sse-starlette) handles SSE framing and ping intervals.

Requirements: DASH-01.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import AsyncGenerator

import asyncpg
from fastapi import APIRouter, Depends
from sse_starlette.sse import EventSourceResponse

from hivemind.api.auth import require_api_key
from hivemind.config import settings
from hivemind.db.models import ApiKey

logger = logging.getLogger(__name__)

stream_router = APIRouter(prefix="/stream", tags=["stream"])

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _raw_database_url(url: str) -> str:
    """Strip the SQLAlchemy dialect suffix from a database URL.

    SQLAlchemy uses ``postgresql+asyncpg://...`` but raw asyncpg needs
    ``postgresql://...``.  This helper strips the ``+asyncpg`` suffix so
    the URL is compatible with asyncpg.connect().

    Args:
        url: SQLAlchemy-style database URL (may or may not have dialect suffix).

    Returns:
        PostgreSQL URL without SQLAlchemy dialect suffix.
    """
    return url.replace("+asyncpg", "")


async def notify_knowledge_published(session, item_data: dict) -> None:
    """Emit a PostgreSQL NOTIFY on the 'knowledge_published' channel.

    Called after a KnowledgeItem is committed to the database to trigger
    SSE delivery to connected dashboard clients.

    The payload is a JSON object with the following keys:
    - id:        UUID string of the new KnowledgeItem
    - is_public: bool — routes to "public" or "private" SSE event type
    - org_id:    string — used for namespace isolation on private events
    - category:  string — knowledge category value
    - title:     string — first 80 chars of content (display label)

    Args:
        session:   Active SQLAlchemy AsyncSession in the current request context.
        item_data: Dict with keys: id, is_public, org_id, category, title.
    """
    from sqlalchemy import text  # noqa: PLC0415

    payload = json.dumps(item_data)
    await session.execute(
        text("SELECT pg_notify('knowledge_published', :payload)"),
        {"payload": payload},
    )


# ---------------------------------------------------------------------------
# SSE feed endpoint
# ---------------------------------------------------------------------------


@stream_router.get(
    "/feed",
    operation_id="stream_knowledge_feed",
    summary="Real-time knowledge feed via Server-Sent Events",
    description=(
        "Streams real-time knowledge events as the commons grows. "
        "Public events are delivered to all connected clients. "
        "Private events are scoped to the calling organisation. "
        "A ping event is emitted every 25 seconds to prevent proxy timeouts."
    ),
    response_class=EventSourceResponse,
)
async def stream_knowledge_feed(
    api_key_record: ApiKey = Depends(require_api_key),
) -> EventSourceResponse:
    """Stream knowledge events for the authenticated organisation.

    Opens a dedicated asyncpg connection for PostgreSQL LISTEN/NOTIFY and
    yields SSE events as items are published to the knowledge_published channel.

    org_id is extracted from the authenticated API key — never from query params.
    """
    org_id = str(api_key_record.org_id)

    async def event_generator() -> AsyncGenerator[dict, None]:
        """Async generator that yields SSE events from the knowledge_published channel."""
        conn: asyncpg.Connection | None = None
        queue: asyncio.Queue = asyncio.Queue()

        def _listener(connection, pid, channel, payload_str):
            """Asyncpg LISTEN callback — runs in the asyncpg event loop thread."""
            try:
                data = json.loads(payload_str)
                queue.put_nowait(data)
            except (json.JSONDecodeError, Exception) as exc:
                logger.warning("SSE: failed to parse NOTIFY payload: %s", exc)

        try:
            raw_url = _raw_database_url(settings.database_url)
            conn = await asyncpg.connect(raw_url)
            await conn.add_listener("knowledge_published", _listener)
            logger.info("SSE: client connected for org_id=%s", org_id)

            while True:
                try:
                    # Wait for next event with 30s timeout — yield ping on timeout
                    item = await asyncio.wait_for(queue.get(), timeout=30.0)
                except asyncio.TimeoutError:
                    # Keepalive ping — prevents proxy/load-balancer from closing idle connection
                    yield {"event": "ping", "data": ""}
                    continue

                # Route by visibility
                is_public = item.get("is_public", False)
                item_org_id = str(item.get("org_id", ""))

                if is_public:
                    # Public event — deliver to all connected clients
                    yield {"event": "public", "data": json.dumps(item)}
                elif item_org_id == org_id:
                    # Private event — deliver only to the matching org
                    yield {"event": "private", "data": json.dumps(item)}
                # else: private event for a different org — skip silently

        except asyncio.CancelledError:
            # Client disconnected — clean up silently
            logger.info("SSE: client disconnected for org_id=%s", org_id)
            raise
        except Exception as exc:
            logger.error("SSE: error in event generator for org_id=%s: %s", org_id, exc)
        finally:
            if conn is not None:
                try:
                    await conn.remove_listener("knowledge_published", _listener)
                    await conn.close()
                except Exception:
                    pass  # best-effort cleanup

    return EventSourceResponse(event_generator(), ping=25)
