"""report_outcome MCP tool for HiveMind.

MCP-06: Explicit active confirmation signal for quality scoring.

When an agent calls this tool, it records whether retrieved knowledge actually
helped solve a problem. These outcome signals are the primary driver of quality
score evolution (QI-01, QI-02) — they distinguish knowledge that is retrieved
from knowledge that is genuinely useful.

Signal types recorded:
- "outcome_solved"       : item helped the agent solve a task
- "outcome_not_helpful"  : item was retrieved but did not help

Deduplication: if a run_id is provided and a signal with that (item_id, run_id)
combination already exists, the call is idempotent — the existing signal is
returned with status "already_recorded".

Security (ACL-01):
- org_id is extracted from the bearer token, NEVER from tool arguments
- item must exist and be accessible to the calling org before recording signal
"""

from __future__ import annotations

import logging
import uuid as _uuid

import sqlalchemy as sa
from fastmcp.server.dependencies import get_http_headers
from mcp.types import CallToolResult, TextContent

from hivemind.db.models import KnowledgeItem, QualitySignal
from hivemind.db.session import get_session
from hivemind.quality.signals import record_signal
from hivemind.server.auth import decode_token

logger = logging.getLogger(__name__)

# Valid outcome values (MCP-06)
_VALID_OUTCOMES = {"solved", "did_not_help"}

# Signal type mapping from outcome string to DB signal_type vocabulary
_OUTCOME_TO_SIGNAL = {
    "solved": "outcome_solved",
    "did_not_help": "outcome_not_helpful",
}

# helpful_count / not_helpful_count column to increment per outcome
_OUTCOME_TO_COUNTER = {
    "solved": KnowledgeItem.helpful_count,
    "did_not_help": KnowledgeItem.not_helpful_count,
}


# ---------------------------------------------------------------------------
# Auth helpers (same pattern as search_knowledge)
# ---------------------------------------------------------------------------


def _extract_auth(headers: dict[str, str]):
    """Extract and decode the Authorization bearer token."""
    auth_header = headers.get("authorization", "")
    if not auth_header.startswith("Bearer "):
        raise ValueError("Missing or invalid Authorization header. Expected 'Bearer <token>'.")
    token = auth_header[len("Bearer "):]
    return decode_token(token)


def _error(message: str) -> CallToolResult:
    """Return a structured MCP isError response."""
    return CallToolResult(
        content=[TextContent(type="text", text=message)],
        isError=True,
    )


# ---------------------------------------------------------------------------
# report_outcome tool
# ---------------------------------------------------------------------------


async def report_outcome(
    item_id: str,
    outcome: str,
    run_id: str | None = None,
) -> dict | CallToolResult:
    """Report whether a knowledge item helped solve a problem (MCP-06).

    Records an explicit outcome signal for the given knowledge item. This signal
    is used by the quality scorer (QI-01, QI-02) to evolve quality_score over
    time. "solved" outcomes increase the item's quality score; "did_not_help"
    outcomes decrease it.

    Deduplication: if run_id is provided and an outcome signal with the same
    (item_id, run_id) pair already exists, the call returns successfully with
    status "already_recorded" without inserting a duplicate row.

    Args:
        item_id:  UUID of the knowledge item being rated.
        outcome:  Must be "solved" or "did_not_help".
        run_id:   Optional agent run ID for deduplication and tracing. Strongly
                  recommended — prevents double-counting when retries occur.

    Returns:
        dict: { status, item_id, outcome, signal_id }
        CallToolResult with isError=True on validation or auth failure.
    """
    # -----------------------------------------------------------------------
    # Auth: extract JWT from headers (ACL-01 — org_id never from arguments)
    # -----------------------------------------------------------------------
    try:
        headers = get_http_headers()
        auth = _extract_auth(headers)
    except ValueError as exc:
        return _error(str(exc))

    org_id = auth.org_id
    agent_id = auth.agent_id

    # -----------------------------------------------------------------------
    # Validate outcome value
    # -----------------------------------------------------------------------
    if outcome not in _VALID_OUTCOMES:
        return _error(
            f"Invalid outcome '{outcome}'. Must be one of: {', '.join(sorted(_VALID_OUTCOMES))}"
        )

    # -----------------------------------------------------------------------
    # Validate item_id is a well-formed UUID
    # -----------------------------------------------------------------------
    try:
        item_uuid = _uuid.UUID(item_id)
    except ValueError:
        return _error(f"Invalid item_id format: '{item_id}' is not a valid UUID.")

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
        return _error(f"Knowledge item '{item_id}' not found.")

    # -----------------------------------------------------------------------
    # Deduplication check: same (item_id, run_id) must not insert twice
    # -----------------------------------------------------------------------
    if run_id is not None:
        async with get_session() as session:
            existing_result = await session.execute(
                sa.select(QualitySignal.id).where(
                    QualitySignal.knowledge_item_id == item_uuid,
                    QualitySignal.run_id == run_id,
                    QualitySignal.signal_type.in_(
                        ["outcome_solved", "outcome_not_helpful"]
                    ),
                )
            )
            existing_signal = existing_result.scalar_one_or_none()

        if existing_signal is not None:
            logger.info(
                "Duplicate outcome report detected: item_id=%s run_id=%s — returning existing signal",
                item_id,
                run_id,
            )
            return {
                "status": "already_recorded",
                "item_id": item_id,
                "outcome": outcome,
                "signal_id": str(existing_signal),
            }

    # -----------------------------------------------------------------------
    # Record the quality signal
    # -----------------------------------------------------------------------
    signal_type = _OUTCOME_TO_SIGNAL[outcome]
    signal_id = await record_signal(
        knowledge_item_id=item_id,
        signal_type=signal_type,
        agent_id=agent_id,
        run_id=run_id,
    )

    # -----------------------------------------------------------------------
    # Atomically increment the appropriate denormalized counter
    # -----------------------------------------------------------------------
    counter_col = _OUTCOME_TO_COUNTER[outcome]
    async with get_session() as session:
        await session.execute(
            sa.update(KnowledgeItem)
            .where(KnowledgeItem.id == item_uuid)
            .values({counter_col.key: counter_col + 1})
        )
        await session.commit()

    logger.info(
        "Outcome recorded: item_id=%s outcome=%s signal_id=%s run_id=%s agent_id=%s",
        item_id,
        outcome,
        signal_id,
        run_id,
        agent_id,
    )

    return {
        "status": "recorded",
        "item_id": item_id,
        "outcome": outcome,
        "signal_id": signal_id,
    }
