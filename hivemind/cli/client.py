"""Synchronous database client for HiveMind CLI operations.

Uses SQLAlchemy sync engine (postgresql://) instead of the async engine used
by the MCP server.  This avoids asyncio event loop issues when Typer commands
call DB functions directly from a non-async context.

The sync URL is derived from settings.database_url by stripping the +asyncpg
driver suffix so the psycopg2 (or any sync) driver is used instead.

FOR UPDATE SKIP LOCKED is applied to fetch_pending() so that if two CLI
sessions run concurrently, they don't both process the same contribution
(per research Pattern 6).
"""

from __future__ import annotations

import datetime
import uuid
from typing import Optional

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from hivemind.config import settings
from hivemind.db.models import KnowledgeCategory, KnowledgeItem, PendingContribution
from hivemind.pipeline.embedder import get_embedder
from hivemind.webhooks.tasks import dispatch_webhooks


# ---------------------------------------------------------------------------
# Sync engine + session factory
# ---------------------------------------------------------------------------
# Derive sync URL from the async URL by removing the +asyncpg driver suffix.
# e.g. "postgresql+asyncpg://..." → "postgresql://..."
_sync_url = settings.database_url.replace("+asyncpg", "")

_engine = create_engine(_sync_url, pool_pre_ping=True)
SessionFactory = sessionmaker(bind=_engine, expire_on_commit=False)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def fetch_pending(org_id: str, limit: int = 10) -> list[PendingContribution]:
    """Fetch pending contributions for review (oldest first).

    Uses FOR UPDATE SKIP LOCKED so concurrent CLI sessions don't process the
    same item simultaneously.

    Args:
        org_id: Organisation namespace to filter by.
        limit:  Maximum number of items to return.

    Returns:
        List of PendingContribution ORM objects ordered by contributed_at ASC.
    """
    with SessionFactory() as session:
        # FOR UPDATE SKIP LOCKED prevents double-processing in concurrent sessions
        items = (
            session.query(PendingContribution)
            .filter(PendingContribution.org_id == org_id)
            .order_by(PendingContribution.contributed_at.asc())
            .limit(limit)
            .with_for_update(skip_locked=True)
            .all()
        )
        # Detach from session so callers can access attributes after session closes.
        # expire_on_commit=False on the factory handles this, but explicit expunge
        # makes the intent clear.
        session.expunge_all()
        return items


def approve_contribution(
    contribution_id: uuid.UUID,
    is_public: bool = False,
    category_override: Optional[str] = None,
) -> KnowledgeItem:
    """Promote a pending contribution to the approved knowledge_items table.

    Steps:
    1. Fetch PendingContribution by id
    2. Generate embedding from cleaned content
    3. Create KnowledgeItem from contribution data
    4. Delete the PendingContribution (it has been promoted)
    5. Return the new KnowledgeItem

    Args:
        contribution_id:   UUID of the PendingContribution to approve.
        is_public:         Whether to publish to the public commons.
        category_override: Override the agent-suggested category if set.

    Returns:
        The newly created KnowledgeItem (already committed).

    Raises:
        ValueError: If the contribution is not found.
    """
    with SessionFactory() as session:
        contribution = session.get(PendingContribution, contribution_id)
        if contribution is None:
            raise ValueError(f"Contribution {contribution_id} not found.")

        # Resolve category
        final_category: KnowledgeCategory
        if category_override is not None:
            final_category = KnowledgeCategory(category_override)
        else:
            final_category = contribution.category

        # Generate embedding at approval time (not at contribution time)
        embedding = get_embedder().embed(contribution.content)

        # Build KnowledgeItem from contribution data
        item = KnowledgeItem(
            org_id=contribution.org_id,
            source_agent_id=contribution.source_agent_id,
            run_id=contribution.run_id,
            content=contribution.content,
            content_hash=contribution.content_hash,
            category=final_category,
            confidence=contribution.confidence,
            framework=contribution.framework,
            language=contribution.language,
            version=contribution.version,
            tags=contribution.tags,
            is_public=is_public,
            embedding=embedding,
            contributed_at=contribution.contributed_at,
            approved_at=datetime.datetime.now(datetime.timezone.utc),
        )

        session.add(item)
        session.delete(contribution)
        session.commit()

        # INFRA-03: Dispatch webhook notifications for approved knowledge
        try:
            dispatched = dispatch_webhooks(
                org_id=contribution.org_id,
                event="knowledge.approved",
                knowledge_item_id=str(item.id),
                category=final_category.value,
            )
            if dispatched > 0:
                import logging  # noqa: PLC0415
                logging.getLogger(__name__).info(
                    "Dispatched %d webhook(s) for knowledge item %s",
                    dispatched, item.id,
                )
        except Exception:
            # Webhook delivery is best-effort — don't block approval on delivery failure
            import logging  # noqa: PLC0415
            logging.getLogger(__name__).warning(
                "Failed to dispatch webhooks for item %s — approval still succeeded",
                item.id,
                exc_info=True,
            )

        # Refresh to get server-generated fields (id, etc.)
        session.refresh(item)
        session.expunge(item)
        return item


def reject_contribution(contribution_id: uuid.UUID) -> None:
    """Delete a pending contribution from the review queue.

    Args:
        contribution_id: UUID of the PendingContribution to reject.
    """
    with SessionFactory() as session:
        contribution = session.get(PendingContribution, contribution_id)
        if contribution is not None:
            session.delete(contribution)
            session.commit()


