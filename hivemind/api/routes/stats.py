"""Statistics endpoints for the HiveMind dashboard (DASH-03, DASH-06).

Endpoints:
- GET /stats/commons — global commons health metrics (DASH-06)
- GET /stats/org     — per-organisation contribution and reciprocity stats (DASH-03)
- GET /stats/user    — per-agent contribution and retrieval metrics (DASH-03)

All queries use existing ORM models and columns — no new tables required.
Data is already tracked in knowledge_items and quality_signals from Phases 1-3.

Security:
- All endpoints require X-API-Key header via require_api_key dependency
- org_id is always extracted from the authenticated ApiKey record (ACL-01)
- Commons endpoint returns public aggregate stats only — no private namespace data

Requirements: DASH-03, DASH-06.
"""

from __future__ import annotations

import datetime
import logging
from typing import Annotated

import sqlalchemy as sa
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from hivemind.api.auth import require_api_key
from hivemind.db.models import ApiKey, KnowledgeItem, PendingContribution, QualitySignal
from hivemind.db.session import get_session

logger = logging.getLogger(__name__)

stats_router = APIRouter(prefix="/stats", tags=["stats"])

_UTC = datetime.timezone.utc


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------


class CategoryCount(BaseModel):
    """Category with item count."""

    category: str
    count: int


class CommonsStatsResponse(BaseModel):
    """Response body for GET /stats/commons."""

    total_items: int
    total_pending: int
    growth_rate_24h: int
    growth_rate_7d: int
    retrieval_volume_24h: int
    domains_covered: int
    categories: list[CategoryCount]


class TopItem(BaseModel):
    """A top knowledge item by retrieval count."""

    id: str
    title: str
    retrieval_count: int


class OrgStatsResponse(BaseModel):
    """Response body for GET /stats/org."""

    contributions_total: int
    contributions_pending: int
    contributions_approved_24h: int
    retrievals_by_others: int
    helpful_count: int
    not_helpful_count: int
    top_items: list[TopItem]


class UserStatsResponse(BaseModel):
    """Response body for GET /stats/user."""

    agent_id: str | None
    agent_contributions: int
    agent_retrievals_received: int
    agent_helpful_ratio: float | None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@stats_router.get(
    "/commons",
    response_model=CommonsStatsResponse,
    operation_id="get_commons_stats",
    summary="Global commons health metrics",
    description=(
        "Returns aggregate statistics across the entire knowledge commons: "
        "total items, growth rates, retrieval volume, and domain coverage. "
        "This is a public-facing view — no private namespace data is included."
    ),
)
async def get_commons_stats(
    api_key_record: ApiKey = Depends(require_api_key),
) -> CommonsStatsResponse:
    """Return global commons health metrics.

    Authentication is required to prevent anonymous scraping, but the data
    returned is aggregated across all orgs with no private content exposed.
    """
    now = datetime.datetime.now(_UTC)
    cutoff_24h = now - datetime.timedelta(hours=24)
    cutoff_7d = now - datetime.timedelta(days=7)

    async with get_session() as session:
        # Total approved items (non-deleted)
        total_items_result = await session.execute(
            sa.select(sa.func.count(KnowledgeItem.id)).where(
                KnowledgeItem.deleted_at.is_(None)
            )
        )
        total_items = total_items_result.scalar_one()

        # Total pending contributions
        total_pending_result = await session.execute(
            sa.select(sa.func.count(PendingContribution.id))
        )
        total_pending = total_pending_result.scalar_one()

        # Growth rate: items contributed in the last 24h
        growth_24h_result = await session.execute(
            sa.select(sa.func.count(KnowledgeItem.id)).where(
                KnowledgeItem.contributed_at > cutoff_24h,
                KnowledgeItem.deleted_at.is_(None),
            )
        )
        growth_rate_24h = growth_24h_result.scalar_one()

        # Growth rate: items contributed in the last 7d
        growth_7d_result = await session.execute(
            sa.select(sa.func.count(KnowledgeItem.id)).where(
                KnowledgeItem.contributed_at > cutoff_7d,
                KnowledgeItem.deleted_at.is_(None),
            )
        )
        growth_rate_7d = growth_7d_result.scalar_one()

        # Retrieval volume: count of retrieval quality signals in the last 24h
        retrieval_vol_result = await session.execute(
            sa.select(sa.func.count(QualitySignal.id)).where(
                QualitySignal.signal_type == "retrieval",
                QualitySignal.created_at > cutoff_24h,
            )
        )
        retrieval_volume_24h = retrieval_vol_result.scalar_one()

        # Domains covered: distinct categories
        domains_result = await session.execute(
            sa.select(sa.func.count(sa.distinct(KnowledgeItem.category))).where(
                KnowledgeItem.deleted_at.is_(None)
            )
        )
        domains_covered = domains_result.scalar_one()

        # Category breakdown
        categories_result = await session.execute(
            sa.select(KnowledgeItem.category, sa.func.count(KnowledgeItem.id).label("count"))
            .where(KnowledgeItem.deleted_at.is_(None))
            .group_by(KnowledgeItem.category)
            .order_by(sa.func.count(KnowledgeItem.id).desc())
        )
        categories = [
            CategoryCount(category=row.category.value, count=row.count)
            for row in categories_result
        ]

    return CommonsStatsResponse(
        total_items=total_items,
        total_pending=total_pending,
        growth_rate_24h=growth_rate_24h,
        growth_rate_7d=growth_rate_7d,
        retrieval_volume_24h=retrieval_volume_24h,
        domains_covered=domains_covered,
        categories=categories,
    )


