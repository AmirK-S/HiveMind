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
