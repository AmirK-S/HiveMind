"""Knowledge search and fetch REST endpoints for the HiveMind API (SDK-01).

Endpoints:
- GET /knowledge/search — semantic search with pagination
- GET /knowledge/{item_id} — fetch full content by UUID

Both endpoints require the ``X-API-Key`` header and delegate search/fetch logic
to the internal ``_search`` and ``_fetch_by_id`` helpers in
``hivemind.server.tools.search_knowledge`` to avoid duplicating query logic.

The REST layer is a thin HTTP adapter over the same embedding + cosine search
used by the MCP tool.

Security:
- org_id is extracted from the authenticated ApiKey record — never from query params.
- Org isolation: (org_id == :org_id) OR (is_public == True) — same as MCP tool.
- Content hash integrity check in fetch mode (SEC-02).

Operation IDs are set explicitly so that the OpenAPI spec generates clean method
names for SDK clients (Pattern 6 from Phase 03 research).

Requirements: SDK-01.
"""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from hivemind.api.auth import require_api_key
from hivemind.db.models import ApiKey
from hivemind.server.tools.search_knowledge import _fetch_by_id, _search

logger = logging.getLogger(__name__)

knowledge_router = APIRouter(prefix="/knowledge", tags=["knowledge"])


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------


class KnowledgeSearchResult(BaseModel):
    """Single result item in a search response."""

    id: str
    title: str
    category: str
    confidence: float
    org_attribution: str
    relevance_score: float

    model_config = {"from_attributes": True}


class KnowledgeSearchResponse(BaseModel):
    """Response body for GET /knowledge/search."""

    results: list[KnowledgeSearchResult]
    total_found: int
    next_cursor: str | None

    model_config = {"from_attributes": True}


class KnowledgeItemResponse(BaseModel):
    """Response body for GET /knowledge/{item_id} — full content."""

    id: str
    content: str
    category: str
    confidence: float
    framework: str | None
    language: str | None
    version: str | None
    tags: dict | None
    org_attribution: str
    contributed_at: str
    # Exactly one of these two fields will be present
    integrity_verified: bool | None = None
    integrity_warning: str | None = None

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@knowledge_router.get(
    "/search",
    response_model=KnowledgeSearchResponse,
    operation_id="search_knowledge",
    summary="Semantic search over the knowledge commons",
    description=(
        "Embeds the query text and performs a cosine similarity search over your "
        "organisation's private namespace plus the public commons. Results are "
        "deduplicated by content hash with private items prioritised."
    ),
)
async def search_knowledge_endpoint(
    query: Annotated[str, Query(description="Search query text")],
    category: Annotated[str | None, Query(description="Optional category filter")] = None,
    limit: Annotated[int, Query(ge=1, le=50, description="Max results (1-50)")] = 10,
    cursor: Annotated[str | None, Query(description="Pagination cursor from previous response")] = None,
    api_key_record: ApiKey = Depends(require_api_key),
) -> KnowledgeSearchResponse:
    """Search knowledge items by semantic similarity.

    org_id is always extracted from the authenticated API key — never from the query string.
    """
    org_id = api_key_record.org_id

    result = await _search(
        query=query,
        org_id=org_id,
        category=category,
        limit=limit,
        cursor=cursor,
    )

    # _search returns CallToolResult on error (e.g. invalid category)
    from mcp.types import CallToolResult

    if isinstance(result, CallToolResult):
        # Extract the error message from the MCP result
        error_text = result.content[0].text if result.content else "Search failed"
        raise HTTPException(status_code=400, detail=error_text)

    return KnowledgeSearchResponse(
        results=[KnowledgeSearchResult(**r) for r in result["results"]],
        total_found=result["total_found"],
        next_cursor=result["next_cursor"],
    )


@knowledge_router.get(
    "/{item_id}",
    response_model=KnowledgeItemResponse,
    operation_id="get_knowledge_item",
    summary="Fetch a knowledge item by UUID",
    description=(
        "Returns full content for a specific knowledge item. "
        "Includes content hash integrity verification (SEC-02). "
        "Returns integrity_verified=True if the hash matches, "
        "or integrity_warning if a mismatch is detected."
    ),
)
async def get_knowledge_item_endpoint(
    item_id: str,
    api_key_record: ApiKey = Depends(require_api_key),
) -> KnowledgeItemResponse:
    """Fetch a single knowledge item by UUID with integrity verification.

    org_id is always extracted from the authenticated API key — never from the URL.
    """
    org_id = api_key_record.org_id

    result = await _fetch_by_id(id=item_id, org_id=org_id)

    from mcp.types import CallToolResult

    if isinstance(result, CallToolResult):
        error_text = result.content[0].text if result.content else "Item not found"
        # Map "not found" errors to 404; validation errors to 400
        if "not found" in error_text.lower():
            raise HTTPException(status_code=404, detail=error_text)
        raise HTTPException(status_code=400, detail=error_text)

    return KnowledgeItemResponse(**result)