@stats_router.get(
    "/org",
    response_model=OrgStatsResponse,
    operation_id="get_org_stats",
    summary="Organisation contribution and reciprocity statistics",
    description=(
        "Returns contribution metrics and reciprocity data for the calling organisation: "
        "total approved items, pending queue size, recent approvals, how many times "
        "other agents retrieved this org's knowledge, and the top 5 most-retrieved items."
    ),
)
async def get_org_stats(
    api_key_record: ApiKey = Depends(require_api_key),
) -> OrgStatsResponse:
    """Return per-organisation stats including the reciprocity metric.

    org_id is always extracted from the authenticated API key — never from query params.
    """
    org_id = api_key_record.org_id
    now = datetime.datetime.now(_UTC)
    cutoff_24h = now - datetime.timedelta(hours=24)

    async with get_session() as session:
        # Total approved items for this org
        total_result = await session.execute(
            sa.select(sa.func.count(KnowledgeItem.id)).where(
                KnowledgeItem.org_id == org_id,
                KnowledgeItem.deleted_at.is_(None),
            )
        )
        contributions_total = total_result.scalar_one()

        # Pending contributions for this org
        pending_result = await session.execute(
            sa.select(sa.func.count(PendingContribution.id)).where(
                PendingContribution.org_id == org_id
            )
        )
        contributions_pending = pending_result.scalar_one()

        # Items approved in the last 24h
        approved_24h_result = await session.execute(
            sa.select(sa.func.count(KnowledgeItem.id)).where(
                KnowledgeItem.org_id == org_id,
                KnowledgeItem.approved_at > cutoff_24h,
                KnowledgeItem.deleted_at.is_(None),
            )
        )
        contributions_approved_24h = approved_24h_result.scalar_one()

        # Retrieval reciprocity: total times this org's items have been retrieved
        # SUM of retrieval_count across all items from this org
        retrievals_result = await session.execute(
            sa.select(
                sa.func.coalesce(sa.func.sum(KnowledgeItem.retrieval_count), 0)
            ).where(
                KnowledgeItem.org_id == org_id,
                KnowledgeItem.deleted_at.is_(None),
            )
        )
        retrievals_by_others = retrievals_result.scalar_one()

        # Aggregated feedback counts
        helpful_result = await session.execute(
            sa.select(
                sa.func.coalesce(sa.func.sum(KnowledgeItem.helpful_count), 0),
                sa.func.coalesce(sa.func.sum(KnowledgeItem.not_helpful_count), 0),
            ).where(
                KnowledgeItem.org_id == org_id,
                KnowledgeItem.deleted_at.is_(None),
            )
        )
        helpful_row = helpful_result.one()
        helpful_count = helpful_row[0]
        not_helpful_count = helpful_row[1]

        # Top 5 items by retrieval_count
        top_items_result = await session.execute(
            sa.select(KnowledgeItem.id, KnowledgeItem.content, KnowledgeItem.retrieval_count)
            .where(
                KnowledgeItem.org_id == org_id,
                KnowledgeItem.deleted_at.is_(None),
            )
            .order_by(KnowledgeItem.retrieval_count.desc())
            .limit(5)
        )
        top_items = [
            TopItem(
                id=str(row.id),
                title=row.content[:80] + ("..." if len(row.content) > 80 else ""),
                retrieval_count=row.retrieval_count,
            )
            for row in top_items_result
        ]

    return OrgStatsResponse(
        contributions_total=contributions_total,
        contributions_pending=contributions_pending,
        contributions_approved_24h=contributions_approved_24h,
        retrievals_by_others=retrievals_by_others,
        helpful_count=helpful_count,
        not_helpful_count=not_helpful_count,
        top_items=top_items,
    )


