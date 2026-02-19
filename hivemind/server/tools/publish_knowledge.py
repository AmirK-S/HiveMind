"""publish_knowledge MCP tool for HiveMind.

Allows an agent to explicitly publish knowledge from their private namespace
to the public commons, or unpublish it back to private. Publication is
reversible (ACL-02).

Security: Only the owning org can publish/unpublish their own items.
org_id is ALWAYS taken from the bearer token, never from tool arguments (ACL-01).

Flow:
  1. Extract and verify bearer token -> AuthContext
  2. Validate UUID format
  3. Fetch KnowledgeItem by id WHERE org_id == auth.org_id AND deleted_at IS NULL
  4. If not found, return 404 error (never reveal existence in other orgs)
  5. Update item.is_public = is_public
  6. Commit
  7. Return success dict with id, is_public, and message

Requirements: ACL-02 (reversible publication to the public commons).
"""

from __future__ import annotations

import uuid as _uuid

from fastmcp.server.dependencies import get_http_headers
from mcp.types import CallToolResult, TextContent
from sqlalchemy import select

from hivemind.db.models import KnowledgeItem
from hivemind.db.session import get_session
from hivemind.server.auth import decode_token


def _extract_auth(headers: dict[str, str]):
    """Extract and decode the Authorization bearer token.

    Args:
        headers: HTTP headers dict from get_http_headers().

    Returns:
        AuthContext with org_id and agent_id.

    Raises:
        ValueError: If the Authorization header is missing, malformed, or the
                    token is invalid.
    """
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


async def publish_knowledge(id: str, is_public: bool) -> dict | CallToolResult:
    """Toggle the public visibility of a knowledge item in HiveMind.

    Publishes a private knowledge item to the public commons, or unpublishes
    it back to private. Publication is fully reversible (ACL-02).

    Security: The calling agent must own the item (org_id from bearer token
    must match item.org_id). Items belonging to other orgs are never revealed
    — a 404 is returned regardless of whether the item exists in another org.

    Args:
        id:        UUID string of the KnowledgeItem to publish or unpublish.
        is_public: True to publish to the public commons; False to unpublish
                   back to private.

    Returns:
        Dict with id, is_public, and message on success.
        CallToolResult with isError=True on any failure.

    Requirements: ACL-02 (reversible publication to the public commons).
    """
    # Step 1: Extract auth context from bearer token (org_id NEVER from args)
    try:
        headers = get_http_headers()
        auth = _extract_auth(headers)
    except ValueError as exc:
        return _error(str(exc))

    # Step 2: Validate UUID format
    try:
        item_id = _uuid.UUID(id)
    except ValueError:
        return _error(f"Invalid UUID format: '{id}'. Expected a valid UUID string.")

    # Step 3: Fetch KnowledgeItem scoped to the caller's org
    async with get_session() as session:
        result = await session.execute(
            select(KnowledgeItem).where(
                KnowledgeItem.id == item_id,
                KnowledgeItem.org_id == auth.org_id,
                KnowledgeItem.deleted_at.is_(None),
            )
        )
        item = result.scalar_one_or_none()

        # Step 4: Return 404 if not found — never reveal cross-org existence
        if item is None:
            return _error(
                f"Knowledge item '{id}' not found or you do not have access to it."
            )

        # Step 5: Toggle is_public (reversible — ACL-02)
        item.is_public = is_public
        await session.commit()

    # Step 6: Return success
    if is_public:
        message = "Knowledge published to the public commons."
    else:
        message = "Knowledge unpublished from the public commons."

    return {
        "id": str(item_id),
        "is_public": is_public,
        "message": message,
    }
