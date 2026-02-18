"""delete_knowledge MCP tool for HiveMind.

Soft-deletes an approved knowledge item owned by the calling agent.

Security (ACL-01, pitfall 6):
- org_id and agent_id are extracted from the bearer token, never from tool args
- Query filters by id AND org_id AND source_agent_id — agents can only delete
  their own items within their own org namespace
- Returns 404 (not 403) for items not found or owned by another agent/org so
  existence of items in other namespaces is not revealed (per research pitfall 6)

Soft-delete:
- Sets deleted_at timestamp instead of removing the physical row
- Deleted items are excluded from search_knowledge and list_knowledge results
- Physical rows are retained for audit trail
"""

from __future__ import annotations

import datetime
import uuid as _uuid

from fastmcp.server.dependencies import get_http_headers
from mcp.types import CallToolResult, TextContent
from sqlalchemy import select

from hivemind.db.models import KnowledgeItem
from hivemind.db.session import get_session
from hivemind.server.auth import decode_token


# ---------------------------------------------------------------------------
# Auth helpers
# ---------------------------------------------------------------------------


def _extract_auth(headers: dict[str, str]):
    auth_header = headers.get("authorization", "")
    if not auth_header.startswith("Bearer "):
        raise ValueError(
            "Missing or invalid Authorization header. Expected 'Bearer <token>'."
        )
    token = auth_header[len("Bearer "):]
    return decode_token(token)


def _auth_error(message: str) -> CallToolResult:
    return CallToolResult(
        content=[TextContent(type="text", text=message)],
        isError=True,
    )


def _not_found(id: str) -> CallToolResult:
    """Return 404-style error — does NOT reveal whether item exists in another org."""
    return CallToolResult(
        content=[TextContent(
            type="text",
            text=f"Knowledge item '{id}' not found.",
        )],
        isError=True,
    )


# ---------------------------------------------------------------------------
# delete_knowledge tool
# ---------------------------------------------------------------------------


async def delete_knowledge(id: str) -> dict | CallToolResult:
    """Soft-delete a knowledge item you contributed.

    Sets the deleted_at timestamp on the item so it no longer appears in
    search results.  Only items you own (same agent_id and org_id from your
    JWT) can be deleted.  The physical row is retained for audit purposes.

    Args:
        id: UUID of the approved knowledge item to delete.

    Returns:
        Dict with id, status "deleted", and a confirmation message on success.
        CallToolResult with isError=True if not found, already deleted, or on
        auth failure.  Returns a 404-style error for items in other orgs (does
        not reveal existence per research pitfall 6).
    """
    # Extract auth — org_id and agent_id both needed for ownership check
    try:
        headers = get_http_headers()
        auth = _extract_auth(headers)
    except ValueError as exc:
        return _auth_error(str(exc))

    org_id = auth.org_id
    agent_id = auth.agent_id

    # Validate UUID format
    try:
        item_uuid = _uuid.UUID(id)
    except ValueError:
        return CallToolResult(
            content=[TextContent(
                type="text",
                text=f"Invalid id format: '{id}' is not a valid UUID.",
            )],
            isError=True,
        )

    async with get_session() as session:
        # Ownership check: id + org_id + agent_id + not-already-deleted
        stmt = select(KnowledgeItem).where(
            KnowledgeItem.id == item_uuid,
            KnowledgeItem.org_id == org_id,
            KnowledgeItem.source_agent_id == agent_id,
            KnowledgeItem.deleted_at.is_(None),  # already deleted items return 404
        )
        result = await session.execute(stmt)
        item = result.scalar_one_or_none()

        if item is None:
            # Per research pitfall 6: return 404 (not 403) — never reveal that
            # an item exists in another org or belongs to another agent
            return _not_found(id)

        # Soft-delete: set deleted_at timestamp, do NOT physically remove the row
        item.deleted_at = datetime.datetime.now(datetime.timezone.utc)
        await session.commit()

    return {
        "id": id,
        "status": "deleted",
        "message": (
            "Knowledge item deleted. "
            "It will no longer appear in search results."
        ),
    }
