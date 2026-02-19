"""Contribution approval and rejection REST endpoints for the HiveMind dashboard (DASH-01).

Endpoints:
- GET  /contributions                     — list pending contributions (paginated)
- POST /contributions/{id}/approve        — approve a pending contribution
- POST /contributions/{id}/reject         — reject a pending contribution

The approve endpoint mirrors the CLI approval flow in hivemind/cli/client.py:
- Generate embedding from contribution content
- Create KnowledgeItem from PendingContribution fields
- Delete the PendingContribution
- Fire PostgreSQL NOTIFY for SSE delivery (DASH-01)
- Dispatch webhook notifications (INFRA-03)

Security:
- All endpoints require X-API-Key header via require_api_key dependency
- org_id is always extracted from the authenticated ApiKey record (ACL-01)
- Contributions are filtered by org_id — cross-org access returns 404

Requirements: DASH-01, DASH-05.
"""

from __future__ import annotations

import asyncio
import datetime
import logging
import uuid as _uuid
from typing import Annotated

import sqlalchemy as sa
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from hivemind.api.auth import get_async_session, require_api_key
from hivemind.api.routes.stream import notify_knowledge_published
from hivemind.db.models import ApiKey, KnowledgeItem, PendingContribution
from hivemind.db.session import get_session
from hivemind.pipeline.embedder import get_embedder
from hivemind.webhooks.tasks import dispatch_webhooks

logger = logging.getLogger(__name__)

contributions_router = APIRouter(prefix="/contributions", tags=["contributions"])


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------


class PendingContributionItem(BaseModel):
    """Single contribution in the pending list response."""

    id: str
    title: str
    content_preview: str
    category: str
    source_agent_id: str
    created_at: str
    content_hash: str

    model_config = {"from_attributes": True}


class ContributionListResponse(BaseModel):
    """Response body for GET /contributions."""

    items: list[PendingContributionItem]
    total: int
    limit: int
    offset: int

    model_config = {"from_attributes": True}


class ApproveResponse(BaseModel):
    """Response body for POST /contributions/{id}/approve."""

    status: str
    item_id: str

    model_config = {"from_attributes": True}


class RejectResponse(BaseModel):
    """Response body for POST /contributions/{id}/reject."""

    status: str
    contribution_id: str

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@contributions_router.get(
    "",
    response_model=ContributionListResponse,
    operation_id="list_pending_contributions",
    summary="List pending contributions awaiting review",
    description=(
        "Returns paginated list of pending contributions for the calling organisation. "
        "Content is truncated to 500 characters for the list view. "
        "Use the approve or reject endpoints to action individual contributions."
    ),
)
async def list_pending_contributions(
    limit: Annotated[int, Query(ge=1, le=200, description="Max results per page")] = 50,
    offset: Annotated[int, Query(ge=0, description="Pagination offset")] = 0,
    api_key_record: ApiKey = Depends(require_api_key),
) -> ContributionListResponse:
    """Return paginated pending contributions for the authenticated organisation.

    org_id is always extracted from the authenticated API key — never from query params.
    """
    org_id = api_key_record.org_id

    async with get_session() as session:
        # Count total for pagination metadata
        count_result = await session.execute(
            sa.select(sa.func.count(PendingContribution.id)).where(
                PendingContribution.org_id == org_id
            )
        )
        total = count_result.scalar_one()

        # Fetch page
        result = await session.execute(
            sa.select(PendingContribution)
            .where(PendingContribution.org_id == org_id)
            .order_by(PendingContribution.contributed_at.desc())
            .limit(limit)
            .offset(offset)
        )
        contributions = result.scalars().all()

    items = [
        PendingContributionItem(
            id=str(c.id),
            # PendingContribution has no title — use first 80 chars of content
            title=c.content[:80] + ("..." if len(c.content) > 80 else ""),
            # Content truncated to 500 chars for list view
            content_preview=c.content[:500] + ("..." if len(c.content) > 500 else ""),
            category=c.category.value,
            source_agent_id=c.source_agent_id,
            created_at=c.contributed_at.isoformat(),
            content_hash=c.content_hash,
        )
        for c in contributions
    ]

    return ContributionListResponse(
        items=items,
        total=total,
        limit=limit,
        offset=offset,
    )


