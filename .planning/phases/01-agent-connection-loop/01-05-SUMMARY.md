---
phase: 01-agent-connection-loop
plan: "05"
subsystem: cli
tags: [pgvector, cosine-similarity, rich, sqlalchemy, embeddings, trust]

# Dependency graph
requires:
  - phase: 01-04
    provides: CLI review workflow (approve/reject/flag) with sync SQLAlchemy client
  - phase: 01-02
    provides: get_embedder() singleton with normalize_embeddings=True for pgvector
  - phase: 01-03
    provides: cosine_distance query pattern in search_knowledge.py
provides:
  - find_similar_knowledge() in cli/client.py — cosine distance top-N lookup for pending content
  - compute_qi_score() in cli/client.py — confidence + flag + length synthesised into QI badge
  - _build_similar_section() in cli/review.py — Rich-formatted near-duplicate panel section
  - _build_qi_badge() in cli/review.py — Rich-formatted High/Medium/Low quality badge
  - Review panel now surfaces QI badge and similar knowledge for every contribution
affects: [phase-02, phase-03, phase-04]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - cosine_distance reused from search_knowledge.py in sync SessionFactory context
    - Graceful degradation with try/except around embedding calls in interactive CLI
    - QI score synthesis: confidence * 100 with flag/length modifiers, clamped 0-100

key-files:
  created: []
  modified:
    - hivemind/cli/client.py
    - hivemind/cli/review.py

key-decisions:
  - "Cosine distance threshold 0.35 (65% similarity) chosen as 'similar enough to mention' boundary — items above this are near-duplicates worth flagging"
  - "Items >= 80% similarity highlighted yellow in review panel as likely duplicates; items 65-80% shown in dim as related-but-distinct"
  - "find_similar_knowledge() uses try/except in review.py (not in client.py) to keep client pure and review interactive workflow resilient"
  - "QI badge is informational only — never a blocker. Positive tone maintained per design principles"

patterns-established:
  - "Sync cosine search: SessionFactory().execute(select(KnowledgeItem, distance_col).order_by(distance_col.asc()).limit(N))"
  - "Threshold filtering post-query: iterate rows and skip distance > threshold rather than WHERE clause (avoids pgvector index hint issues)"
  - "QI score computation: base = confidence * 100, apply modifiers, clamp [0,100], map to badge dict"

requirements-completed: [TRUST-02]

# Metrics
duration: 3min
completed: 2026-02-18
---

# Phase 01 Plan 05: TRUST-02 Similar Knowledge + QI Pre-screening Summary

**Cosine similarity near-duplicate detection and synthesised QI badge added to CLI review panel, closing TRUST-02 quality signal gap**

## Performance

- **Duration:** ~3 min
- **Started:** 2026-02-18T06:43:43Z
- **Completed:** 2026-02-18T06:46:06Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments

- Added `find_similar_knowledge()` to `hivemind/cli/client.py`: embeds pending content via `get_embedder().embed()`, queries `knowledge_items` with `cosine_distance` (same pattern as `search_knowledge.py`), filters by org + public scope, excludes soft-deleted, returns top-3 items with similarity percentage filtered by 0.35 threshold
- Added `compute_qi_score()` to `hivemind/cli/client.py`: synthesises confidence score, `is_sensitive_flagged`, and content length into a 0-100 QI score with High (green)/Medium (yellow)/Low (red) badge and detail lines
- Updated `hivemind/cli/review.py` with `_build_similar_section()` and `_build_qi_badge()` display helpers; review loop now computes QI badge and fetches similar items before rendering the contribution panel, with graceful fallback if embedding fails

## Task Commits

Each task was committed atomically:

1. **Task 1: Add find_similar_knowledge() and compute_qi_score() to CLI client** - `2095caf` (feat)
2. **Task 2: Display similar knowledge and QI badge in review panel** - `ed14725` (feat)

**Plan metadata:** committed with docs commit below

## Files Created/Modified

- `hivemind/cli/client.py` - Added `find_similar_knowledge()` (cosine similarity query, +82 lines) and `compute_qi_score()` (QI badge synthesis, +50 lines)
- `hivemind/cli/review.py` - Added `_build_similar_section()`, `_build_qi_badge()` helpers and wired both into review loop (+75 lines, -2 lines)

## Decisions Made

- Cosine distance threshold 0.35 chosen for "similar enough to mention" — corresponds to ~65% similarity, a reasonable near-duplicate signal
- Items >= 80% similarity highlighted yellow as likely duplicates; items 65-80% shown dim as related-but-distinct
- try/except wraps `find_similar_knowledge()` in review.py (not in client.py) — keeps client pure and ensures the interactive CLI never crashes due to embedding model unavailability
- QI badge is informational only, not a blocker — maintains the positive, rewarding tone established in 01-04

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None — embedding infrastructure, cosine_distance operator, and sync SessionFactory all worked as expected by reusing the established search_knowledge.py pattern.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- TRUST-02 gap fully closed: review panel surfaces both QI pre-screening signals and similar existing knowledge for every contribution
- Phase 1 (Agent Connection Loop) now complete — all 5 plans executed
- Ready for Phase 2 planning: MCP protocol abstraction layer, French-specific PII recognizers (SIRET/SIREN/NIR), and cold-start pre-seeding strategy

---
*Phase: 01-agent-connection-loop*
*Completed: 2026-02-18*

## Self-Check: PASSED

- hivemind/cli/client.py: FOUND
- hivemind/cli/review.py: FOUND
- .planning/phases/01-agent-connection-loop/01-05-SUMMARY.md: FOUND
- Commit 2095caf (Task 1): FOUND
- Commit ed14725 (Task 2): FOUND
