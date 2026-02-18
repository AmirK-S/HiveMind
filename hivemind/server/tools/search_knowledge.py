"""search_knowledge MCP tool for HiveMind.

Supports two modes:
1. Search mode (query provided):
   query text -> embed query -> cosine similarity search -> summary-tier results
2. Fetch mode (id provided):
   item ID -> full content retrieval

Security (ACL-01):
- org_id is extracted from bearer token, NEVER from tool arguments
- Results scoped to: (org_id == :org_id) OR (is_public == True)
  — agents see their private namespace + public commons

Summary-tier response (~30-50 tokens per result):
  id, title (first 80 chars of content), category, confidence, org_attribution,
  relevance_score (1 - cosine_distance)

Pagination: offset-based, cursor encoded as base64 integer.
"""

from __future__ import annotations

import base64

from fastmcp.server.dependencies import get_http_headers
from mcp.types import CallToolResult, TextContent
from sqlalchemy import func, select

from hivemind.config import settings
from hivemind.db.models import KnowledgeCategory, KnowledgeItem
from hivemind.db.session import get_session
from hivemind.pipeline.embedder import get_embedder
from hivemind.server.auth import decode_token


# ---------------------------------------------------------------------------
# Cursor encoding helpers
# ---------------------------------------------------------------------------


def encode_cursor(offset: int) -> str:
    """Encode an integer offset as a URL-safe base64 cursor string."""
    return base64.urlsafe_b64encode(str(offset).encode()).decode()


def decode_cursor(cursor: str) -> int:
    """Decode a base64 cursor string back to an integer offset.

    Returns 0 on any decoding error (safe default — starts from beginning).
    """
    try:
        return int(base64.urlsafe_b64decode(cursor.encode()).decode())
    except Exception:
        return 0


# ---------------------------------------------------------------------------
# Auth helper (shared pattern with add_knowledge)
# ---------------------------------------------------------------------------


def _extract_auth(headers: dict[str, str]):
    """Extract and decode the Authorization bearer token."""
    auth_header = headers.get("authorization", "")
    if not auth_header.startswith("Bearer "):
        raise ValueError("Missing or invalid Authorization header. Expected 'Bearer <token>'.")
    token = auth_header[len("Bearer "):]
    return decode_token(token)


def _auth_error(message: str) -> CallToolResult:
    """Return a structured MCP isError response for auth failures."""
    return CallToolResult(
        content=[TextContent(type="text", text=message)],
        isError=True,
    )


# ---------------------------------------------------------------------------
# search_knowledge tool
# ---------------------------------------------------------------------------


async def search_knowledge(
    query: str | None = None,
    id: str | None = None,
    category: str | None = None,
    limit: int = 10,
    cursor: str | None = None,
) -> dict | CallToolResult:
    """Search or fetch knowledge items from HiveMind.

    Search mode (query provided):
        Embeds the query text and performs a cosine similarity search over the
        knowledge commons. Returns summary-tier results (~30-50 tokens each).

    Fetch mode (id provided):
        Returns full content for a specific knowledge item by UUID.

    Args:
        query:    Text to search for (required for search mode).
        id:       UUID of a specific knowledge item to fetch (fetch mode).
        category: Optional category filter (must be a valid KnowledgeCategory).
        limit:    Maximum results to return (capped at settings.max_search_limit).
        cursor:   Pagination cursor from a previous response's next_cursor field.

    Returns:
        Search mode: dict with results[], total_found, next_cursor.
        Fetch mode:  dict with full item fields.
        Error:       CallToolResult with isError=True.
    """
    # Extract auth context — org_id never comes from tool arguments (ACL-01)
    try:
        headers = get_http_headers()
        auth = _extract_auth(headers)
    except ValueError as exc:
        return _auth_error(str(exc))

    org_id = auth.org_id

    # Validate that at least one mode parameter is provided
    if query is None and id is None:
        return CallToolResult(
            content=[TextContent(
                type="text",
                text="Provide either 'query' for search or 'id' to fetch a specific item.",
            )],
            isError=True,
        )

    # -----------------------------------------------------------------------
    # Fetch mode: return full content for a specific item
    # -----------------------------------------------------------------------
    if id is not None:
        return await _fetch_by_id(id=id, org_id=org_id)

    # -----------------------------------------------------------------------
    # Search mode: embed query -> cosine search -> summary tier
    # -----------------------------------------------------------------------
    return await _search(
        query=query,
        org_id=org_id,
        category=category,
        limit=limit,
        cursor=cursor,
    )


