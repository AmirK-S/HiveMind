---
phase: 02-trust-security-hardening
plan: "02"
subsystem: database
tags: [sqlalchemy, alembic, postgresql, api-keys, webhooks, auto-approve, redis, falkordb]

# Dependency graph
requires:
  - phase: 02-trust-security-hardening plan 01
    provides: Phase 2 planning and research context for schema requirements

provides:
  - ApiKey ORM model with SHA-256 hashed key storage, tier support, and billing-period tracking
  - AutoApproveRule ORM model with per-org, per-category auto-approval config
  - WebhookEndpoint ORM model with JSONB event_types and soft-disable support
  - Alembic migrations 003-005 extending revision chain from 002 to 005
  - Settings fields: redis_url, burst_threshold, burst_window_seconds, falkordb_*, injection_threshold

affects:
  - 02-03 (RBAC/Casbin setup uses models.py Base)
  - 02-04 (API key auth middleware reads ApiKey table)
  - 02-05 (rate limiting reads burst_threshold/burst_window_seconds from settings)
  - 02-06 (webhook delivery reads WebhookEndpoint table)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "SHA-256 key hashing pattern: raw key never stored, only prefix (8 chars) + hash (64 chars)"
    - "create_type=False pattern for referencing existing PostgreSQL enums in later migrations"
    - "Settings extension pattern: add new fields after max_search_limit with clear section comments"

key-files:
  created:
    - alembic/versions/003_api_keys.py
    - alembic/versions/004_auto_approve_rules.py
    - alembic/versions/005_webhook_endpoints.py
  modified:
    - hivemind/db/models.py
    - hivemind/config.py

key-decisions:
  - "create_type=False used in 004_auto_approve_rules to reference existing knowledgecategory enum — prevents duplicate type creation error on upgrade"
  - "ix_api_keys_key_hash created as both a unique constraint (uq_api_keys_key_hash) and an explicit index — the constraint enforces uniqueness while the index name provides a stable reference for future migrations"
  - "WebhookEndpoint.event_types stored as JSONB (not a separate table) — subscription lists are small and rarely queried relationally; JSONB avoids a join table for this phase"

patterns-established:
  - "New Phase 2 models follow same mapped_column pattern with nullable=False, explicit defaults"
  - "Alembic migrations include docstring header listing tables/columns/indexes and design notes"

requirements-completed: [TRUST-04, INFRA-04, INFRA-03, SEC-03]

# Metrics
duration: 2min
completed: 2026-02-19
---

# Phase 02 Plan 02: Schema Foundation Summary

**ApiKey, AutoApproveRule, and WebhookEndpoint ORM models with three Alembic migrations extending the revision chain to 005, plus Redis/FalkorDB/rate-limiting settings in Settings class**

## Performance

- **Duration:** 2 min
- **Started:** 2026-02-19T03:29:42Z
- **Completed:** 2026-02-19T03:31:45Z
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments

- Three new ORM models providing the schema foundation for all Phase 2 features
- Alembic migration chain extended: `None -> 001 -> 002 -> 003 -> 004 -> 005` — all verified intact
- Settings class extended with redis_url, burst_threshold/window (SEC-03), falkordb_* (INFRA-02), and injection_threshold (SEC-01)

## Task Commits

Each task was committed atomically:

1. **Task 1: Add new ORM models and extend config settings** - `516484e` (feat)
2. **Task 2: Create Alembic migrations for new tables** - `81e78e1` (feat)

**Plan metadata:** `(pending docs commit)` (docs: complete plan)

## Files Created/Modified

- `hivemind/db/models.py` — added ApiKey, AutoApproveRule, WebhookEndpoint ORM models; added Integer to imports
- `hivemind/config.py` — added redis_url, burst_threshold, burst_window_seconds, falkordb_host/port/database, injection_threshold
- `alembic/versions/003_api_keys.py` — creates api_keys table with key_hash unique constraint and org_id/key_hash indexes
- `alembic/versions/004_auto_approve_rules.py` — creates auto_approve_rules table referencing existing knowledgecategory enum with create_type=False
- `alembic/versions/005_webhook_endpoints.py` — creates webhook_endpoints table with JSONB event_types and org_id index

## Decisions Made

- `create_type=False` used in migration 004 to reference the existing `knowledgecategory` PostgreSQL enum created by migration 001. Without this, Alembic would attempt to CREATE TYPE knowledgecategory and fail with "type already exists".
- `ApiKey.key_hash` has both a `UniqueConstraint` (enforces uniqueness at DB level) and an explicit `Index` (provides a stable named index for future DDL operations).
- `WebhookEndpoint.event_types` stored as JSONB rather than a separate join table — subscription lists are small and don't require relational queries in Phase 2 scope.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

- `python` command not found on the host (macOS uses `python3`). Resolved by using the project's `.venv/bin/python` interpreter, which has all project dependencies (pgvector, sqlalchemy, pydantic-settings) installed. No code changes required.

## User Setup Required

None - no external service configuration required. The migrations will be applied via `alembic upgrade head` when the database is available.

## Next Phase Readiness

- Schema foundation complete — all three new tables are ready for Phase 2 features
- Plan 03 (RBAC/Casbin) can reference `models.Base` to register casbin_rule table
- Plan 04 (API key auth middleware) can query `ApiKey` model by `key_hash`
- Plan 05 (rate limiting) reads `settings.burst_threshold` and `settings.burst_window_seconds`
- Plan 06 (webhook delivery) queries `WebhookEndpoint` for active endpoints by org

## Self-Check: PASSED

All files verified present:
- hivemind/db/models.py: FOUND
- hivemind/config.py: FOUND
- alembic/versions/003_api_keys.py: FOUND
- alembic/versions/004_auto_approve_rules.py: FOUND
- alembic/versions/005_webhook_endpoints.py: FOUND
- .planning/phases/02-trust-security-hardening/02-02-SUMMARY.md: FOUND

Commits verified:
- 516484e: feat(02-02): add ApiKey, AutoApproveRule, WebhookEndpoint ORM models
- cfd67e0: feat(02-02): add Alembic migrations 003-005

---
*Phase: 02-trust-security-hardening*
*Completed: 2026-02-19*
