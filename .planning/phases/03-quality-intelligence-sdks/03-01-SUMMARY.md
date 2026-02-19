---
phase: 03-quality-intelligence-sdks
plan: "01"
subsystem: database
tags: [sqlalchemy, alembic, postgresql, quality-scoring, bi-temporal, behavioral-signals]

# Dependency graph
requires:
  - phase: 02-trust-security-hardening
    provides: KnowledgeItem model, approved knowledge_items table, alembic migration chain to 005

provides:
  - quality_score column on knowledge_items (Float, server_default=0.5, neutral prior for new items)
  - retrieval_count, helpful_count, not_helpful_count denormalized counters on knowledge_items
  - bi-temporal columns: valid_at, invalid_at, expired_at (nullable DateTime(tz)) on knowledge_items
  - quality_signals table with item FK, signal_type, agent_id, run_id, metadata
  - QualitySignal ORM model
  - alembic migration 006 chaining from 005
  - compute_quality_score() — float 0-1 from weighted behavioral signals (stdlib-only)
  - record_signal() — inserts behavioral signal, returns signal ID
  - get_signals_for_item() — retrieves all signals for an item as dicts
  - increment_retrieval_count() — atomic SQL UPDATE on retrieval_count
  - Phase 3 config settings: quality_*, distillation_*, minhash_*, llm_provider, llm_model

affects:
  - 03-02-PLAN.md (quality-ranked search uses quality_score)
  - 03-03-PLAN.md (temporal queries use valid_at/invalid_at/expired_at)
  - 03-04-PLAN.md (outcome reporting uses record_signal + increment_retrieval_count)
  - 03-05-PLAN.md (distillation uses distillation_* config thresholds)
  - 03-06-PLAN.md (dedup uses minhash_* config)
  - 03-07-PLAN.md (SDK uses compute_quality_score)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "signal_metadata attr pattern: SQLAlchemy ORM attribute named signal_metadata maps to DB column named metadata via mapped_column('metadata', ...) — avoids collision with DeclarativeBase.metadata"
    - "Atomic counter pattern: sa.update().values(col=col+1) for retrieval_count increments — no ORM read+write round-trip"
    - "Partial index pattern: ix_knowledge_items_quality_score WHERE deleted_at IS NULL — quality-ranked queries touch only active items"
    - "Backfill pattern: op.execute(UPDATE ... SET col = expression) in upgrade() for derived initial values"

key-files:
  created:
    - alembic/versions/006_quality_temporal.py
    - hivemind/quality/__init__.py
    - hivemind/quality/scorer.py
    - hivemind/quality/signals.py
  modified:
    - hivemind/db/models.py
    - hivemind/config.py

key-decisions:
  - "signal_metadata attribute name (not metadata): SQLAlchemy reserves the 'metadata' attribute name on DeclarativeBase — ORM attr renamed to signal_metadata, DB column name kept as 'metadata' via mapped_column('metadata', JSONB)"
  - "Four explicit nullable DateTime(tz) columns for bi-temporal (not TSTZRANGE): SQLAlchemy has known DataError friction with DateTimeTZRange; valid_at/invalid_at/expired_at nullable as NULL is semantically correct for existing items"
  - "Backfill quality_score = LEAST(1.0, confidence * 0.5): items with high agent confidence get a slight head start per research Open Question 5"
  - "Quality weights as config-time settings (not deployment_config): environment variables via Settings class — weight changes require restart, not runtime API call"
  - "tanh(retrieval_count / 50) for popularity: saturates smoothly around 200 retrievals without hard cap"
  - "staleness_half_life_days=90.0 default: knowledge items remain fresh for ~3 months without access before decaying below 0.5"

patterns-established:
  - "Quality scorer is pure function: compute_quality_score() takes only primitive args — no DB calls, no side effects, fully testable offline"
  - "Behavioral signals stored in quality_signals table, not directly on KnowledgeItem: separate table allows audit trail and future aggregation strategies"
  - "Denormalized counters on KnowledgeItem (retrieval_count, helpful_count, not_helpful_count): avoids COUNT(*) on quality_signals at query time for dashboard performance"

requirements-completed: [QI-01, QI-02, KM-05]

# Metrics
duration: 3min
completed: 2026-02-19
---

# Phase 03 Plan 01: Quality Infrastructure — Schema, Scorer, and Signals Summary

