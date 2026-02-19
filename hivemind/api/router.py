"""Top-level FastAPI APIRouter for the HiveMind REST API (v1).

Mount this router on the FastAPI app to expose all /api/v1/ endpoints.
Five sub-routers are registered below.

Prefix:  /api/v1
Tags:    ["rest-api"]

Sub-routers included:
- knowledge_router      — GET /api/v1/knowledge/search, GET /api/v1/knowledge/{item_id}
- outcomes_router       — POST /api/v1/outcomes
- stream_router         — GET /api/v1/stream/feed (SSE real-time knowledge feed)
- contributions_router  — GET /api/v1/contributions, POST /api/v1/contributions/{id}/approve|reject
- stats_router          — GET /api/v1/stats/commons|org|user

Requirements: SDK-01, DASH-01, DASH-03, DASH-05, DASH-06.
"""

from __future__ import annotations

from fastapi import APIRouter

from hivemind.api.routes.contributions import contributions_router
from hivemind.api.routes.knowledge import knowledge_router
from hivemind.api.routes.outcomes import outcomes_router
from hivemind.api.routes.stats import stats_router
from hivemind.api.routes.stream import stream_router

api_router = APIRouter(prefix="/api/v1", tags=["rest-api"])

api_router.include_router(knowledge_router)
api_router.include_router(outcomes_router)
api_router.include_router(stream_router)
api_router.include_router(contributions_router)
api_router.include_router(stats_router)
