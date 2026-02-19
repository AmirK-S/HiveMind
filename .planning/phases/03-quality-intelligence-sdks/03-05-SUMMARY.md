---
phase: 03-quality-intelligence-sdks
plan: "05"
subsystem: search-quality
tags: [search, rrf, quality-boosting, celery, signal-aggregation, hybrid-retrieval]
dependency_graph:
  requires: ["03-01", "03-03"]
  provides: ["hybrid-rrf-search", "quality-signal-aggregation"]
  affects: ["search-ranking", "quality-feedback-loop"]
tech_stack:
  added: []
  patterns:
    - "Two-CTE hybrid retrieval (vector + text) fused by RRF in SQL"
    - "Quality-boosted ranking: rrf_score * (0.7 + 0.3 * quality_score)"
    - "Fire-and-forget asyncio.create_task for non-blocking signal recording"
    - "Incremental aggregation (only items with new signals since last_run)"
    - "Sync Celery task pattern with SessionFactory for DB access"
key_files:
  created:
    - hivemind/quality/aggregator.py
  modified:
    - hivemind/server/tools/search_knowledge.py
    - hivemind/webhooks/tasks.py
    - hivemind/server/main.py
decisions:
  - "PostgreSQL native to_tsvector/ts_rank chosen over pg_search/pg_textsearch — avoids OS-level extension installation; RRF pattern identical when pg_search is added later"
  - "Quality boost formula: rrf_score * (0.7 + 0.3 * quality_score) computed in SQL — zero Python post-processing, meets <200ms P95 target"
  - "Fire-and-forget asyncio.create_task for retrieval signal recording — prevents count tracking from blocking search response latency"
  - "Incremental aggregation scoped to items with new signals since last_run — scales with signal volume not total item count"
  - "is_version_current derived from expired_at IS NULL — avoids complex sibling query; expired_at is already set by conflict resolver VERSION_FORK outcome"
metrics:
  duration: "~4 min"
  completed_date: "2026-02-19"
  tasks_completed: 2
  files_modified: 4
---

# Phase 03 Plan 05: Quality-Boosted Hybrid Search and Signal Aggregation Summary

**One-liner:** Hybrid vector+text RRF search with quality_score boosting in SQL, plus incremental Celery-based quality signal aggregation on 10-minute schedule.

## What Was Built

### Task 1: Hybrid Search with RRF and Quality-Boosted Ranking

Upgraded `_search()` in `hivemind/server/tools/search_knowledge.py` from a single cosine-distance query to a two-CTE hybrid approach fused by Reciprocal Rank Fusion (RRF):

**Architecture:**
- **CTE 1 (Vector):** Top 20 candidates ranked by pgvector cosine distance
- **CTE 2 (Text):** Top 20 candidates ranked by PostgreSQL `ts_rank` (native FTS, no extensions)
- **RRF Fusion:** `SUM(1.0 / (60 + rank))` per item across both CTEs, grouped in SQL
- **Quality Boost:** `final_score = rrf_score * (0.7 + 0.3 * quality_score)` applied in SQL
- **Result Shape:** Backward-compatible — `relevance_score` now reflects quality-boosted RRF instead of raw cosine similarity

**Retrieval Count Tracking:**
- `asyncio.create_task(_record_retrieval_signals(returned_ids))` fires after results are built
- Single batch `UPDATE` increments `retrieval_count` for all returned items atomically
- Non-blocking — does not add latency to search response (QI-02 requirement)

**Key files modified:**
- `hivemind/server/tools/search_knowledge.py` — _search(), _record_retrieval_signals()

### Task 2: Quality Signal Aggregation Celery Task with Beat Schedule

Created `hivemind/quality/aggregator.py` with `aggregate_quality_signals()`:

**Aggregation logic:**
1. Reads `quality_aggregation_last_run` from `deployment_config` table (ISO 8601 string)
2. Queries `DISTINCT knowledge_item_id` from `quality_signals WHERE created_at > last_run`
3. For each affected item:
   - Computes `contradiction_rate` from signal type counts
   - Computes `days_since_last_access` from most recent retrieval signal timestamp
   - Determines `is_version_current` from `expired_at IS NULL` (set by VERSION_FORK resolver)
   - Calls `compute_quality_score()` from scorer.py with denormalized counts from KnowledgeItem
   - Updates `KnowledgeItem.quality_score` via batch UPDATE
4. Updates `quality_aggregation_last_run` in deployment_config
5. Returns `{items_updated, run_at}`

**Celery registration:**
- Task registered as `hivemind.aggregate_quality_signals` in `webhooks/tasks.py`
- Celery Beat schedule: `crontab(minute="*/10")` — every 10 minutes
- Uses sync `SessionFactory` (cli pattern) — Celery workers cannot use asyncio

**Key files created/modified:**
- `hivemind/quality/aggregator.py` (new)
- `hivemind/webhooks/tasks.py` — added task registration + Beat schedule already present
- `hivemind/server/main.py` — added log line after Celery configuration

## Deviations from Plan

### Auto-fixed Issues

None beyond minor implementation details.

**Observation:** `webhooks/tasks.py` already contained the `quality-signal-aggregation` Beat schedule entry (added in a previous plan's forward-compatible update) and a `distillation-every-30m` schedule. The missing piece was the actual task registration (`@celery_app.task(name="hivemind.aggregate_quality_signals")`), which was added in this plan.

## Verification Results

All 15 checks passed:
- Hybrid search has RRF, quality_score boosting, to_tsvector, ts_rank, union_all, final_score, 0.7+0.3 formula, asyncio.create_task, and retrieval_count increment
- Aggregator queries new signals since last_run, calls compute_quality_score, updates quality_score, uses deployment_config for timestamp tracking
- Beat schedule is configured with `quality-signal-aggregation` key pointing to `hivemind.aggregate_quality_signals`

## Feedback Loop Closed

```
Agent uses search_knowledge
  -> items returned -> retrieval_count incremented (fire-and-forget)
  -> agent reports outcome via report_outcome tool -> QualitySignal inserted

Celery Beat (every 10 min)
  -> aggregate_quality_signals() triggered
  -> items with new signals since last_run identified
  -> quality_score recomputed via weighted formula
  -> KnowledgeItem.quality_score updated

Next search request
  -> final_score = rrf_score * (0.7 + 0.3 * updated_quality_score)
  -> higher quality items rank above lower-quality items at similar relevance
```

## Commits

| Task | Hash | Description |
|------|------|-------------|
| Task 1 | eaad376 | feat(03-05): hybrid RRF search with quality-boosted ranking |
| Task 2 | 872c8f5 | feat(03-05): quality signal aggregation Celery task with Beat schedule |

## Self-Check: PASSED
