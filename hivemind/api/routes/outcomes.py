"""Outcome reporting REST endpoint for HiveMind (SDK-01).

Endpoint:
- POST /outcomes — report a usage outcome for a knowledge item

This endpoint is a placeholder for Plan 03 (quality signal recording).
It validates the input, returns a recorded acknowledgement, and is ready
to be wired to the quality signal table once that schema is available.

Operation ID is set explicitly for clean SDK generation (Pattern 6).

Requirements: SDK-01.
"""

from __future__ import annotations

import logging
from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from hivemind.api.auth import require_api_key
from hivemind.db.models import ApiKey

logger = logging.getLogger(__name__)

outcomes_router = APIRouter(prefix="/outcomes", tags=["outcomes"])


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
        description="Optional agent run ID for tracing this outcome to a specific execution",
    )


class OutcomeResponse(BaseModel):
    """Response body for POST /outcomes."""

    status: str
    item_id: str
    outcome: str


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
        "Used to compute quality signals for the knowledge commons. "
        "Full wiring to the quality signal table is completed in Plan 03."
    ),
    status_code=202,
)
async def report_outcome_endpoint(
    body: OutcomeRequest,
    api_key_record: ApiKey = Depends(require_api_key),
) -> OutcomeResponse:
    """Record a usage outcome for a knowledge item.

    org_id is always extracted from the authenticated API key.
    Outcome data will be associated with the org in Phase 3 quality signal recording.
    """
    org_id = api_key_record.org_id
    logger.info(
        "Outcome reported: item_id=%s outcome=%s org_id=%s run_id=%s",
        body.item_id,
        body.outcome,
        org_id,
        body.run_id,
    )

    # Placeholder: return acknowledged. Plan 03 will wire this to quality signal DB.
    return OutcomeResponse(
        status="recorded",
        item_id=body.item_id,
        outcome=body.outcome,
    )