**Alembic migration 006 adds quality_score, bi-temporal columns, and quality_signals table to knowledge_items; quality scorer module computes float 0-1 from weighted behavioral signals using stdlib math only**

## Performance

- **Duration:** 3 min
- **Started:** 2026-02-19T12:15:14Z
- **Completed:** 2026-02-19T12:18:49Z
- **Tasks:** 2
- **Files modified:** 6 (2 created, 4 new files)

## Accomplishments

- Alembic migration 006 adds quality_score (default 0.5), 3 denormalized counters, 3 bi-temporal columns, and the quality_signals table — complete data foundation for Phase 3
- compute_quality_score() implements research Pattern 3 formula: 40% usefulness + 25% popularity (tanh) + 20% freshness (exp decay) - 15% contradiction + 10% version bonus; all weights tunable via Settings
- signal recording helpers (record_signal, get_signals_for_item, increment_retrieval_count) provide the behavioral signal ingestion layer for all subsequent Phase 3 plans

## Task Commits

Each task was committed atomically:

1. **Task 1: Schema migration and model updates** - `1c1b016` (feat)
2. **Task 2: Quality scorer module and signal recording helpers** - `1c5f190` (feat)

## Files Created/Modified

- `alembic/versions/006_quality_temporal.py` — Migration adding quality_score, counters, temporal columns, quality_signals table, backfill, and partial index
- `hivemind/db/models.py` — KnowledgeItem extended with quality + temporal columns; QualitySignal ORM model added; ForeignKey imported
- `hivemind/quality/__init__.py` — Module init for quality intelligence package
- `hivemind/quality/scorer.py` — compute_quality_score() with documented formula, all params, clamp to [0,1]
- `hivemind/quality/signals.py` — record_signal(), get_signals_for_item(), increment_retrieval_count() using async get_session() pattern
- `hivemind/config.py` — quality_staleness_half_life_days, quality_weights_*, distillation_*, minhash_*, llm_provider, llm_model

## Decisions Made

- **signal_metadata attribute name:** SQLAlchemy's DeclarativeBase reserves `metadata` as a class attribute. Renamed ORM attribute to `signal_metadata` while keeping the DB column named `metadata` via `mapped_column("metadata", JSONB)`.
- **Four explicit nullable DateTime(tz) columns:** TSTZRANGE avoided — SQLAlchemy has known DataError friction with DateTimeTZRange (multiple GitHub issues). Four explicit columns (valid_at, invalid_at, expired_at + existing contributed_at) are simpler and fully compatible.
- **Backfill formula:** `quality_score = LEAST(1.0, confidence * 0.5)` — per research Open Question 5, high-confidence items get slight head start without exceeding neutral prior territory.
- **Quality weights as Settings fields:** Config-time environment variables, not runtime deployment_config. Consistent with plan guidance — weight changes require server restart, not a DB write.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Renamed ORM attribute metadata -> signal_metadata**
- **Found during:** Task 1 (model update, ORM verification)
- **Issue:** SQLAlchemy raises `InvalidRequestError: Attribute name 'metadata' is reserved when using the Declarative API` — the plan specified `metadata` as the ORM attribute name but it conflicts with DeclarativeBase internals
- **Fix:** Renamed ORM attribute to `signal_metadata`; kept DB column name as `metadata` using `mapped_column("metadata", JSONB)` — no schema change, no migration impact
- **Files modified:** `hivemind/db/models.py`
- **Verification:** `from hivemind.db.models import QualitySignal` imports cleanly; all model tests pass
- **Committed in:** `1c1b016` (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 — SQLAlchemy reserved attribute name collision)
**Impact on plan:** Cosmetic rename only. DB column name is unchanged. No schema or migration impact.

## Issues Encountered

None beyond the metadata attribute collision documented above.

## User Setup Required

None - no external service configuration required for this plan.

## Next Phase Readiness

- quality_score, temporal columns, and quality_signals table provide the complete data foundation for all Phase 3 plans
- compute_quality_score() ready for use by quality-ranked search (03-02) and outcome reporting (03-04)
- record_signal() and increment_retrieval_count() ready for integration into search and MCP tool handlers
- All Phase 3 config settings (quality_weights_*, distillation_*, minhash_*, llm_*) have sensible defaults and are tunable via environment variables
- Migration 006 must be applied to the database before any Phase 3 features go live

---
*Phase: 03-quality-intelligence-sdks*
*Completed: 2026-02-19*
