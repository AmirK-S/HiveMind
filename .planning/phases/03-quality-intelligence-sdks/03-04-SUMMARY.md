---
phase: 03-quality-intelligence-sdks
plan: "04"
subsystem: dedup-conflict
tags: [dedup, minhash, cosine, llm, conflict-resolution, temporal, bi-temporal]

# Dependency graph
requires:
  - phase: 03-quality-intelligence-sdks
    plan: "01"
    provides: "KnowledgeItem with bi-temporal columns (expired_at, invalid_at, valid_at), config settings (minhash_*, llm_*)"

provides:
  - hivemind/dedup/__init__.py — package init
  - hivemind/dedup/cosine_stage.py — find_cosine_candidates() with 0.35 threshold
  - hivemind/dedup/minhash_stage.py — MinHashLSH singleton, insert_into_lsh, find_minhash_candidates, rebuild_lsh_index
  - hivemind/dedup/llm_stage.py — confirm_duplicate_llm() with 10s timeout, graceful skip
  - hivemind/dedup/pipeline.py — run_dedup_pipeline() orchestrating three stages
  - hivemind/conflict/__init__.py — package init
  - hivemind/conflict/resolver.py — resolve_conflict() and apply_conflict_resolution()
  - add_knowledge.py dedup+conflict integration path

affects:
  - 03-05-PLAN.md (distillation can reuse find_cosine_candidates and MinHash index)
  - 03-07-PLAN.md (SDK wraps add_knowledge which now runs dedup)

# Tech tracking
tech-stack:
  added:
    - "datasketch 1.9.0 — MinHash and MinHashLSH for Jaccard similarity near-duplicate detection"
  patterns:
    - "Module-level singleton pattern: _lsh_index initialized lazily on first get_lsh_index() call — avoids per-request rebuild cost"
    - "Lazy import pattern: all stage modules import hivemind.config.settings lazily to avoid circular dependency"
    - "Graceful degradation pattern: LLM stage returns is_duplicate=False with descriptive reason when API key missing or call fails"
    - "Bi-temporal action pattern: UPDATE sets expired_at (system-time end); VERSION_FORK sets invalid_at (world-time end) on existing item"
    - "Non-blocking conflict fallback: resolve_conflict() defaults to ADD on any LLM failure — never blocks contribution flow"

key-files:
  created:
    - hivemind/dedup/__init__.py
    - hivemind/dedup/cosine_stage.py
    - hivemind/dedup/minhash_stage.py
    - hivemind/dedup/llm_stage.py
    - hivemind/dedup/pipeline.py
    - hivemind/conflict/__init__.py
    - hivemind/conflict/resolver.py
  modified:
    - hivemind/server/tools/add_knowledge.py
    - hivemind/config.py
    - pyproject.toml

key-decisions:
  - "anthropic_api_key added to Settings (empty default): LLM stages in both dedup and conflict resolver skip gracefully when key is absent — the pipeline is fully operational without LLM credentials"
  - "datasketch added to pyproject.toml dependencies: MinHash LSH is a hard dependency for Stage 2; no optional import guard needed"
  - "NOOP returns informational response (not isError): NOOP is correct behavior (duplicate detected), not an error — callers can distinguish via status='duplicate_detected'"
  - "VERSION_FORK passes valid_at to new item via _fork_valid_at: world-time fork requires the new item's valid_at to be set at resolution time, not at DB insert time"
  - "FLAGGED_FOR_REVIEW adds 'conflict_flagged' tag to tags list: avoids schema change for a rare edge case — the flag is queryable via tags JSONB, no new column needed"
  - "Dedup integration uses lazy imports inside add_knowledge(): avoids circular dependency between add_knowledge -> dedup.pipeline -> db.session -> (same session context)"

# Metrics
duration: 6min
completed: 2026-02-19
---

# Phase 03 Plan 04: Three-Stage Dedup Pipeline and LLM Conflict Resolution Summary

**Three-stage near-duplicate detection (cosine -> MinHash LSH -> LLM) with four-outcome conflict resolution (UPDATE/ADD/NOOP/VERSION_FORK) integrated into the add_knowledge ingestion flow as a non-blocking pre-insert gate**

## Performance

- **Duration:** 6 min
- **Started:** 2026-02-19T12:22:07Z
- **Completed:** 2026-02-19T12:28:12Z
- **Tasks:** 2
- **Files modified:** 10 (7 created, 3 modified)

## Accomplishments

