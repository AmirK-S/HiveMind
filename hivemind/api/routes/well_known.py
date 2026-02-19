"""Well-known endpoints for MCP discovery directory support.

Serves Smithery server-card.json at the standard MCP well-known path:
  GET /.well-known/mcp/server-card.json

This path MUST be registered on the top-level FastAPI app (not api_router)
because /.well-known/ is a root path, not under /api/v1/.

Requirements: DIST-04 (Smithery discovery), DIST-06 (Glama.ai)
"""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse

well_known_router = APIRouter(tags=["well-known"])


@well_known_router.get("/.well-known/mcp/server-card.json")
async def server_card() -> JSONResponse:
    """Smithery server-card.json endpoint for MCP directory discovery.

    Returns a JSON document describing this MCP server, its authentication
    requirements, and the list of tools it exposes.

    Smithery.ai reads this endpoint when indexing MCP servers to populate
    their directory listing.
    """
    return JSONResponse(
        {
            "serverInfo": {
                "name": "hivemind",
                "description": (
                    "Shared memory system for AI agents — contribute and retrieve "
                    "knowledge from the collective commons"
                ),
                "version": "0.1.0",
            },
            "authentication": {
                "type": "apiKey",
                "in": "header",
                "name": "X-API-Key",
            },
            "tools": [
                {
                    "name": "add_knowledge",
                    "description": "Contribute knowledge to the shared commons",
                },
                {
                    "name": "search_knowledge",
                    "description": "Search the knowledge commons for relevant items",
                },
                {
                    "name": "list_knowledge",
                    "description": "List your contributed knowledge items",
                },
                {
                    "name": "delete_knowledge",
                    "description": "Remove your knowledge contributions",
                },
                {
                    "name": "publish_knowledge",
                    "description": "Publish knowledge to the public commons",
                },
                {
                    "name": "manage_roles",
                    "description": "Manage RBAC roles and permissions",
                },
                {
                    "name": "report_outcome",
                    "description": "Report whether retrieved knowledge was helpful",
                },
            ],
        }
    )
