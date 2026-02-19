---
phase: 04-dashboard-distribution
plan: "01"
subsystem: api
tags: [fastapi, sse, asyncpg, postgresql, listen-notify, streaming, contributions, statistics, dashboard]

# Dependency graph
requires:
  - phase: 01-agent-connection-loop
    provides: PendingContribution, KnowledgeItem ORM models and embedding pipeline
  - phase: 02-trust-security-hardening
    provides: require_api_key auth dependency, ApiKey model, dispatch_webhooks
  - phase: 03-quality-intelligence-sdks
    provides: quality_score field, QualitySignal model, retrieval_count, helpful_count
provides:
  - SSE streaming endpoint GET /api/v1/stream/feed with PostgreSQL LISTEN/NOTIFY
  - Contribution approval endpoint POST /api/v1/contributions/{id}/approve
  - Contribution rejection endpoint POST /api/v1/contributions/{id}/reject
  - Pending contributions list endpoint GET /api/v1/contributions
  - Commons health stats endpoint GET /api/v1/stats/commons
  - Org reciprocity stats endpoint GET /api/v1/stats/org
  - Per-agent stats endpoint GET /api/v1/stats/user
  - notify_knowledge_published() helper for pg_notify after approval
affects:
  - 04-02-dashboard-frontend
  - 04-03-analytics-ui
  - 04-04-distribution

# Tech tracking
tech-stack:
  added:
    - sse-starlette>=3.2.0 (SSE streaming with EventSourceResponse)
    - asyncpg direct connection for LISTEN/NOTIFY (separate from SQLAlchemy pool)
  patterns:
    - Dedicated asyncpg connection for LISTEN/NOTIFY (not SQLAlchemy pool) — LISTEN requires persistent idle connection
    - asyncio.Queue bridges asyncpg listener callback to async generator
    - 30s timeout on queue.get() with ping yield on timeout for keepalive
    - 404-not-403 pattern for cross-org access (prevents org discovery)
    - dispatch_webhooks called via run_in_executor from async context (sync Celery task)

key-files:
  created:
    - hivemind/api/routes/stream.py
    - hivemind/api/routes/contributions.py
    - hivemind/api/routes/stats.py
  modified:
    - hivemind/api/router.py
    - pyproject.toml

key-decisions:
  - "Dedicated asyncpg connection for LISTEN/NOTIFY — SQLAlchemy pool connections are transactional and not suitable for persistent LISTEN state"
  - "notify_knowledge_published uses SQLAlchemy text() with pg_notify — called within the same session after commit for consistency"
  - "dispatch_webhooks called via asyncio.get_event_loop().run_in_executor() from async approve endpoint — dispatch_webhooks is synchronous (uses sync SessionFactory)"
  - "PendingContribution has no title field — first 80 chars of content used as display title in list view and NOTIFY payload"
  - "quality_score=0.5 neutral prior set on KnowledgeItem at approval time — matches CLI approval flow"
  - "SSE private events check item_org_id == org_id — silently skips events for other orgs without error"

patterns-established:
  - "Pattern: Dedicated asyncpg connection (not pool) for PostgreSQL LISTEN/NOTIFY in SSE endpoints"
  - "Pattern: asyncio.Queue as bridge from asyncpg listener callback to async SSE generator"
  - "Pattern: 25s ping interval + 30s queue timeout for SSE keepalive through proxy timeouts"

requirements-completed: [DASH-01, DASH-03, DASH-05, DASH-06]

# Metrics
duration: 5min
completed: 2026-02-19
---

# Phase 4 Plan 01: Dashboard API Endpoints Summary

**Three FastAPI route modules for SSE streaming, contribution approval/rejection, and commons/org/user stats — wiring the REST API layer for the dashboard frontend**

## Performance

- **Duration:** 5 min
- **Started:** 2026-02-19T13:35:05Z
- **Completed:** 2026-02-19T13:40:13Z
- **Tasks:** 3
- **Files modified:** 5

