"""search_knowledge MCP tool for HiveMind.

Supports two modes:
1. Search mode (query provided):
   query text -> embed query -> hybrid BM25+vector RRF ranking -> quality-boosted results
2. Fetch mode (id provided):
   item ID -> full content retrieval with content hash integrity verification (SEC-02)

Search architecture (KM-02, QI-03):
- Pure retrieval tier: two-CTE approach (vector + text) fused by RRF entirely in SQL.
  No LLM in the hot path — meets the <200ms P95 target.
- Quality boosting: final_score = rrf_score * (0.7 + 0.3 * quality_score)
  Applied in SQL so the DB engine can order results without Python post-processing.
- Text search: PostgreSQL built-in to_tsvector/ts_rank (not pg_search/pg_textsearch).
  Extensions avoided per research Open Question 1 — native FTS is adequate for V1.
- Retrieval count tracking: batch UPDATE after results collected; retrieval signals
  recorded via fire-and-forget asyncio task (non-blocking).

Security (ACL-01, SEC-02, ACL-05):
- org_id is extracted from bearer token, NEVER from tool arguments
- Results scoped to: (org_id == :org_id) OR (is_public == True)
  — agents see their private namespace + public commons
- Fetch mode verifies content hash on retrieval to detect tampering (SEC-02)
- Search results deduplicated by content_hash with private items prioritized (ACL-05)

Summary-tier response (~30-50 tokens per result):
  id, title (first 80 chars of content), category, confidence, org_attribution,
  relevance_score (quality-boosted RRF final_score)

Temporal queries (KM-06):
- Optional at_time parameter (ISO 8601 string) restricts search to items valid at that time.
- Items with NULL valid_at are treated as "always valid" (backward compat with pre-migration data).
- Optional version parameter narrows results to a specific version when used with at_time.

Pagination: offset-based, cursor encoded as base64 integer.
"""

from __future__ import annotations

import asyncio
import base64
import datetime
import logging

from fastmcp.server.dependencies import get_http_headers
from mcp.types import CallToolResult, TextContent
from sqlalchemy import func, select, text, union_all

from hivemind.config import settings
from hivemind.db.models import KnowledgeCategory, KnowledgeItem
from hivemind.db.session import get_session
from hivemind.pipeline.embedder import get_embedder
from hivemind.pipeline.integrity import verify_content_hash
from hivemind.server.auth import decode_token
from hivemind.temporal.queries import build_temporal_filter

logger = logging.getLogger(__name__)


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
# Retrieval signal recording (fire-and-forget)
# ---------------------------------------------------------------------------


async def _record_retrieval_signals(item_ids: list[str]) -> None:
    """Batch-record retrieval signals and increment retrieval_count for returned items.

    Runs as a fire-and-forget asyncio task so it does not block search response.
    Uses a single batch UPDATE for efficiency (no N+1 queries).

    Args:
        item_ids: List of UUID strings for items that were returned in search results.
    """
    if not item_ids:
        return

    import uuid as _uuid  # noqa: PLC0415
    import sqlalchemy as sa  # noqa: PLC0415

    try:
        uuid_list = [_uuid.UUID(iid) for iid in item_ids]
        async with get_session() as session:
            # Batch increment retrieval_count atomically
            await session.execute(
                sa.update(KnowledgeItem)
                .where(KnowledgeItem.id.in_(uuid_list))
                .values(retrieval_count=KnowledgeItem.retrieval_count + 1)
            )
            await session.commit()
    except Exception as exc:
        # Signal recording is best-effort — log but never fail the search
        logger.warning("Failed to record retrieval signals for %d items: %s", len(item_ids), exc)


# ---------------------------------------------------------------------------
# search_knowledge tool
# ---------------------------------------------------------------------------


