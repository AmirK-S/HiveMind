"""Top-level FastAPI APIRouter for the HiveMind REST API (v1).

Mount this router on the FastAPI app with ``app.include_router(api_router)``
to expose all /api/v1/ endpoints.

Prefix:  /api/v1
Tags:    ["rest-api"]

Sub-routers included:
- knowledge_router — GET /api/v1/knowledge/search, GET /api/v1/knowledge/{item_id}
- outcomes_router  — POST /api/v1/outcomes

Requirements: SDK-01 (REST API for generated SDK targets).
"""

from __future__ import annotations

from fastapi import APIRouter

from hivemind.api.routes.knowledge import knowledge_router
from hivemind.api.routes.outcomes import outcomes_router

api_router = APIRouter(prefix="/api/v1", tags=["rest-api"])

api_router.include_router(knowledge_router)
api_router.include_router(outcomes_router)