@contributions_router.post(
    "/{contribution_id}/approve",
    response_model=ApproveResponse,
    operation_id="approve_contribution",
    summary="Approve a pending contribution",
    description=(
        "Promotes a pending contribution to an approved knowledge item. "
        "Generates an embedding, creates a KnowledgeItem from the contribution data, "
        "deletes the PendingContribution, fires a PostgreSQL NOTIFY for SSE clients, "
        "and dispatches webhook notifications. "
        "Returns 404 if the contribution is not found in the calling organisation's namespace."
    ),
)
async def approve_contribution_endpoint(
    contribution_id: _uuid.UUID,
    api_key_record: ApiKey = Depends(require_api_key),
) -> ApproveResponse:
    """Approve a pending contribution and promote it to the knowledge commons.

    org_id is always extracted from the authenticated API key (ACL-01).
    Cross-org contributions return 404 to prevent org discovery.
    """
    org_id = api_key_record.org_id

    async with get_session() as session:
        # Query by id AND org_id — namespace isolation (404-not-403 pattern, ACL-01)
        result = await session.execute(
            sa.select(PendingContribution).where(
                PendingContribution.id == contribution_id,
                PendingContribution.org_id == org_id,
            )
        )
        contribution = result.scalar_one_or_none()

    if contribution is None:
        raise HTTPException(
            status_code=404,
            detail=f"Contribution '{contribution_id}' not found.",
        )

    # Generate embedding at approval time (same as CLI approval flow)
    embedding = get_embedder().embed(contribution.content)

    # Build KnowledgeItem from contribution data (mirrors cli/client.py approve_contribution)
    now = datetime.datetime.now(datetime.timezone.utc)
    item = KnowledgeItem(
        org_id=contribution.org_id,
        source_agent_id=contribution.source_agent_id,
        run_id=contribution.run_id,
        content=contribution.content,
        content_hash=contribution.content_hash,
        category=contribution.category,
        confidence=contribution.confidence,
        framework=contribution.framework,
        language=contribution.language,
        version=contribution.version,
        tags=contribution.tags,
        is_public=False,  # default private; org controls visibility via publish_knowledge
        embedding=embedding,
        quality_score=0.5,  # neutral prior (QI-01)
        contributed_at=contribution.contributed_at,
        approved_at=now,
    )

    item_data = {
        "id": None,  # populated after commit
        "is_public": item.is_public,
        "org_id": str(org_id),
        "category": contribution.category.value,
        "title": contribution.content[:80] + ("..." if len(contribution.content) > 80 else ""),
    }

    async with get_session() as session:
        session.add(item)
        # Remove the pending contribution
        contrib_to_delete = await session.get(PendingContribution, contribution_id)
        if contrib_to_delete is not None:
            await session.delete(contrib_to_delete)
        await session.commit()
        await session.refresh(item)

        # Populate item_data.id now that we have the DB-generated UUID
        item_data["id"] = str(item.id)

        # Fire NOTIFY within the same session so it's in-transaction
        await notify_knowledge_published(session, item_data)
        await session.commit()

    # Dispatch webhooks best-effort (never block approval on delivery failure)
    try:
        dispatched = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: dispatch_webhooks(
                org_id=str(org_id),
                event="knowledge.approved",
                knowledge_item_id=str(item.id),
                category=contribution.category.value,
            ),
        )
        if dispatched > 0:
            logger.info(
                "Dispatched %d webhook(s) for knowledge item %s via REST approve",
                dispatched,
                item.id,
            )
    except Exception:
        logger.warning(
            "Failed to dispatch webhooks for item %s — approval still succeeded",
            item.id,
            exc_info=True,
        )

    logger.info(
        "Contribution approved via REST: contribution_id=%s item_id=%s org_id=%s",
        contribution_id,
        item.id,
        org_id,
    )

    return ApproveResponse(status="approved", item_id=str(item.id))


@contributions_router.post(
    "/{contribution_id}/reject",
    response_model=RejectResponse,
    operation_id="reject_contribution",
    summary="Reject a pending contribution",
    description=(
        "Removes a pending contribution from the review queue. "
        "Dispatches a 'knowledge.rejected' webhook notification. "
        "Returns 404 if the contribution is not found in the calling organisation's namespace."
    ),
)
async def reject_contribution_endpoint(
    contribution_id: _uuid.UUID,
    api_key_record: ApiKey = Depends(require_api_key),
) -> RejectResponse:
    """Delete a pending contribution from the review queue.

    org_id is always extracted from the authenticated API key (ACL-01).
    Cross-org contributions return 404 to prevent org discovery.
    """
    org_id = api_key_record.org_id

    async with get_session() as session:
        result = await session.execute(
            sa.select(PendingContribution).where(
                PendingContribution.id == contribution_id,
                PendingContribution.org_id == org_id,
            )
        )
        contribution = result.scalar_one_or_none()

    if contribution is None:
        raise HTTPException(
            status_code=404,
            detail=f"Contribution '{contribution_id}' not found.",
        )

    category_value = contribution.category.value

    async with get_session() as session:
        contrib_to_delete = await session.get(PendingContribution, contribution_id)
        if contrib_to_delete is not None:
            await session.delete(contrib_to_delete)
            await session.commit()

    # Dispatch webhooks best-effort
    try:
        await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: dispatch_webhooks(
                org_id=str(org_id),
                event="knowledge.rejected",
                knowledge_item_id=str(contribution_id),
                category=category_value,
            ),
        )
    except Exception:
        logger.warning(
            "Failed to dispatch webhooks for rejected contribution %s",
            contribution_id,
            exc_info=True,
        )

    logger.info(
        "Contribution rejected via REST: contribution_id=%s org_id=%s",
        contribution_id,
        org_id,
    )

    return RejectResponse(status="rejected", contribution_id=str(contribution_id))