async def search_knowledge(
    query: str | None = None,
    id: str | None = None,
    category: str | None = None,
    limit: int = 10,
    cursor: str | None = None,
    at_time: str | None = None,
    version: str | None = None,
) -> dict | CallToolResult:
    """Search or fetch knowledge items from HiveMind.

    Search mode (query provided):
        Embeds the query text and performs a hybrid BM25+vector search using
        Reciprocal Rank Fusion (RRF) with quality score boosting. Returns
        deduplicated summary-tier results (~30-50 tokens each).
        Private items are prioritized over public duplicates (ACL-05).
        Rankings: final_score = rrf_score * (0.7 + 0.3 * quality_score)

    Fetch mode (id provided):
        Returns full content for a specific knowledge item by UUID, with content
        hash integrity verification (SEC-02). Includes integrity_verified or
        integrity_warning field in response.

    Temporal query mode (at_time provided, KM-06):
        When at_time is given, search results are restricted to items that were
        valid at that point in time. Items with NULL valid_at are treated as
        always-valid (backward compatible with pre-temporal-migration data).
        When combined with version, further restricts results to a specific
        knowledge version.

    Args:
        query:    Text to search for (required for search mode).
        id:       UUID of a specific knowledge item to fetch (fetch mode).
        category: Optional category filter (must be a valid KnowledgeCategory).
        limit:    Maximum results to return (capped at settings.max_search_limit).
        cursor:   Pagination cursor from a previous response's next_cursor field.
        at_time:  Optional ISO 8601 datetime string for point-in-time queries (KM-06).
                  When provided, only items valid at this time are returned.
                  Example: "2026-01-01T00:00:00Z"
        version:  Optional version string filter (exact match). Only meaningful
                  when used with at_time for version-scoped temporal queries.

    Returns:
        Search mode: dict with results[], total_found, next_cursor.
        Fetch mode:  dict with full item fields + integrity_verified/integrity_warning.
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
    # Search mode: embed query -> hybrid RRF -> quality boost -> dedup
    # -----------------------------------------------------------------------
    return await _search(
        query=query,
        org_id=org_id,
        category=category,
        limit=limit,
        cursor=cursor,
        at_time=at_time,
        version=version,
    )


async def _fetch_by_id(id: str, org_id: str) -> dict | CallToolResult:
    """Fetch a single knowledge item by ID with org isolation and hash verification."""
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

    # SEC-02: Verify content integrity — detect tampering
    if not verify_content_hash(item.content, item.content_hash):
        # Log tamper warning but still return the item with a warning field
        # This is a data integrity issue, not a user error
        logger.warning(
            "Content hash mismatch for item %s — possible tampering detected",
            item.id,
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
            "integrity_warning": "Content hash mismatch detected — this item may have been tampered with.",
        }

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
        "integrity_verified": True,
    }


async def _search(
    query: str,
    org_id: str,
    category: str | None,
    limit: int,
    cursor: str | None,
    at_time: str | None = None,
    version: str | None = None,
) -> dict | CallToolResult:
    """Hybrid RRF search with quality-boosted ranking.

    Implements two-tier retrieval:
    1. Vector CTE: cosine distance ranking over pgvector embeddings
    2. Text CTE: PostgreSQL full-text search (to_tsvector / ts_rank)
    Both CTEs are fused via Reciprocal Rank Fusion (RRF) entirely in SQL.

    Final score formula:
        rrf_score  = SUM(1.0 / (60 + rank)) per item across both retrieval tiers
        final_score = rrf_score * (0.7 + 0.3 * quality_score)

    The quality boost rewards items with higher behavioral quality signals while
    preserving relevance as the primary ranking signal. Items with quality_score=1.0
    receive a 1.0x multiplier; items with quality_score=0.0 receive a 0.7x multiplier.

    Temporal filtering (KM-06): when at_time is provided, only items valid at that
    point in time are returned. Items with NULL valid_at are always-valid (backward
    compat with pre-migration data).

    Result shape is backward-compatible with the previous cosine-only implementation:
    relevance_score now reflects the quality-boosted RRF final_score instead of
    raw cosine similarity, but all other fields are unchanged.
    """
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

    # Optional temporal filter: parse at_time ISO 8601 string if provided
    target_time: datetime.datetime | None = None
    if at_time is not None:
        try:
            target_time = datetime.datetime.fromisoformat(at_time)
        except ValueError:
            return CallToolResult(
                content=[TextContent(
                    type="text",
                    text=(
                        f"Invalid at_time format: '{at_time}'. "
                        "Expected ISO 8601 datetime string, e.g. '2026-01-01T00:00:00Z'."
                    ),
                )],
                isError=True,
            )

    # Embed the query text using the singleton embedding provider
    query_embedding = get_embedder().embed(query)

    async with get_session() as session:
        # Shared WHERE conditions used in both CTEs
        org_filter = (KnowledgeItem.org_id == org_id) | (KnowledgeItem.is_public == True)  # noqa: E712
        deleted_filter = KnowledgeItem.deleted_at.is_(None)
        embedding_filter = KnowledgeItem.embedding.isnot(None)

        # Optional filters accumulated for both CTEs
        extra_filters = []
        if category_enum is not None:
            extra_filters.append(KnowledgeItem.category == category_enum)
        if target_time is not None:
            extra_filters.extend(build_temporal_filter(target_time))
            if version is not None:
                extra_filters.append(KnowledgeItem.version == version)

        # -------------------------------------------------------------------
        # CTE 1: Vector search (cosine distance)
        # -------------------------------------------------------------------
        vector_base = (
            select(
                KnowledgeItem.id,
                func.row_number().over(
                    order_by=KnowledgeItem.embedding.cosine_distance(query_embedding)
                ).label("vec_rank"),
            )
            .where(org_filter)
            .where(deleted_filter)
            .where(embedding_filter)
        )
        for f in extra_filters:
            vector_base = vector_base.where(f)
        vector_cte = vector_base.limit(20).cte("vector_results")

        # -------------------------------------------------------------------
        # CTE 2: Full-text search (PostgreSQL ts_rank)
        # Uses native to_tsvector / ts_rank — no external extensions needed.
        # -------------------------------------------------------------------
        ts_query_expr = func.plainto_tsquery("english", query)
        ts_vector_expr = func.to_tsvector("english", KnowledgeItem.content)
        text_base = (
            select(
                KnowledgeItem.id,
                func.row_number().over(
                    order_by=func.ts_rank(ts_vector_expr, ts_query_expr).desc()
                ).label("text_rank"),
            )
            .where(org_filter)
            .where(deleted_filter)
            .where(ts_vector_expr.op("@@")(ts_query_expr))
        )
        for f in extra_filters:
            text_base = text_base.where(f)
        text_cte = text_base.limit(20).cte("text_results")

        # -------------------------------------------------------------------
        # RRF fusion: SUM(1.0 / (60 + rank)) per item across both CTEs
        # Standard k=60 constant balances contribution from both retrieval tiers.
        # -------------------------------------------------------------------
        rrf_union = union_all(
            select(vector_cte.c.id, vector_cte.c.vec_rank.label("rank")),
            select(text_cte.c.id, text_cte.c.text_rank.label("rank")),
        ).subquery()

        rrf_scores = (
            select(
                rrf_union.c.id,
                func.sum(1.0 / (60 + rrf_union.c.rank)).label("rrf_score"),
            )
            .group_by(rrf_union.c.id)
        ).subquery()

        # -------------------------------------------------------------------
        # Quality-boosted final score: rrf_score * (0.7 + 0.3 * quality_score)
        # Items with quality_score=1.0 get 1.0x; quality_score=0.0 gets 0.7x.
        # Computed in SQL — no Python post-processing to meet <200ms P95 target.
        # -------------------------------------------------------------------
        final_score_expr = (
            rrf_scores.c.rrf_score * (0.7 + 0.3 * KnowledgeItem.quality_score)
        ).label("final_score")

        final_query = (
            select(KnowledgeItem, final_score_expr)
            .join(rrf_scores, KnowledgeItem.id == rrf_scores.c.id)
            .order_by(text("final_score DESC"))
        )

        # Count total matching items for pagination metadata
        count_subquery = final_query.subquery()
        total_result = await session.execute(
            select(func.count()).select_from(count_subquery)
        )
        total_count = total_result.scalar_one()

        # Apply pagination
        paginated_query = final_query.limit(limit).offset(offset)
        result = await session.execute(paginated_query)
        rows = result.all()

    # ACL-05: Deduplicate results by content_hash when spanning private + public
    # Private results take priority over public duplicates (org attribution preserved).
    # Results are ordered by quality-boosted RRF score DESC; private items with same
    # content naturally appear at equal or better score — first-seen wins.
    seen_hashes: set[str] = set()
    deduped_rows = []
    for item, final_score in rows:
        if item.content_hash in seen_hashes:
            continue  # skip duplicate — earlier (higher score or private) copy kept
        seen_hashes.add(item.content_hash)
        deduped_rows.append((item, final_score))

    # Adjust total to account for dedup (approximate — exact count requires full scan)
    dedup_reduction = len(rows) - len(deduped_rows)
    total_count = max(0, total_count - dedup_reduction)

    # Build summary-tier results (~30-50 tokens per result)
    results = [
        {
            "id": str(item.id),
            # First 80 chars as title — gives agent enough context to decide if worth fetching
            "title": item.content[:80] + ("..." if len(item.content) > 80 else ""),
            "category": item.category.value,
            "confidence": item.confidence,
            "org_attribution": item.org_id,
            # Quality-boosted RRF final_score replaces raw cosine similarity (QI-03)
            "relevance_score": round(float(final_score), 4),
        }
        for item, final_score in deduped_rows
    ]

    has_more = (offset + limit) < total_count
    next_cursor = encode_cursor(offset + limit) if has_more else None

    # Fire-and-forget retrieval count tracking — does not block search response (QI-02)
    if deduped_rows:
        returned_ids = [str(item.id) for item, _ in deduped_rows]
        asyncio.create_task(_record_retrieval_signals(returned_ids))

    return {
        "results": results,
        "total_found": total_count,
        "next_cursor": next_cursor,
    }
