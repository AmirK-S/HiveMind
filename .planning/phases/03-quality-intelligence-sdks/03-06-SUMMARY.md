---
phase: 03-quality-intelligence-sdks
plan: 06
subsystem: quality
tags: [celery, celery-beat, distillation, dedup, pii, pgvector, cosine-similarity, background-tasks]

# Dependency graph
requires:
  - phase: 03-01
    provides: quality scorer, quality signals model, deployment_config model
  - phase: 03-04
    provides: three-stage dedup pipeline (cosine/MinHash/LLM), conflict resolver

provides:
  - Sleep-time distillation Celery task (hivemind/quality/distillation.py)
  - run_distillation() with threshold check, duplicate merging, contradiction flagging, summary generation, quality pre-screening
  - Celery Beat schedule: distillation every 30 minutes + quality aggregation every 10 minutes
  - PII re-scan on every LLM-generated summary (QI-04 compliance)
  - Provenance links on canonical items and distilled summaries for erasure propagation

affects:
  - 03-07 (SDK clients phase — completes background maintenance loop)
  - Phase 4 (cold-start pre-seeding strategy benefits from distilled summaries)

# Tech tracking
tech-stack:
  added: [celery.schedules.crontab]
  patterns:
    - Threshold-gated periodic task (condition check inside task body, not Beat scheduler)
    - Lazy PIIPipeline import inside Celery task body to avoid loading heavy ML models on worker startup
    - Provenance links in JSONB tags for erasure propagation without schema changes
    - BFS connected-component clustering from pgvector cosine distance pairs

key-files:
  created:
    - hivemind/quality/distillation.py
  modified:
    - hivemind/webhooks/tasks.py

key-decisions:
  - "Celery Beat only supports time-based scheduling — threshold check (pending_count/conflict_count) lives inside task body, not in the Beat schedule definition (Pitfall 6)"
  - "Merged duplicates are expired (expired_at = now()), never deleted — preserves immutable audit trail per KM-05"
  - "Provenance links maintained in two places: canonical item tags (provenance_links: [merged_ids]) and distilled summaries (source_item_ids: [cluster_ids])"
  - "LLM summary generation is non-blocking — if API key absent or call fails, cluster is silently skipped"
  - "PIIPipeline imported lazily inside run_distillation() body — prevents loading spacy/GLiNER model at Celery worker startup"
  - "quality_score = 0.6 for distilled summaries — slightly above neutral 0.5 to reward curated content"
  - "Low-quality pre-screening threshold at 0.2 preliminary score — uses confidence inversion (1 - confidence) as contradiction_rate proxy for pending items with no behavioral history"

patterns-established:
  - "Periodic background task pattern: condition-gated work inside Celery task body, Beat handles only time schedule"
  - "PII re-scan pattern: every LLM-generated text output must pass through PIIPipeline.get_instance().strip() before storage"

requirements-completed: [QI-04, QI-05]

# Metrics
duration: 4min
completed: 2026-02-19
---

# Phase 3 Plan 06: Sleep-time Distillation Summary

**Celery Beat distillation task merging duplicates, flagging contradictions, generating PII-scanned summaries, and pre-screening quality for the review queue every 30 minutes**

## Performance

- **Duration:** ~4 min
- **Started:** 2026-02-19T12:31:22Z
- **Completed:** 2026-02-19T12:35:00Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments

- Implemented full sleep-time distillation pipeline with 5 stages: threshold check, duplicate merging, contradiction flagging, summary generation, quality pre-screening
- All LLM-generated summaries mandatorily scanned through PIIPipeline before storage (QI-04 compliance)
- Provenance links maintained in JSONB tags enabling erasure propagation without schema changes
- Celery Beat schedule registered with both 30-minute distillation and 10-minute quality aggregation entries

## Task Commits

Each task was committed atomically:

1. **Task 1: Sleep-time distillation task with duplicate merging and summary generation** - `306cc94` (feat)
2. **Task 2: Celery Beat schedule and distillation task registration** - `8eba1b8` (feat)

**Plan metadata:** (docs commit — see below)

## Files Created/Modified

- `hivemind/quality/distillation.py` — Main distillation function: threshold check, duplicate merging (expired_at), contradiction clustering, LLM summary generation + PII re-scan, quality pre-screening, last-run timestamp update
- `hivemind/webhooks/tasks.py` — Added run_distillation_task() Celery task (hivemind.distill); updated configure_celery() with Celery Beat schedule (distillation-every-30m + quality-signal-aggregation)

## Decisions Made

- Celery Beat threshold check lives inside task body — Beat only supports time-based scheduling; condition gates must be task-internal (research Pitfall 6)
- Duplicates expired via `expired_at = now()` not deleted — preserves immutable audit trail per KM-05 constraint
- Provenance links stored as JSONB tags (`provenance_links` on canonical items, `source_item_ids` on distilled summaries) — enables erasure propagation without new DB columns
- PIIPipeline imported lazily inside `run_distillation()` body — prevents loading spacy/GLiNER (~400MB) at Celery worker startup
- `quality_score = 0.6` for distilled summaries — above neutral 0.5 to reward curated content, below 0.8 confidence threshold for new contributions
- Low-quality pre-screening uses `1 - confidence` as contradiction_rate proxy for pending items that have no behavioral history yet
- Both Beat schedule entries (distillation + aggregation) included regardless of Plan 05 execution order — idempotent if 05 runs first

## Deviations from Plan

None — plan executed exactly as written.

## Issues Encountered

None — all imports succeeded, Beat schedule verified programmatically, all 7 success criteria confirmed.

## User Setup Required

None — no external service configuration required beyond existing HIVEMIND_ANTHROPIC_API_KEY for LLM summary generation (already established in Plan 04). If key is absent, summary generation degrades gracefully.

## Next Phase Readiness

- Distillation pipeline complete — commons is now self-maintaining
- Plan 07 (SDK clients) is the final plan in Phase 3
- Distilled summaries accumulate with `source_item_ids` provenance for Phase 4 cold-start pre-seeding strategy

---
*Phase: 03-quality-intelligence-sdks*
*Completed: 2026-02-19*