- Three-stage dedup pipeline: Stage 1 (cosine, reuses embedding pattern from search_knowledge.py) finds top-10 candidates within 0.35 distance threshold; Stage 2 (MinHash LSH singleton) filters to lexical near-duplicates via Jaccard intersection; Stage 3 (LLM) confirms semantic duplicates with 10s timeout and graceful skip
- LLM conflict resolver classifies relationships using structured prompt with four outcome vocabulary: UPDATE (expire old), ADD (coexist), NOOP (block), VERSION_FORK (world-time split via invalid_at/valid_at); multi-hop conflicts flagged for human review
- add_knowledge integrates full dedup+conflict pipeline before DB insert; LLM unavailability never blocks contributions (defaults to ADD throughout)

## Task Commits

Each task was committed atomically:

1. **Task 1: Three-stage dedup pipeline** - `1a1088b` (feat)
2. **Task 2: LLM conflict resolution and add_knowledge integration** - `8302673` (feat)

## Files Created/Modified

- `hivemind/dedup/__init__.py` — Package init for near-duplicate detection module
- `hivemind/dedup/cosine_stage.py` — find_cosine_candidates() — top-K cosine similarity search with 0.35 distance threshold, reuses vector query pattern from search_knowledge.py
- `hivemind/dedup/minhash_stage.py` — get_lsh_index() singleton, minhash_for_text(), insert_into_lsh(), find_minhash_candidates(), rebuild_lsh_index() — datasketch MinHashLSH
- `hivemind/dedup/llm_stage.py` — confirm_duplicate_llm() — Anthropic API with 10s timeout, structured JSON prompt, graceful skip when no API key or call fails
- `hivemind/dedup/pipeline.py` — run_dedup_pipeline() — orchestrates three stages, returns ADD/DUPLICATE with stages_run list and all candidate details
- `hivemind/conflict/__init__.py` — Package init for conflict resolution module
- `hivemind/conflict/resolver.py` — resolve_conflict() with LLM-assisted four-outcome classification; apply_conflict_resolution() executes DB actions (expired_at/invalid_at updates); multi-hop detection via is_direct_conflict flag
- `hivemind/server/tools/add_knowledge.py` — Integrated dedup pipeline and conflict resolution as Steps 5/5a/5b before DB insert; NOOP returns duplicate_detected status; VERSION_FORK sets valid_at on new item; FLAGGED_FOR_REVIEW adds conflict_flagged tag
- `hivemind/config.py` — Added anthropic_api_key setting (empty default = LLM stages skip gracefully, HIVEMIND_ANTHROPIC_API_KEY env var)
- `pyproject.toml` — Added datasketch dependency

## Decisions Made

- **anthropic_api_key as Settings field:** The plan specified `HIVEMIND_ANTHROPIC_API_KEY` env var. Added as `anthropic_api_key: str = ""` in Settings class, consistent with the pydantic-settings pattern used throughout the codebase. Empty default ensures both dedup LLM stage and conflict resolver degrade gracefully.
- **NOOP returns dict (not isError):** Plan specifies returning `{ status: "duplicate_detected", duplicate_of: ..., reason: ... }` — this is informational, not an error. Returning `CallToolResult(isError=True)` would be wrong here.
- **VERSION_FORK valid_at timing:** The fork's world-time start must be captured at resolution time (when apply_conflict_resolution runs) and passed through to the KnowledgeItem insert. `_fork_valid_at` variable threads this timestamp through the function.
- **FLAGGED_FOR_REVIEW stores conflict_flagged tag:** Multi-hop conflicts don't need a new DB column — the tags JSONB field can carry this flag. Avoids a migration for an edge case.

## Deviations from Plan

None - plan executed exactly as written.

The `lsh.h` attribute (not `lsh.threshold`) was noted from the datasketch API (MinHashLSH exposes `h` for num_perm, not `threshold` directly on the object) — this was a verification command detail in the plan, not a deviation.

## Issues Encountered

None beyond the datasketch API attribute inspection (lsh.h vs lsh.threshold).

## User Setup Required

To enable LLM stages (dedup Stage 3 and conflict resolution), set:
```
HIVEMIND_ANTHROPIC_API_KEY=<your-anthropic-api-key>
```

Both stages work without this — they default to non-duplicate / ADD outcomes respectively.

## Next Phase Readiness

- run_dedup_pipeline() is callable by distillation (03-05) to find clusters of near-duplicates for consolidation
- insert_into_lsh() should be called on each approved knowledge item to keep the MinHash index current
- rebuild_lsh_index() available for startup rehydration or after config changes
- conflict resolver ready for use in any future flow that needs UPDATE/VERSION_FORK semantics

## Self-Check: PASSED

All created files verified present on disk. Both task commits (1a1088b, 8302673) verified in git log.

---
*Phase: 03-quality-intelligence-sdks*
*Completed: 2026-02-19*
