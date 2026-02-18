"""list_knowledge MCP tool for HiveMind.

Returns the calling agent's own contributions — both pending and approved.
Only items belonging to the agent's own source_agent_id (from JWT) are returned;
agents cannot see other agents' contributions.

Pagination: offset-based, cursor encoded as base64 integer (same scheme as
search_knowledge).

Security (ACL-01):
- org_id and agent_id are extracted from the bearer token, never from tool args
- Query filters by BOTH org_id AND source_agent_id — per-agent isolation
"""

from __future__ import annotations

import base64
import datetime

from fastmcp.server.dependencies import get_http_headers
from mcp.types import CallToolResult, TextContent
from sqlalchemy import func, or_, select

from hivemind.db.models import KnowledgeCategory, KnowledgeItem, PendingContribution
from hivemind.db.session import get_session
from hivemind.server.auth import decode_token


# ---------------------------------------------------------------------------
# Cursor helpers (re-used pattern from search_knowledge)
# ---------------------------------------------------------------------------


def _encode_cursor(offset: int) -> str:
    return base64.urlsafe_b64encode(str(offset).encode()).decode()


def _decode_cursor(cursor: str) -> int:
    try:
        return int(base64.urlsafe_b64decode(cursor.encode()).decode())
    except Exception:
        return 0


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


# ---------------------------------------------------------------------------
# list_knowledge tool
# ---------------------------------------------------------------------------


async def list_knowledge(
    status: str = "all",
    category: str | None = None,
    limit: int = 20,
    cursor: str | None = None,
) -> dict | CallToolResult:
    """List your own knowledge contributions (pending and/or approved).

    Returns a paginated view of the contributions this agent has made within
    its organisation's namespace.  Agents can only see their own contributions
    — the filter is enforced via the JWT bearer token, never from tool arguments.

    Args:
        status:   Filter by contribution status.  One of "pending", "approved",
                  or "all" (default).
        category: Optional KnowledgeCategory value to narrow results.
        limit:    Maximum items to return per page (default 20, max 100).
        cursor:   Opaque pagination cursor returned in a previous response.

    Returns:
        Dict with contributions[], total_count, and next_cursor.
        CallToolResult with isError=True on auth or validation failure.
    """
    # Extract auth — both org_id and agent_id needed for per-agent isolation
    try:
        headers = get_http_headers()
        auth = _extract_auth(headers)
    except ValueError as exc:
        return _auth_error(str(exc))

    org_id = auth.org_id
    agent_id = auth.agent_id

    # Validate status parameter
    valid_statuses = {"pending", "approved", "all"}
    if status not in valid_statuses:
        return CallToolResult(
            content=[TextContent(
                type="text",
                text=(
                    f"Invalid status '{status}'. "
                    f"Valid values: {', '.join(sorted(valid_statuses))}"
                ),
            )],
            isError=True,
        )

    # Validate optional category
    category_enum: KnowledgeCategory | None = None
    if category is not None:
        try:
            category_enum = KnowledgeCategory(category)
        except ValueError:
            valid_values = [c.value for c in KnowledgeCategory]
            return CallToolResult(
                content=[TextContent(
                    type="text",
                    text=(
                        f"Invalid category '{category}'. "
                        f"Valid values: {', '.join(valid_values)}"
                    ),
                )],
                isError=True,
            )

    # Cap limit
    limit = min(max(1, limit), 100)
    offset = _decode_cursor(cursor) if cursor else 0

    contributions: list[dict] = []
    total_count = 0

    async with get_session() as session:
        # -------------------------------------------------------------------
        # Build result sets for each requested status
        # -------------------------------------------------------------------
        pending_items: list[dict] = []
        approved_items: list[dict] = []

        if status in ("pending", "all"):
            stmt = select(PendingContribution).where(
                PendingContribution.org_id == org_id,
                PendingContribution.source_agent_id == agent_id,
            )
            if category_enum is not None:
                stmt = stmt.where(PendingContribution.category == category_enum)
            stmt = stmt.order_by(PendingContribution.contributed_at.desc())

            result = await session.execute(stmt)
            for item in result.scalars().all():
                pending_items.append({
                    "id": str(item.id),
                    "status": "pending",
                    "content_preview": item.content[:80] + ("..." if len(item.content) > 80 else ""),
                    "category": item.category.value,
                    "confidence": item.confidence,
                    "contributed_at": item.contributed_at.isoformat(),
                    "is_public": None,  # pending items don't have a visibility setting yet
                })

        if status in ("approved", "all"):
            stmt = select(KnowledgeItem).where(
                KnowledgeItem.org_id == org_id,
                KnowledgeItem.source_agent_id == agent_id,
                KnowledgeItem.deleted_at.is_(None),  # exclude soft-deleted items
            )
            if category_enum is not None:
                stmt = stmt.where(KnowledgeItem.category == category_enum)
            stmt = stmt.order_by(KnowledgeItem.contributed_at.desc())

            result = await session.execute(stmt)
            for item in result.scalars().all():
                approved_items.append({
                    "id": str(item.id),
                    "status": "approved",
                    "content_preview": item.content[:80] + ("..." if len(item.content) > 80 else ""),
                    "category": item.category.value,
                    "confidence": item.confidence,
                    "contributed_at": item.contributed_at.isoformat(),
                    "is_public": item.is_public,
                })

    # Merge: pending first (newest), then approved (newest)
    # This simple merge preserves recency within each group
    all_items = pending_items + approved_items
    total_count = len(all_items)

    # Apply pagination over merged list
    page_items = all_items[offset : offset + limit]

    has_more = (offset + limit) < total_count
    next_cursor = _encode_cursor(offset + limit) if has_more else None

    return {
        "contributions": page_items,
        "total_count": total_count,
        "next_cursor": next_cursor,
    }
