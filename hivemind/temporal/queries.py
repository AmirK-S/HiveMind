"""Bi-temporal query helpers for HiveMind (KM-05, KM-06).

Point-in-time knowledge retrieval enables:
- Version-scoped queries: "what did we know about X as of version 2.1?"
- Historical accuracy: prevents surfacing knowledge that was invalid at time T
- Audit trails: reproducible answers tied to a specific point in time

Bi-temporal model (KM-05):
    System time  (when the row was recorded):
        contributed_at = system-time start (immutable, always set)
        expired_at     = system-time end (NULL = current row, not superseded)

    World time (when the fact was true in reality):
        valid_at   = world-time start (NULL = "always valid" / pre-temporal-migration)
        invalid_at = world-time end   (NULL = "still valid today")

    For point-in-time queries at time T:
        1. valid_at IS NULL OR valid_at <= T    (item was valid by time T)
        2. invalid_at IS NULL OR invalid_at > T  (item was not yet invalidated at T)
        3. expired_at IS NULL                    (current system-time row only)

    Items where valid_at IS NULL are treated as "always valid" (backward compatible
    with pre-migration data). They always pass the world-time start check.
"""

from __future__ import annotations

import datetime
import logging

import sqlalchemy as sa
from sqlalchemy import func, or_, select

from hivemind.db.models import KnowledgeItem
from hivemind.db.session import get_session

logger = logging.getLogger(__name__)


def build_temporal_filter(at_time: datetime.datetime) -> list:
    """Return SQLAlchemy WHERE clause conditions for point-in-time filtering.

    The returned list of conditions can be applied to any SELECT statement
    via ``stmt.where(*build_temporal_filter(at_time))``.

    Filtering semantics for a query at time T:
    - World-time start (valid_at): NULL items pass unconditionally (always-valid
      backward-compat), non-NULL items must satisfy valid_at <= T.
    - World-time end (invalid_at): NULL means "still valid" (passes); non-NULL
      must satisfy invalid_at > T (item hadn't been invalidated yet at T).
    - System-time end (expired_at): must be NULL — only current (non-superseded)
      rows are returned.

    Args:
        at_time: The point in time to query at. Should be timezone-aware.

    Returns:
        List of three SQLAlchemy binary expression conditions.
    """
    return [
        # World-time start: NULL valid_at = always valid; otherwise must be <= T
        or_(
            KnowledgeItem.valid_at.is_(None),
            KnowledgeItem.valid_at <= at_time,
        ),
        # World-time end: NULL = still valid; otherwise must not have expired yet
        or_(
            KnowledgeItem.invalid_at.is_(None),
            KnowledgeItem.invalid_at > at_time,
        ),
        # System-time end: only current (not superseded) rows
        KnowledgeItem.expired_at.is_(None),
    ]


async def query_at_time(
    query_embedding: list[float],
    org_id: str,
    at_time: datetime.datetime,
    version: str | None = None,
    category: str | None = None,
    limit: int = 10,
) -> list[dict]:
    """Perform a point-in-time cosine similarity search.

    Returns knowledge items that were valid at the specified time, ranked by
    cosine similarity to the provided embedding vector.

    This is a standalone temporal search that combines:
    - Cosine distance ranking against query_embedding
    - Bi-temporal filtering via build_temporal_filter()
    - Org isolation: org_id match OR is_public
    - Optional version filter (version column exact match)
    - Optional category filter

    Args:
        query_embedding: Pre-computed embedding vector for the query text.
        org_id:          Calling org's namespace (ACL-01).
        at_time:         Point in time to query at.
        version:         Optional version string to filter by (exact match on
                         KnowledgeItem.version column). Applied in addition to
                         the temporal filter.
        category:        Optional KnowledgeCategory value to filter by.
        limit:           Maximum number of results to return.

    Returns:
        List of dicts with keys: id, content, category, relevance_score,
        valid_at, version.
    """
    distance_col = KnowledgeItem.embedding.cosine_distance(query_embedding).label("distance")

    stmt = (
        select(KnowledgeItem, distance_col)
        .where(
            # Org isolation: own items + public commons (ACL-01)
            (KnowledgeItem.org_id == org_id) | (KnowledgeItem.is_public == True)  # noqa: E712
        )
        .where(KnowledgeItem.embedding.isnot(None))
        .where(KnowledgeItem.deleted_at.is_(None))
    )

    # Apply bi-temporal filter conditions
    for condition in build_temporal_filter(at_time):
        stmt = stmt.where(condition)

    # Optional version filter (version-scoped temporal query, KM-06)
    if version is not None:
        stmt = stmt.where(KnowledgeItem.version == version)

    # Optional category filter
    if category is not None:
        from hivemind.db.models import KnowledgeCategory  # noqa: PLC0415
        try:
            category_enum = KnowledgeCategory(category)
            stmt = stmt.where(KnowledgeItem.category == category_enum)
        except ValueError:
            logger.warning("query_at_time: unknown category '%s' — ignoring filter", category)

    # Rank by cosine distance (ascending = most similar first)
    stmt = stmt.order_by(distance_col.asc()).limit(limit)

    async with get_session() as session:
        result = await session.execute(stmt)
        rows = result.all()

    return [
        {
            "id": str(item.id),
            "content": item.content,
            "category": item.category.value,
            # Convert cosine distance [0..2] to similarity score [1..−1]
            "relevance_score": round(1 - distance, 4),
            "valid_at": item.valid_at.isoformat() if item.valid_at else None,
            "version": item.version,
        }
        for item, distance in rows
    ]
