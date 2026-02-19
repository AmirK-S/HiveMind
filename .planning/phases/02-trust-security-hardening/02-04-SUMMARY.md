---
phase: 02-trust-security-hardening
plan: 04
subsystem: infra
tags: [graphiti, pgvector, falkordb, celery, redis, webhook, knowledge-store, driver-pattern]

# Dependency graph
requires:
  - phase: 01-agent-connection-loop
    provides: "KnowledgeItem ORM model, get_session(), PgVector cosine search patterns, cli/client.py sync session"
  - phase: 02-trust-security-hardening
    plan: 02
    provides: "WebhookEndpoint model, redis_url + falkordb_* settings in config.py"

provides:
  - "KnowledgeStoreDriver ABC with 7 abstract methods (store, fetch, search, delete, verify_integrity, find_similar, health_check)"
  - "PgVectorDriver — wraps existing async SQLAlchemy patterns behind the ABC"
  - "FalkorDBDriver — scaffold wrapping graphiti-core FalkorDriver, health_check only (Phase 3)"
  - "get_driver() factory selecting pgvector or falkordb by name"
  - "KnowledgeNode + SearchResult dataclasses as backend-agnostic data containers"
  - "celery_app with configure_celery() for Redis broker/backend setup"
  - "deliver_webhook Celery task with 3-retry httpx POST"
  - "dispatch_webhooks helper fanning out to active WebhookEndpoints"

affects: [03-graph-intelligence, phase-3-falkordb, approval-flow-integration]

# Tech tracking
tech-stack:
  added: [celery==5.6.2, httpx (already in deps)]
  patterns:
    - "Graphiti GraphDriver pattern adapted to HiveMind knowledge domain"
    - "Backend-agnostic ABC with factory function — get_driver('pgvector'|'falkordb')"
    - "Lazy imports inside class methods for optional heavy dependencies (graphiti-core, falkordb)"
    - "Celery bind=True + self.retry() pattern for retriable tasks"
    - "Fire-and-forget fan-out via deliver_webhook.delay() per endpoint"

key-files:
  created:
    - "hivemind/graph/__init__.py — package marker"
    - "hivemind/graph/driver.py — KnowledgeStoreDriver ABC + PgVectorDriver + FalkorDBDriver + get_driver()"
    - "hivemind/webhooks/__init__.py — package marker"
    - "hivemind/webhooks/tasks.py — celery_app + deliver_webhook task + dispatch_webhooks helper"
  modified: []

key-decisions:
  - "PgVectorDriver wraps existing query patterns from search_knowledge.py and cli/client.py — no query duplication, just ABC-compliant wrappers"
  - "FalkorDBDriver raises NotImplementedError on all methods except health_check — prevents accidental use while scaffolding Phase 3 integration"
  - "Lazy imports used for graphiti_core.driver.falkordb_driver — FalkorDB is an optional dependency, lazy import prevents ImportError if not installed"
  - "Celery installed via pip install into venv — was missing despite being in pyproject.toml dependencies (not yet pip-installed in dev environment)"
  - "dispatch_webhooks uses sync SessionFactory (cli pattern) not async session — called from sync CLI approval flow"

patterns-established:
  - "Knowledge store operations always go through KnowledgeStoreDriver interface — callers never import PgVectorDriver directly"
  - "Webhook fan-out: dispatch_webhooks queries active endpoints, filters by event_types subscription, then enqueues per-endpoint Celery tasks"
  - "Celery configure_celery() called at server lifespan — broker not hardcoded in module"

requirements-completed: [INFRA-02, INFRA-03]

# Metrics
duration: 3min
completed: 2026-02-19
---

# Phase 02 Plan 04: Knowledge Store Driver + Webhook Infrastructure Summary

**KnowledgeStoreDriver ABC (Graphiti pattern, 7 methods) + PgVectorDriver wrapping existing pgvector queries + FalkorDB scaffold + Celery deliver_webhook task with retry + dispatch_webhooks fan-out helper**