async def _fetch_by_id(id: str, org_id: str) -> dict | CallToolResult:
    """Fetch a single knowledge item by ID with org isolation."""
    import uuid as _uuid

    # Validate UUID format
    try:
        item_uuid = _uuid.UUID(id)
    except ValueError:
        return CallToolResult(
            content=[TextContent(type="text", text=f"Invalid id format: '{id}' is not a valid UUID.")],
            isError=True,
        )

    async with get_session() as session:
        stmt = select(KnowledgeItem).where(
            KnowledgeItem.id == item_uuid,
            # Org isolation: own items OR public items (never expose other orgs' private data)
            (KnowledgeItem.org_id == org_id) | (KnowledgeItem.is_public == True),  # noqa: E712
            KnowledgeItem.deleted_at.is_(None),  # exclude soft-deleted items
        )
        result = await session.execute(stmt)
        item = result.scalar_one_or_none()

    if item is None:
        # Per research pitfall 6: never reveal existence of items in other orgs
        return CallToolResult(
            content=[TextContent(
                type="text",
                text=f"Knowledge item '{id}' not found.",
            )],
            isError=True,
        )

    return {
        "id": str(item.id),
        "content": item.content,
        "category": item.category.value,
        "confidence": item.confidence,
        "framework": item.framework,
        "language": item.language,
        "version": item.version,
        "tags": item.tags,
        "org_attribution": item.org_id,
        "contributed_at": item.contributed_at.isoformat(),
    }


async def _search(
    query: str,
    org_id: str,
    category: str | None,
    limit: int,
    cursor: str | None,
) -> dict | CallToolResult:
    """Embed query and return cosine-ranked summary-tier results."""
    # Cap limit to configured maximum
    limit = min(limit, settings.max_search_limit)

    # Decode cursor to offset
    offset = decode_cursor(cursor) if cursor else 0

    # Optional category filter validation
    category_enum: KnowledgeCategory | None = None
    if category is not None:
        try:
            category_enum = KnowledgeCategory(category)
        except ValueError:
            valid_values = [c.value for c in KnowledgeCategory]
            return CallToolResult(
                content=[TextContent(
                    type="text",
                    text=(
                        f"Invalid category '{category}'. "
                        f"Valid values: {', '.join(valid_values)}"
                    ),
                )],
                isError=True,
            )

    # Embed the query text using the singleton embedding provider
    query_embedding = get_embedder().embed(query)

    async with get_session() as session:
        # Build the search query with cosine distance ranking
        distance_col = KnowledgeItem.embedding.cosine_distance(query_embedding).label("distance")

        stmt = (
            select(KnowledgeItem, distance_col)
            .where(
                # Org isolation: own items + public commons
                (KnowledgeItem.org_id == org_id) | (KnowledgeItem.is_public == True)  # noqa: E712
            )
            .where(KnowledgeItem.embedding.isnot(None))  # skip items without embeddings
            .where(KnowledgeItem.deleted_at.is_(None))  # exclude soft-deleted items
        )

        if category_enum is not None:
            stmt = stmt.where(KnowledgeItem.category == category_enum)

        # Count total matching items for pagination metadata
        count_subquery = stmt.subquery()
        total_result = await session.execute(
            select(func.count()).select_from(count_subquery)
        )
        total_count = total_result.scalar_one()

        # Apply ordering, pagination
        stmt = stmt.order_by(distance_col.asc()).limit(limit).offset(offset)

        result = await session.execute(stmt)
        rows = result.all()

    # Build summary-tier results (~30-50 tokens per result)
    results = [
        {
            "id": str(item.id),
            # First 80 chars as title — gives agent enough context to decide if worth fetching
            "title": item.content[:80] + ("..." if len(item.content) > 80 else ""),
            "category": item.category.value,
            "confidence": item.confidence,
            "org_attribution": item.org_id,
            # Convert cosine distance [0..2] to similarity score [1..−1]
            # For unit vectors: distance 0 = identical, distance 2 = opposite
            "relevance_score": round(1 - distance, 4),
        }
        for item, distance in rows
    ]

    has_more = (offset + limit) < total_count
    next_cursor = encode_cursor(offset + limit) if has_more else None

    return {
        "results": results,
        "total_found": total_count,
        "next_cursor": next_cursor,
    }
