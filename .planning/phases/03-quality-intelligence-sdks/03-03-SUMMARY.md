---
phase: 03-quality-intelligence-sdks
plan: 03
subsystem: api
tags: [mcp, quality-signals, temporal-queries, outcome-reporting, bitemporal, pgvector]

# Dependency graph
requires:
  - phase: 03-01-SUMMARY.md
    provides: quality signal infrastructure (QualitySignal table, record_signal(), helpful_count/not_helpful_count columns)
  - phase: 03-02-SUMMARY.md
    provides: REST API layer at /api/v1/ with X-API-Key auth and outcomes stub endpoint

provides:
  - report_outcome MCP tool (MCP-06): records "solved"/"did_not_help" signals with deduplication by run_id
  - REST POST /api/v1/outcomes wired to real signal recording logic with same deduplication semantics
  - hivemind/temporal/queries.py: build_temporal_filter() and query_at_time() bi-temporal helpers
  - search_knowledge MCP tool extended with at_time and version parameters for point-in-time queries

affects:
  - 03-04 through 03-07 (quality scorer, SDK generation — depends on outcome signals flowing into quality_signals table)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Idempotent outcome recording: deduplication by (item_id, run_id) returns already_recorded status"
    - "Additive temporal filtering: at_time=None preserves exact prior search behavior"
    - "NULL valid_at = always-valid sentinel: backward compatible with pre-temporal-migration items"
    - "Bi-temporal conditions extracted to build_temporal_filter() for reuse across search surfaces"
    - "Atomic counter increment via raw SQL UPDATE (no ORM read+write race condition)"

key-files:
  created:
    - hivemind/server/tools/report_outcome.py
    - hivemind/temporal/__init__.py
    - hivemind/temporal/queries.py
  modified:
    - hivemind/server/main.py
    - hivemind/api/routes/outcomes.py
    - hivemind/server/tools/search_knowledge.py

key-decisions:
  - "Deduplication check scopes to outcome signal types only (outcome_solved, outcome_not_helpful) — retrieval signals are not deduplicated by run_id"
  - "NULL valid_at items always pass temporal filter (OR condition, not AND) — pre-migration items treated as always-valid not always-excluded"
  - "version filter only applied when at_time is also provided — version alone without temporal context would be misleading"
  - "REST endpoint uses getattr() for dynamic counter column reference — avoids hardcoding column attribute names twice"

patterns-established:
  - "build_temporal_filter(at_time) returns list of 3 conditions: unpack into any stmt.where(*conditions)"
  - "Temporal filter is additive to existing search — no existing behavior changes when at_time=None"

requirements-completed: [MCP-06, KM-06]

# Metrics
duration: 4min
completed: 2026-02-19
---

# Phase 3 Plan 03: Outcome Reporting and Temporal Queries Summary

**report_outcome MCP tool with run_id deduplication, REST endpoint wiring, and bi-temporal build_temporal_filter() helpers integrated into search_knowledge**

## Performance

- **Duration:** 4 min
- **Started:** 2026-02-19T12:22:10Z
- **Completed:** 2026-02-19T12:26:57Z
- **Tasks:** 2
- **Files modified:** 5 (3 created, 3 modified)

## Accomplishments

- report_outcome MCP tool records "solved"/"did_not_help" signals, validates org access, deduplicates by run_id, and atomically increments helpful_count/not_helpful_count
- REST POST /api/v1/outcomes replaced placeholder with full signal recording logic (identical semantics to MCP tool)
- build_temporal_filter() returns 3 SQLAlchemy conditions for point-in-time filtering; NULL valid_at treated as always-valid for backward compatibility
- search_knowledge extended with optional at_time (ISO 8601) and version parameters — additive filter, no behavior change when omitted

## Task Commits

Each task was committed atomically:

1. **Task 1: report_outcome MCP tool and REST endpoint wiring** - `f07d823` (feat)
2. **Task 2: Bi-temporal query helpers and search_knowledge temporal filter** - `d4af305` (feat)

**Plan metadata:** (docs commit — see final commit below)

## Files Created/Modified

- `hivemind/server/tools/report_outcome.py` - MCP-06 outcome reporting tool: auth, validation, dedup, signal recording, counter increment
- `hivemind/temporal/__init__.py` - Empty package init for temporal module
- `hivemind/temporal/queries.py` - build_temporal_filter() and query_at_time() bi-temporal helpers
- `hivemind/server/main.py` - Added report_outcome import and registration as 7th MCP tool
- `hivemind/api/routes/outcomes.py` - Replaced placeholder with real signal recording, dedup, counter increment
- `hivemind/server/tools/search_knowledge.py` - Added at_time, version params, temporal filter integration

## Decisions Made

- Deduplication check scopes to outcome signal types only (outcome_solved, outcome_not_helpful) — retrieval signals are not deduplicated by run_id since the same run can legitimately retrieve many items
- NULL valid_at items always pass the temporal filter via OR condition — pre-migration items are treated as always-valid, not always-excluded (this is the backward-compatible choice)
- version filter only meaningful when combined with at_time — applying version alone without a temporal anchor would be ambiguous
- REST endpoint uses getattr() for dynamic counter column resolution — avoids duplicate column attribute references

## Deviations from Plan

None — plan executed exactly as written.

## Issues Encountered

None. The virtual environment needed to be invoked via `.venv/bin/python` (not `python3`) to access project dependencies — this was expected from prior plans.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- Quality signal pipeline fully wired: agents can now call report_outcome() after search_knowledge() to report whether retrieved items helped
- Temporal query infrastructure ready for use by any future search surface
- Plan 04 (quality scorer) can now aggregate outcome_solved/outcome_not_helpful signals from the quality_signals table to compute quality_score evolution

---
*Phase: 03-quality-intelligence-sdks*
*Completed: 2026-02-19*