## Performance

- **Duration:** ~3 min
- **Started:** 2026-02-19T03:30:34Z
- **Completed:** 2026-02-19T03:33:34Z
- **Tasks:** 2
- **Files modified:** 4 created, 0 modified

## Accomplishments

- KnowledgeStoreDriver ABC establishes a backend-agnostic interface following Graphiti's GraphDriver pattern, consolidating the search/fetch/delete/find-similar operations that were previously scattered across search_knowledge.py and cli/client.py
- PgVectorDriver wraps all existing SQLAlchemy async query patterns behind the ABC with correct org isolation (ACL-01), soft-delete handling, and cosine distance search
- FalkorDBDriver scaffold wraps graphiti-core's FalkorDriver — ready for Phase 3 full implementation, health_check is the only live method
- Celery webhook delivery infrastructure enables near-real-time push notifications to external consumers on knowledge approval events, with 3-retry fault tolerance per endpoint

## Task Commits

Each task was committed atomically:

1. **Task 1: KnowledgeStoreDriver abstraction with PgVector + FalkorDB implementations** — `8b9983e` (feat)
2. **Task 2: Celery webhook delivery infrastructure** — `18fbec6` (feat)

**Plan metadata:** (created next)

## Files Created/Modified

- `hivemind/graph/__init__.py` — Package marker for graph module
- `hivemind/graph/driver.py` — KnowledgeStoreDriver ABC (7 abstract methods), PgVectorDriver implementation, FalkorDBDriver scaffold, KnowledgeNode/SearchResult dataclasses, get_driver() factory
- `hivemind/webhooks/__init__.py` — Package marker for webhooks module
- `hivemind/webhooks/tasks.py` — Celery app, configure_celery(), deliver_webhook task (3 retries, 5s delay), dispatch_webhooks fan-out helper

## Decisions Made

- PgVectorDriver wraps existing query patterns from search_knowledge.py and cli/client.py without duplicating logic — ABC-compliant wrappers that call the same underlying SQLAlchemy operations
- FalkorDBDriver raises NotImplementedError on all methods except health_check — prevents accidental use while reserving the scaffold for Phase 3 graph intelligence
- Lazy imports for graphiti_core inside FalkorDBDriver — optional dependency that may not be installed; lazy import prevents ImportError when using PgVectorDriver
- dispatch_webhooks uses sync SessionFactory (cli/client.py pattern) not async session — it's called from the synchronous CLI approval flow

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Installed celery package missing from venv**
- **Found during:** Task 2 (Celery webhook delivery infrastructure)
- **Issue:** `celery` listed in pyproject.toml dependencies but not installed in the development venv — `from celery import Celery` raised ModuleNotFoundError
- **Fix:** Ran `.venv/bin/pip install celery httpx` — celery 5.6.2 installed successfully
- **Files modified:** None (pip install only)
- **Verification:** `from hivemind.webhooks.tasks import celery_app` succeeded, celery_app.main == "hivemind"
- **Committed in:** 18fbec6 (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (1 blocking)
**Impact on plan:** Necessary installation of declared dependency missing from dev environment. No scope creep.

## Issues Encountered

None beyond the missing celery package (handled as Rule 3 auto-fix above).

## User Setup Required

None — no external service configuration required for these modules. Celery workers require Redis at runtime (configured via `HIVEMIND_REDIS_URL`), but this is covered by Phase 2 infrastructure setup.

## Next Phase Readiness

- KnowledgeStoreDriver ready for use by any Phase 2 plan that needs backend-agnostic knowledge access
- dispatch_webhooks ready to be called from cli/client.py approve_contribution() after Phase 2 webhook endpoint management is complete (02-05 or 02-06)
- FalkorDB scaffold in place for Phase 3 graph intelligence work — no refactoring needed to fill in the NotImplementedError methods

---
*Phase: 02-trust-security-hardening*
*Completed: 2026-02-19*