## Accomplishments
- SSE endpoint at GET /api/v1/stream/feed using PostgreSQL LISTEN/NOTIFY with dedicated asyncpg connection, 25s keepalive ping, and org-scoped private event isolation
- Contribution approval/rejection endpoints that mirror CLI approval flow: embedding generation, KnowledgeItem creation, NOTIFY trigger, and Celery webhook dispatch
- Three statistics endpoints covering commons health metrics, org-level reciprocity, and per-agent contribution tracking using existing DB columns
- All five sub-routers (knowledge, outcomes, stream, contributions, stats) registered in api_router

## Task Commits

Each task was committed atomically:

1. **Task 1: SSE stream endpoint with PostgreSQL LISTEN/NOTIFY** - `291a6c9` (feat)
2. **Task 2: Contribution approve/reject REST endpoints** - `878657e` (feat)
3. **Task 3: Statistics endpoints + router wiring** - `deaa950` (feat)

## Files Created/Modified
- `hivemind/api/routes/stream.py` — SSE feed endpoint with asyncpg LISTEN/NOTIFY, EventSourceResponse, and notify_knowledge_published() helper
- `hivemind/api/routes/contributions.py` — GET /contributions list, POST /approve, POST /reject with embedding + webhook dispatch
- `hivemind/api/routes/stats.py` — GET /stats/commons (global), /stats/org (reciprocity), /stats/user (per-agent)
- `hivemind/api/router.py` — Updated to include stream_router, contributions_router, stats_router (5 sub-routers total)
- `pyproject.toml` — Added sse-starlette>=3.2.0 dependency

## Decisions Made
- Dedicated asyncpg connection for LISTEN/NOTIFY (not SQLAlchemy pool) — LISTEN requires a persistent idle connection, SQLAlchemy pool connections are transactional
- `notify_knowledge_published()` implemented as a standalone async function using SQLAlchemy `text("SELECT pg_notify(...)")` — called within the approval session after item commit
- `dispatch_webhooks` is synchronous (uses sync SessionFactory from cli/client.py) — called via `asyncio.get_event_loop().run_in_executor()` from the async approve/reject endpoints to avoid blocking the event loop
- `PendingContribution` has no `title` field — first 80 characters of `content` used as display title in list view and NOTIFY payload
- `is_public=False` on newly approved items — matches CLI approval behavior; orgs use publish_knowledge tool to make items public

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] dispatch_webhooks called via run_in_executor from async context**
- **Found during:** Task 2 (approve endpoint implementation)
- **Issue:** Plan says `dispatch_webhooks(org_id, "knowledge.approved", item_data)` but the actual function signature is `dispatch_webhooks(org_id, event, knowledge_item_id, category)`. Additionally, dispatch_webhooks is synchronous (uses sync SessionFactory) and would block the async event loop if called directly.
- **Fix:** Adapted call to match actual API signature; wrapped in `asyncio.get_event_loop().run_in_executor(None, lambda: dispatch_webhooks(...))` to avoid blocking the async request handler.
- **Files modified:** hivemind/api/routes/contributions.py
- **Verification:** Import succeeds, function signatures match
- **Committed in:** 878657e (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (1 bug — API signature mismatch + sync/async context fix)
**Impact on plan:** Fix required for correct operation. No scope creep — identical semantic behavior to plan intent.

## Issues Encountered
None beyond the dispatch_webhooks signature adaptation documented above.

## User Setup Required
None - no external service configuration required beyond existing database and Redis setup.

## Next Phase Readiness
- All three endpoint groups are ready to be consumed by the dashboard frontend (Plans 04-02 and 04-03)
- SSE feed at /api/v1/stream/feed provides real-time events once PostgreSQL NOTIFY is triggered on approval
- Contribution workflow (list/approve/reject) replaces the CLI review flow for the dashboard
- Stats endpoints provide all data needed for the analytics dashboard
- No blockers for subsequent plans

---
*Phase: 04-dashboard-distribution*
*Completed: 2026-02-19*

## Self-Check: PASSED

- FOUND: hivemind/api/routes/stream.py
- FOUND: hivemind/api/routes/contributions.py
- FOUND: hivemind/api/routes/stats.py
- FOUND: .planning/phases/04-dashboard-distribution/04-01-SUMMARY.md
- FOUND: commit 291a6c9 (Task 1: SSE stream endpoint)
- FOUND: commit 878657e (Task 2: contribution endpoints)
- FOUND: commit deaa950 (Task 3: stats endpoints + router wiring)
