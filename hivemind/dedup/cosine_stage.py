"""Stage 1 of the dedup pipeline: cosine similarity candidate retrieval.

Reuses the same vector search pattern from search_knowledge.py to find the
top-K most similar knowledge items to a given content string. Items with
cosine distance >= 0.35 (< 65% similarity) are not returned — they are too
dissimilar to be near-duplicates.
"""

from __future__ import annotations

from sqlalchemy import select

from hivemind.db.models import KnowledgeItem
from hivemind.db.session import get_session
from hivemind.pipeline.embedder import get_embedder

# Maximum number of candidate items Stage 1 will return
DEFAULT_TOP_K = 10


async def find_cosine_candidates(
    content: str,
    org_id: str,
    top_k: int = DEFAULT_TOP_K,
) -> list[dict]:
    """Find the top-K most similar knowledge items by cosine distance.

    Embeds the content and performs a cosine similarity search scoped to the
    given org (own items + public commons).  Only active, non-expired items are
    considered.

    Args:
        content: The new content to compare against existing items.
        org_id:  The contributing org's ID — used for namespace isolation.
        top_k:   Maximum number of candidate results to return (default 10).

    Returns:
        List of candidate dicts, each containing:
          { id, content, content_hash, distance, category, version }
        Ordered by cosine distance ascending (most similar first).
        Only items with distance < 0.35 (>= 65% similarity) are included.
    """
    embedding = get_embedder().embed(content)

    async with get_session() as session:
        distance_col = KnowledgeItem.embedding.cosine_distance(embedding).label("distance")

        stmt = (
            select(KnowledgeItem, distance_col)
            .where(
                # Org isolation: own items + public commons (ACL-01)
                (KnowledgeItem.org_id == org_id) | (KnowledgeItem.is_public == True)  # noqa: E712
            )
            .where(KnowledgeItem.embedding.isnot(None))  # skip items without embeddings
            .where(KnowledgeItem.deleted_at.is_(None))   # exclude soft-deleted items
            .where(KnowledgeItem.expired_at.is_(None))   # exclude expired (superseded) items
            .order_by(distance_col.asc())
            .limit(top_k)
        )

        result = await session.execute(stmt)
        rows = result.all()

    # Filter to items with cosine distance < 0.35 (>= 65% similarity threshold)
    # Items below this threshold are too dissimilar to be near-duplicates.
    candidates = []
    for item, distance in rows:
        if distance >= 0.35:
            continue
        candidates.append({
            "id": str(item.id),
            "content": item.content,
            "content_hash": item.content_hash,
            "distance": float(distance),
            "category": item.category.value,
            "version": item.version,
        })

    return candidates
