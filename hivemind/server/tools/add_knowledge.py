"""add_knowledge MCP tool for HiveMind.

Security design (ACL-01, TRUST-01, SEC-01, SEC-03, TRUST-04):
- org_id is ALWAYS taken from the bearer token, never from tool arguments
- Raw content is scanned for prompt injection BEFORE PII stripping (SEC-01)
- Anti-sybil burst detection enforced after injection scan (SEC-03)
- Raw content is PII-stripped BEFORE any DB insert — raw text is never stored
- Content with >50% placeholders is auto-rejected (too redacted to be useful)
- Auto-approve rules checked post-hash — matching org+category skips pending queue (TRUST-04)
- Contributions enter pending_contributions (quarantine) or knowledge_items (auto-approved)

Flow:
  1. Extract and verify bearer token -> AuthContext
  2. Validate input parameters
  1.5. Scan for prompt injection (SEC-01)
  1.6. Anti-sybil burst detection (SEC-03)
  3. Strip PII from content
  4. Auto-reject if should_reject is True
  5. Compute content hash of cleaned text
  5a. Check auto-approve rules (TRUST-04)
  5b. Run dedup pipeline (KM-03) — three-stage near-duplicate detection
  5c. If DUPLICATE: run conflict resolution (KM-07) — UPDATE/ADD/NOOP/VERSION_FORK
  5d. Insert directly with embedding (auto-approve path) OR into pending queue (normal path)
  6. Return contribution_id + status
"""

from __future__ import annotations

import datetime

from fastmcp.server.dependencies import get_http_headers
from mcp.types import CallToolResult, TextContent
from sqlalchemy import select

from hivemind.db.models import AutoApproveRule, KnowledgeCategory, KnowledgeItem, PendingContribution
from hivemind.db.session import get_session
from hivemind.pipeline.embedder import get_embedder
from hivemind.pipeline.injection import InjectionScanner
from hivemind.pipeline.pii import strip_pii
from hivemind.security.rate_limit import check_burst, get_redis_connection
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

    The content is scanned for prompt injection, then PII-stripped before any
    storage. If more than 50% of the post-strip content is placeholder tokens,
    the contribution is auto-rejected. If an auto-approve rule matches the
    org+category, the item is inserted directly into the knowledge commons;
    otherwise it enters the pending_contributions queue for operator review.

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

    # Step 1.5: Scan for prompt injection BEFORE PII stripping (SEC-01)
    # Injection patterns may be hidden in text that gets partially redacted —
    # scan raw content before any modification.
    is_injection, injection_score = InjectionScanner.get_instance().is_injection(content)
    if is_injection:
        return CallToolResult(
            content=[TextContent(
                type="text",
                text=(
                    f"Rejected: content contains potential prompt injection "
                    f"(confidence: {injection_score:.0%}). "
                    f"Malicious instructions are not allowed in the commons."
                ),
            )],
            isError=True,
        )

    # Step 1.6: Anti-sybil burst detection (SEC-03)
    # Check if this org is submitting contributions at an anomalous rate.
    # Uses Redis ZSET sliding window from rate_limit.py.
    redis_conn = get_redis_connection()
    if redis_conn is not None:
        import uuid as _uuid
        contribution_id = str(_uuid.uuid4())  # temp ID for burst tracking
        is_burst = await check_burst(auth.org_id, contribution_id, redis_conn)
        if is_burst:
            return CallToolResult(
                content=[TextContent(
                    type="text",
                    text=(
                        "Rate limit exceeded: too many contributions in a short window. "
                        "Please wait before submitting again."
                    ),
                )],
                isError=True,
            )

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
    import hashlib
    content_hash = hashlib.sha256(cleaned_content.encode()).hexdigest()

    # Step 5: Dedup pipeline — three-stage near-duplicate detection (KM-03)
    # Runs BEFORE the DB insert to avoid writing duplicates into the commons.
    # Lazy imports to avoid circular dependencies.
    from hivemind.dedup.pipeline import run_dedup_pipeline
    from hivemind.conflict.resolver import apply_conflict_resolution, resolve_conflict

    dedup_result = await run_dedup_pipeline(cleaned_content, auth.org_id)

    # Track VERSION_FORK valid_at for new item insertion
    _fork_valid_at = None

    if dedup_result.get("action") == "DUPLICATE":
        # Step 5a: Conflict resolution — classify relationship with the best match
        top_duplicate = dedup_result["duplicates"][0] if dedup_result.get("duplicates") else {}
        resolution = await resolve_conflict(cleaned_content, top_duplicate, auth.org_id)

        if resolution["action"] == "NOOP":
            # Exact or near-exact duplicate — block insertion, return informational
            return {
                "contribution_id": resolution.get("existing_item_id", ""),
                "status": "duplicate_detected",
                "category": category,
                "message": (
                    "Contribution not added: near-duplicate already exists in the commons. "
                    f"Reason: {resolution.get('reason', 'duplicate')}"
                ),
                "duplicate_of": resolution.get("existing_item_id", ""),
            }

        if resolution["action"] in ("UPDATE", "VERSION_FORK"):
            # Apply resolution — expire/invalidate the existing item
            applied = await apply_conflict_resolution(
                resolution=resolution,
                new_content=cleaned_content,
                existing_item_id=resolution.get("existing_item_id", ""),
                org_id=auth.org_id,
            )
            if resolution["action"] == "VERSION_FORK":
                # Capture valid_at for new item (world-time start of the fork)
                _fork_valid_at = applied.get("valid_at")
            # Fall through to insert the new item below

        elif resolution["action"] == "FLAGGED_FOR_REVIEW":
            # Multi-hop conflict — insert as pending with a conflict flag note
            # Store the flag in the tags field to avoid schema change
            if tags is None:
                tags = []
            tags = list(tags)
            if "conflict_flagged" not in tags:
                tags.append("conflict_flagged")
            # Fall through to normal pending queue insert below

        # resolution["action"] == "ADD": fall through to normal insert (no DB changes)

    # Step 5b: Insert — either directly (auto-approve) or into pending queue
    async with get_session() as session:
        # Step 5b-i: Check auto-approve rules (TRUST-04)
        auto_approve_result = await session.execute(
            select(AutoApproveRule).where(
                AutoApproveRule.org_id == auth.org_id,
                AutoApproveRule.category == category_enum,
                AutoApproveRule.is_auto_approve == True,  # noqa: E712
            )
        )
        auto_approve_rule = auto_approve_result.scalar_one_or_none()

        if auto_approve_rule:
            # Auto-approved: skip pending queue, insert directly with embedding
            embedding = get_embedder().embed(cleaned_content)
            item = KnowledgeItem(
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
                is_public=False,  # auto-approved items start private
                embedding=embedding,
                contributed_at=datetime.datetime.now(datetime.timezone.utc),
                approved_at=datetime.datetime.now(datetime.timezone.utc),
                # VERSION_FORK: new item takes valid_at = fork time (world-time start)
                valid_at=_fork_valid_at,
            )
            session.add(item)
            await session.commit()
            return {
                "contribution_id": str(item.id),
                "status": "auto_approved",
                "category": category,
                "message": "Knowledge contribution auto-approved and added to the commons.",
            }
        else:
            # Normal flow: insert to pending_contributions queue
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

        return {
            "contribution_id": contribution_id,
            "status": "queued",
            "category": category,
            "message": "Knowledge contribution queued for review.",
        }