@stats_router.get(
    "/user",
    response_model=UserStatsResponse,
    operation_id="get_user_stats",
    summary="Per-agent contribution and retrieval statistics",
    description=(
        "Returns contribution and retrieval metrics for a specific agent or all agents "
        "in the calling organisation. Includes the reciprocity metric: how many times "
        "this agent's contributions have been retrieved by other agents."
    ),
)
async def get_user_stats(
    agent_id: Annotated[str | None, Query(description="Agent ID filter (optional — all agents if omitted)")] = None,
    api_key_record: ApiKey = Depends(require_api_key),
) -> UserStatsResponse:
    """Return per-agent contribution and retrieval stats.

    org_id is always extracted from the authenticated API key (ACL-01).
    agent_id is an optional filter — omit to aggregate across all org agents.
    """
    org_id = api_key_record.org_id

    # Build base filter conditions
    filters = [
        KnowledgeItem.org_id == org_id,
        KnowledgeItem.deleted_at.is_(None),
    ]
    if agent_id is not None:
        filters.append(KnowledgeItem.source_agent_id == agent_id)

    async with get_session() as session:
        # Count contributions for this agent/org
        contrib_result = await session.execute(
            sa.select(sa.func.count(KnowledgeItem.id)).where(*filters)
        )
        agent_contributions = contrib_result.scalar_one()

        # Retrieval reciprocity: total times this agent's items were retrieved
        retrievals_result = await session.execute(
            sa.select(
                sa.func.coalesce(sa.func.sum(KnowledgeItem.retrieval_count), 0)
            ).where(*filters)
        )
        agent_retrievals_received = retrievals_result.scalar_one()

        # Helpful ratio: helpful / (helpful + not_helpful)
        feedback_result = await session.execute(
            sa.select(
                sa.func.coalesce(sa.func.sum(KnowledgeItem.helpful_count), 0),
                sa.func.coalesce(sa.func.sum(KnowledgeItem.not_helpful_count), 0),
            ).where(*filters)
        )
        feedback_row = feedback_result.one()
        total_helpful = feedback_row[0]
        total_not_helpful = feedback_row[1]

    # Compute helpful ratio — None if no feedback yet
    total_feedback = total_helpful + total_not_helpful
    agent_helpful_ratio: float | None = None
    if total_feedback > 0:
        agent_helpful_ratio = round(total_helpful / total_feedback, 4)

    return UserStatsResponse(
        agent_id=agent_id,
        agent_contributions=agent_contributions,
        agent_retrievals_received=agent_retrievals_received,
        agent_helpful_ratio=agent_helpful_ratio,
    )
