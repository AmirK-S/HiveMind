"""Outcome reporting REST endpoint for HiveMind (SDK-01, MCP-06).

Endpoint:
- POST /outcomes — report a usage outcome for a knowledge item

Records whether retrieved knowledge helped an agent solve a problem.
These signals drive quality score evolution (QI-01, QI-02).

Deduplication: if run_id is provided and a signal for (item_id, run_id) already
exists, the call is idempotent — returns success with status "already_recorded".

Operation ID is set explicitly for clean SDK generation (Pattern 6).

Requirements: SDK-01, MCP-06.
"""

from __future__ import annotations

import logging
import uuid as _uuid

import sqlalchemy as sa
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import Literal

from hivemind.api.auth import require_api_key
from hivemind.db.models import ApiKey, KnowledgeItem, QualitySignal
from hivemind.db.session import get_session
from hivemind.quality.signals import record_signal

logger = logging.getLogger(__name__)

outcomes_router = APIRouter(prefix="/outcomes", tags=["outcomes"])

# Signal type mapping from outcome string to DB signal_type vocabulary
_OUTCOME_TO_SIGNAL = {
    "solved": "outcome_solved",
    "did_not_help": "outcome_not_helpful",
}

# Column reference for denormalized counter increment per outcome
_OUTCOME_TO_COUNTER_KEY = {
    "solved": "helpful_count",
    "did_not_help": "not_helpful_count",
}


# ---------------------------------------------------------------------------
# Request / response schemas
# ---------------------------------------------------------------------------


class OutcomeRequest(BaseModel):
    """Request body for POST /outcomes."""

    item_id: str = Field(..., description="UUID of the knowledge item this outcome applies to")
    outcome: Literal["solved", "did_not_help"] = Field(
        ..., description="Outcome of using this knowledge item"
    )
    run_id: str | None = Field(
        default=None,
        description=(
            "Optional agent run ID for deduplication and tracing. "
            "Strongly recommended — prevents double-counting on retries."
        ),
    )


class OutcomeResponse(BaseModel):
    """Response body for POST /outcomes."""

    status: str
    item_id: str
    outcome: str
    signal_id: str | None = None


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------


@outcomes_router.post(
    "",
    response_model=OutcomeResponse,
    operation_id="report_outcome",
    summary="Report a usage outcome for a knowledge item",
    description=(
        "Records whether a knowledge item helped solve a problem or did not help. "
        "Used to compute quality signals for the knowledge commons (QI-01, QI-02). "
        "Deduplication by run_id ensures idempotency on retries."
    ),
    status_code=202,
)
async def report_outcome_endpoint(
    body: OutcomeRequest,
    api_key_record: ApiKey = Depends(require_api_key),
) -> OutcomeResponse:
    """Record a usage outcome for a knowledge item.

    org_id is always extracted from the authenticated API key (ACL-01).
    The item must exist and be accessible to the calling org.
    Duplicate outcome reports for the same (item_id, run_id) are idempotent.
    """
    org_id = api_key_record.org_id

    # -----------------------------------------------------------------------
    # Validate item_id is a well-formed UUID
    # -----------------------------------------------------------------------
    try:
        item_uuid = _uuid.UUID(body.item_id)
    except ValueError:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid item_id format: '{body.item_id}' is not a valid UUID.",
        )

    # -----------------------------------------------------------------------
    # Verify item exists and is accessible to this org
    # -----------------------------------------------------------------------
    async with get_session() as session:
        result = await session.execute(
            sa.select(KnowledgeItem.id).where(
                KnowledgeItem.id == item_uuid,
                # Org isolation: own items OR public commons (ACL-01)
                (KnowledgeItem.org_id == org_id) | (KnowledgeItem.is_public == True),  # noqa: E712
                KnowledgeItem.deleted_at.is_(None),
            )
        )
        item_exists = result.scalar_one_or_none() is not None

    if not item_exists:
        # Never reveal existence of items in other orgs (ACL-01, pitfall 6)
        raise HTTPException(
            status_code=404,
            detail=f"Knowledge item '{body.item_id}' not found.",
        )

    # -----------------------------------------------------------------------
    # Deduplication check: same (item_id, run_id) must not insert twice
    # -----------------------------------------------------------------------
    if body.run_id is not None:
        async with get_session() as session:
            existing_result = await session.execute(
                sa.select(QualitySignal.id).where(
                    QualitySignal.knowledge_item_id == item_uuid,
                    QualitySignal.run_id == body.run_id,
                    QualitySignal.signal_type.in_(
                        ["outcome_solved", "outcome_not_helpful"]
                    ),
                )
            )
            existing_signal = existing_result.scalar_one_or_none()

        if existing_signal is not None:
            logger.info(
                "Duplicate outcome report: item_id=%s run_id=%s — returning existing signal",
                body.item_id,
                body.run_id,
            )
            return OutcomeResponse(
                status="already_recorded",
                item_id=body.item_id,
                outcome=body.outcome,
                signal_id=str(existing_signal),
            )

    # -----------------------------------------------------------------------
    # Record the quality signal
    # -----------------------------------------------------------------------
    signal_type = _OUTCOME_TO_SIGNAL[body.outcome]
    signal_id = await record_signal(
        knowledge_item_id=body.item_id,
        signal_type=signal_type,
        agent_id=api_key_record.agent_id,
        run_id=body.run_id,
    )

    # -----------------------------------------------------------------------
    # Atomically increment the appropriate denormalized counter
    # -----------------------------------------------------------------------
    counter_key = _OUTCOME_TO_COUNTER_KEY[body.outcome]
    async with get_session() as session:
        await session.execute(
            sa.update(KnowledgeItem)
            .where(KnowledgeItem.id == item_uuid)
            .values({counter_key: getattr(KnowledgeItem, counter_key) + 1})
        )
        await session.commit()

    logger.info(
        "Outcome recorded via REST: item_id=%s outcome=%s signal_id=%s run_id=%s org_id=%s",
        body.item_id,
        body.outcome,
        signal_id,
        body.run_id,
        org_id,
    )

    return OutcomeResponse(
        status="recorded",
        item_id=body.item_id,
        outcome=body.outcome,
        signal_id=signal_id,
    )
