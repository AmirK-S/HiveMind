"""add_knowledge MCP tool for HiveMind.

Security design (ACL-01, TRUST-01):
- org_id is ALWAYS taken from the bearer token, never from tool arguments
- Raw content is PII-stripped BEFORE any DB insert — raw text is never stored
- Content with >50% placeholders is auto-rejected (too redacted to be useful)
- Contributions enter pending_contributions (quarantine), not knowledge_items (commons)

Flow:
  1. Extract and verify bearer token -> AuthContext
  2. Validate input parameters
  3. Strip PII from content
  4. Auto-reject if should_reject is True
  5. Compute content hash of cleaned text
  6. Insert into pending_contributions
  7. Return contribution_id + status='queued'
"""

from __future__ import annotations

import datetime
import hashlib

from fastmcp.server.dependencies import get_http_headers
from mcp.types import CallToolResult, TextContent

from hivemind.db.models import KnowledgeCategory, PendingContribution
from hivemind.db.session import get_session
from hivemind.pipeline.pii import strip_pii
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
    from hivemind.server.auth import AuthContext  # noqa: F401 (type only)

    auth_header = headers.get("authorization", "")
    if not auth_header.startswith("Bearer "):
        raise ValueError("Missing or invalid Authorization header. Expected 'Bearer <token>'.")
    token = auth_header[len("Bearer "):]
    return decode_token(token)


def _auth_error(message: str) -> CallToolResult:
    """Return a structured MCP isError response for auth failures."""
    return CallToolResult(
        content=[TextContent(type="text", text=message)],
        isError=True,
    )


async def add_knowledge(
    content: str,
    category: str,
    confidence: float = 0.8,
    framework: str | None = None,
    language: str | None = None,
    version: str | None = None,
    tags: list[str] | None = None,
    run_id: str | None = None,
) -> dict | CallToolResult:
    """Contribute a knowledge item to HiveMind.

    The content is PII-stripped before any storage. If more than 50% of the
    post-strip content is placeholder tokens, the contribution is auto-rejected.
    On success, the item enters the pending_contributions queue and an operator
    can approve it via the CLI.

    Args:
        content:    The knowledge text to contribute (min 10 characters).
        category:   Knowledge category (must be a valid KnowledgeCategory value).
        confidence: Confidence score 0.0–1.0 (default 0.8).
        framework:  Optional framework name (e.g. "fastapi", "langchain").
        language:   Optional programming language (e.g. "python", "typescript").
        version:    Optional version string.
        tags:       Optional list of tags for additional classification.
        run_id:     Optional agent run/session identifier for provenance.

    Returns:
        Dict with contribution_id, status, category, and message on success.
        CallToolResult with isError=True on any failure.
    """
    # Step 0: Validate inputs before touching the DB
    if len(content) < 10:
        return CallToolResult(
            content=[TextContent(
                type="text",
                text="Rejected: content is too short (minimum 10 characters).",
            )],
            isError=True,
        )

    if not (0.0 <= confidence <= 1.0):
        return CallToolResult(
            content=[TextContent(
                type="text",
                text="Rejected: confidence must be between 0.0 and 1.0.",
            )],
            isError=True,
        )

    # Step 0b: Validate category against the controlled vocabulary
    try:
        category_enum = KnowledgeCategory(category)
    except ValueError:
        valid_values = [c.value for c in KnowledgeCategory]
        return CallToolResult(
            content=[TextContent(
                type="text",
                text=(
                    f"Rejected: '{category}' is not a valid category. "
                    f"Valid values: {', '.join(valid_values)}"
                ),
            )],
            isError=True,
        )

    # Step 1: Extract auth context from bearer token
    # org_id is NEVER taken from tool arguments (ACL-01)
    try:
        headers = get_http_headers()
        auth = _extract_auth(headers)
    except ValueError as exc:
        return _auth_error(str(exc))

    # Step 2: PII-strip the content BEFORE any storage (TRUST-01)
    # Raw content is never persisted — only the cleaned version.
    cleaned_content, should_reject = strip_pii(content)

    # Step 3: Auto-reject if too much was redacted
    if should_reject:
        return CallToolResult(
            content=[TextContent(
                type="text",
                text=(
                    "Rejected: too much content was identified as sensitive and redacted (>50%). "
                    "The contribution cannot be meaningfully preserved."
                ),
            )],
            isError=True,
        )

    # Step 4: Compute content hash of the cleaned text
    content_hash = hashlib.sha256(cleaned_content.encode()).hexdigest()

    # Step 5: Insert into pending_contributions (quarantine — not the commons)
    async with get_session() as session:
        contribution = PendingContribution(
            org_id=auth.org_id,
            source_agent_id=auth.agent_id,
            run_id=run_id,
            content=cleaned_content,
            content_hash=content_hash,
            category=category_enum,
            confidence=confidence,
            framework=framework,
            language=language,
            version=version,
            tags={"tags": tags} if tags else None,
            contributed_at=datetime.datetime.now(datetime.timezone.utc),
        )
        session.add(contribution)
        await session.commit()
        contribution_id = str(contribution.id)

    # Step 6: Return success — agent moves on (fire-and-forget pattern)
    return {
        "contribution_id": contribution_id,
        "status": "queued",
        "category": category,
        "message": "Knowledge contribution queued for review.",
    }