def flag_contribution(contribution_id: uuid.UUID) -> None:
    """Flag a pending contribution as potentially containing sensitive content.

    Sets is_sensitive_flagged = True so operators can re-examine the PII
    stripping result.

    Args:
        contribution_id: UUID of the PendingContribution to flag.
    """
    with SessionFactory() as session:
        contribution = session.get(PendingContribution, contribution_id)
        if contribution is not None:
            contribution.is_sensitive_flagged = True
            session.commit()


def get_org_stats(org_id: str) -> dict:
    """Return gamification stats for an organisation.

    Args:
        org_id: Organisation namespace.

    Returns:
        Dict with:
        - total_contributions: total approved KnowledgeItems for this org
        - agent_count: distinct source_agent_id values across all orgs (global reach)
    """
    with SessionFactory() as session:
        from sqlalchemy import distinct, func  # noqa: PLC0415

        total_contributions = (
            session.query(func.count(KnowledgeItem.id))
            .filter(
                KnowledgeItem.org_id == org_id,
                KnowledgeItem.deleted_at.is_(None),
            )
            .scalar()
            or 0
        )

        # "Helped X agents" — distinct agent IDs across all orgs
        agent_count = (
            session.query(func.count(distinct(KnowledgeItem.source_agent_id)))
            .filter(KnowledgeItem.deleted_at.is_(None))
            .scalar()
            or 0
        )

        return {
            "total_contributions": total_contributions,
            "agent_count": agent_count,
        }


def find_similar_knowledge(
    content: str,
    org_id: str,
    top_n: int = 3,
    threshold: float = 0.35,
) -> list[dict]:
    """Find existing knowledge items most similar to the given content.

    Uses cosine distance (same pattern as search_knowledge.py) to find the
    top-N most semantically similar items in the knowledge commons.  Returns
    items where cosine distance <= threshold (i.e. similarity >= 65%).

    This is used by the CLI review panel for near-duplicate detection
    (TRUST-02 requirement).

    Args:
        content:   The pending contribution content to compare against.
        org_id:    Organisation namespace — scopes results to org + public items.
        top_n:     Maximum number of similar items to return.
        threshold: Cosine distance cutoff (0.35 ≈ 65% similarity).  Items with
                   distance > threshold are excluded as insufficiently similar.

    Returns:
        List of dicts with keys: id, title, category, similarity (%), org_id.
        Empty list if no items meet the threshold.
    """
    from sqlalchemy import func, select  # noqa: PLC0415

    # Generate embedding for the pending contribution content
    embedding = get_embedder().embed(content)

    with SessionFactory() as session:
        # Build cosine distance column (same operator as search_knowledge.py line 233)
        distance_col = KnowledgeItem.embedding.cosine_distance(embedding).label("distance")

        stmt = (
            select(KnowledgeItem, distance_col)
            .where(
                # Org isolation: own private items + public commons
                (KnowledgeItem.org_id == org_id) | (KnowledgeItem.is_public == True)  # noqa: E712
            )
            .where(KnowledgeItem.deleted_at.is_(None))      # exclude soft-deleted
            .where(KnowledgeItem.embedding.isnot(None))     # skip items without embeddings
            .order_by(distance_col.asc())                   # lowest distance = most similar
            .limit(top_n)
        )

        result = session.execute(stmt)
        rows = result.all()

    # Filter to only items within the similarity threshold
    similar = []
    for item, distance in rows:
        if distance > threshold:
            continue  # too dissimilar — skip
        similar.append({
            "id": str(item.id),
            "title": item.content[:80] + ("..." if len(item.content) > 80 else ""),
            "category": item.category.value,
            "similarity": round((1 - distance) * 100),  # convert distance to %
            "org_id": item.org_id,
        })

    return similar


def compute_qi_score(contribution: PendingContribution) -> dict:
    """Compute a Quality Index pre-screening signal for a pending contribution.

    Synthesises confidence score, is_sensitive_flagged status, and content
    length into a single 0-100 score with a High/Medium/Low badge.  Used by
    the CLI review panel (TRUST-02) to help reviewers quickly assess quality
    without reading every word.

    Scoring rules:
    - Base score:    confidence * 100
    - Modifier -30:  is_sensitive_flagged (lower trust — PII may still be present)
    - Modifier -20:  content length < 50 chars (very short = suspect)
    - Modifier +10:  content length > 200 chars (detailed = higher value signal)
    - Clamped to [0, 100]

    Badge thresholds:
    - score >= 80: High  (green)
    - score >= 50: Medium (yellow)
    - score <  50: Low   (red)

    Args:
        contribution: PendingContribution ORM object (already detached from session).

    Returns:
        Dict with keys: score, label, color, icon, details (list of str).
    """
    # Base score from confidence
    score = contribution.confidence * 100

    # Apply modifiers
    if contribution.is_sensitive_flagged:
        score -= 30  # flagged content carries lower trust
    if len(contribution.content) < 50:
        score -= 20  # very short content is suspect
    elif len(contribution.content) > 200:
        score += 10  # longer, detailed content is a richer signal

    # Clamp to [0, 100]
    score = max(0, min(100, score))
    score = round(score)

    # Determine badge
    if score >= 80:
        badge = {"label": "High", "color": "green", "icon": "+++"}
    elif score >= 50:
        badge = {"label": "Medium", "color": "yellow", "icon": "++"}
    else:
        badge = {"label": "Low", "color": "red", "icon": "+"}

    # Build detail lines (None values are filtered out)
    details = [
        f"Confidence: {contribution.confidence:.0%}",
        "Flagged as sensitive" if contribution.is_sensitive_flagged else None,
        "Very short content" if len(contribution.content) < 50 else None,
    ]
    details = [d for d in details if d is not None]

    return {
        "score": score,
        "label": badge["label"],
        "color": badge["color"],
        "icon": badge["icon"],
        "details": details,
    }
