---
phase: 03-quality-intelligence-sdks
plan: 02
subsystem: api
tags: [fastapi, rest-api, api-key, sha256, metering, openapi, sdk]

# Dependency graph
requires:
  - phase: 02-trust-security-hardening
    provides: ApiKey model with SHA-256 hash, request_count, billing_period fields
  - phase: 03-quality-intelligence-sdks
    plan: 01
    provides: Phase 3 config foundation
provides:
  - FastAPI APIRouter at /api/v1/ prefix (knowledge search, fetch, outcome reporting)
  - require_api_key FastAPI dependency with SHA-256 hash lookup and atomic metering
  - GET /api/v1/knowledge/search with semantic search via _search() helper
  - GET /api/v1/knowledge/{item_id} with integrity verification via _fetch_by_id()
  - POST /api/v1/outcomes placeholder for quality signal recording (Plan 03)
  - Custom generate_unique_id_function for clean OpenAPI operation IDs
affects:
  - 03-03-PLAN (outcomes endpoint to be wired to quality signal table)
  - 03-07-PLAN (SDK generation targets these operation IDs)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - FastAPI dependency injection for auth + metering (single DB session, no middleware class)
    - APIKeyHeader(auto_error=False) with custom 401 for uniform error messages
    - SHA-256 hash comparison for API key validation (raw key never stored or compared)
    - Atomic billing period reset inside require_api_key (billing_age_days >= reset_days)
    - Thin HTTP adapter pattern: REST routes delegate to existing _search/_fetch_by_id helpers
    - operation_id on each route for deterministic SDK method name generation
    - custom_generate_unique_id_function on FastAPI app for clean OpenAPI spec

key-files:
  created:
    - hivemind/api/__init__.py
    - hivemind/api/auth.py
    - hivemind/api/middleware.py
    - hivemind/api/router.py
    - hivemind/api/routes/__init__.py
    - hivemind/api/routes/knowledge.py
    - hivemind/api/routes/outcomes.py
  modified:
    - hivemind/server/main.py

key-decisions:
  - "Metering integrated into require_api_key dependency (not Starlette middleware) — same DB session as auth, testable via dependency override"
  - "APIKeyHeader(auto_error=False) used so 401 (not 403) is returned for missing/invalid keys"
  - "billing_period_start may be naive UTC — normalised with replace(tzinfo=UTC) before comparison"
  - "REST layer is a thin HTTP adapter over _search/_fetch_by_id — no query logic duplication"
  - "outcomes endpoint returns HTTP 202 (accepted) as it is a placeholder for Plan 03 wiring"

patterns-established:
  - "Auth-metering colocation: increment request_count inside the same DB session as key validation for atomicity"
  - "Thin adapter: REST routes call shared internal functions (_search, _fetch_by_id) from MCP tool layer"
  - "Operation ID discipline: set operation_id on every REST route for predictable SDK generation"

requirements-completed:
  - SDK-01

# Metrics
duration: 3min
completed: 2026-02-19
---

# Phase 03 Plan 02: REST API Layer Summary

**FastAPI REST API at /api/v1/ with X-API-Key authentication, atomic usage metering, semantic knowledge search and fetch endpoints, and clean OpenAPI operation IDs for SDK generation**

## Performance

- **Duration:** 3 min
- **Started:** 2026-02-19T12:15:16Z
- **Completed:** 2026-02-19T12:18:XX Z
- **Tasks:** 2
- **Files modified:** 8

## Accomplishments

- REST API layer at /api/v1/ exposes knowledge search, fetch, and outcome reporting over standard HTTP with X-API-Key authentication
- require_api_key dependency validates SHA-256 hashed keys against the api_keys table and atomically increments request_count + last_used_at in each authenticated request
- Knowledge endpoints reuse _search() and _fetch_by_id() from search_knowledge.py — no query logic duplicated between MCP and REST layers
- FastAPI app generates clean operation IDs (e.g. search_knowledge, get_knowledge_item, report_outcome) for predictable SDK method name generation in Plan 07

## Task Commits

1. **Task 1: REST API router with API key auth and metering middleware** - `09601ba` (feat)
2. **Task 2: Knowledge and outcomes REST endpoints + mount on FastAPI app** - `d0ab877` (feat)

## Files Created/Modified

- `hivemind/api/__init__.py` - Package init for REST API module
- `hivemind/api/auth.py` - require_api_key FastAPI dependency: SHA-256 hash lookup, billing reset, atomic metering
- `hivemind/api/middleware.py` - Design documentation stub (metering integrated into auth dep)
- `hivemind/api/router.py` - Top-level APIRouter at /api/v1 prefix, includes sub-routers
- `hivemind/api/routes/__init__.py` - Routes sub-package init
- `hivemind/api/routes/knowledge.py` - GET /knowledge/search and GET /knowledge/{item_id} with Pydantic response schemas
- `hivemind/api/routes/outcomes.py` - POST /outcomes placeholder with Pydantic validation, HTTP 202
- `hivemind/server/main.py` - Added api_router mount, custom_generate_unique_id_function, APIRoute import

## Decisions Made

- **Metering in auth dependency (not middleware):** The plan offered two options; integrating metering into `require_api_key` was chosen because it runs in the same DB session as key validation (single transaction), is trivially testable via FastAPI dependency overrides, and avoids Starlette BaseHTTPMiddleware streaming pitfalls.
- **APIKeyHeader(auto_error=False) + custom 401:** FastAPI's default for missing header is 403 (Forbidden). Using `auto_error=False` and raising `HTTPException(401)` manually gives consistent 401 for both missing and invalid keys.
- **Billing period UTC normalisation:** `billing_period_start` stored as naive UTC in some rows; normalised with `.replace(tzinfo=UTC)` before comparison to avoid TypeError on timezone-aware subtraction.
- **outcomes returns HTTP 202:** The outcome endpoint is a validated placeholder pending Plan 03 quality signal wiring; 202 (Accepted) signals the request was received but not yet durably processed.

## Deviations from Plan

None - plan executed exactly as written. The metering-in-auth approach was the plan's recommended "simpler alternative" and was implemented as specified.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- GET /api/v1/knowledge/search and GET /api/v1/knowledge/{item_id} are live and ready for SDK generation (Plan 07)
- POST /api/v1/outcomes validated and ready to be wired to quality signal table in Plan 03
- OpenAPI spec at /openapi.json includes all REST endpoints with clean operation IDs
- Metering pipeline operational: every authenticated REST request increments request_count

---
*Phase: 03-quality-intelligence-sdks*
*Completed: 2026-02-19*
