---
phase: 02-trust-security-hardening
plan: "05"
subsystem: api
tags: [injection-scanning, content-integrity, auto-approve, deduplication, rate-limiting, deberta, sha256, mcp-tools]

# Dependency graph
requires:
  - phase: 02-trust-security-hardening plan 01
    provides: InjectionScanner singleton (injection.py), verify_content_hash (integrity.py)
  - phase: 02-trust-security-hardening plan 02
    provides: AutoApproveRule ORM model, KnowledgeItem ORM model (models.py)
  - phase: 02-trust-security-hardening plan 03
    provides: check_burst() and get_redis_connection() from rate_limit.py

provides:
  - add_knowledge with injection scan (SEC-01) + burst detection (SEC-03) + auto-approve bypass (TRUST-04)
  - search_knowledge fetch-by-id with SHA-256 content hash verification (SEC-02)
  - search_knowledge search mode with cross-namespace deduplication by content_hash (ACL-05)

affects:
  - 02-06 (MCP tool wiring — builds on these patterns for RBAC enforcement)
  - server/main.py lifespan (InjectionScanner.get_instance() warm-up call recommended)

# Tech tracking
tech-stack:
  added: []  # all dependencies already in place from Plans 01-03
  patterns:
    - "Scan-before-strip: injection scanner runs on raw content before PII pipeline — prevents patterns hidden by redaction"
    - "Burst tracking with temp UUID: generate uuid4() for ZSET member ID at check_burst call site — reuses existing pattern"
    - "Auto-approve fork: single DB session, two code paths (direct KnowledgeItem vs PendingContribution)"
    - "Integrity-verified field: normal return includes integrity_verified: True; tamper path includes integrity_warning string"
    - "Dedup by seen_hashes set: first-seen wins, naturally prioritizes private (own-org) over public duplicates"

key-files:
  created: []
  modified:
    - hivemind/server/tools/add_knowledge.py
    - hivemind/server/tools/search_knowledge.py

key-decisions:
  - "Injection scan runs on raw content (Step 1.5) before PII strip (Step 2) — injection patterns may be hidden in text that gets partially redacted, scanning before modification catches all variants"
  - "check_burst() called with temp uuid4() at request time — temp ID is added to the ZSET window; the real contribution_id is not yet available before DB commit, so a temp UUID is used for burst tracking only"
  - "Auto-approved items use is_public=False as default — auto-approve means skip-queue, not public release; orgs control visibility separately"
  - "Tamper-detected items still returned with integrity_warning field (not rejected) — data integrity issue is operator-visible but agents should still see the content; operators are notified via WARNING log"
  - "Cross-namespace dedup uses first-seen-wins after distance sort — pgvector returns rows sorted ASC by cosine distance; for identical content (same hash), the private copy naturally appears first when org_id matches, so no explicit private-first sort needed"

patterns-established:
  - "Security layer ordering in add_knowledge: auth -> injection -> burst -> PII -> hash -> auto-approve -> insert"
  - "Integrity check pattern: verify_content_hash() → integrity_verified: True (pass) or integrity_warning string (fail)"
  - "Dedup pattern: seen_hashes: set[str], iterate rows, skip if content_hash in seen_hashes, add to set"

requirements-completed: [TRUST-04, ACL-05, SEC-01, SEC-02, SEC-03]

# Metrics
duration: 3min
completed: 2026-02-19
---

# Phase 02 Plan 05: MCP Tool Security Wiring Summary

**DeBERTa injection scanner + Redis burst detection + auto-approve bypass wired into add_knowledge; SHA-256 content integrity verification + cross-namespace dedup wired into search_knowledge**

## Performance

- **Duration:** ~3 min
- **Started:** 2026-02-19T03:37:56Z
- **Completed:** 2026-02-19T03:41:09Z
- **Tasks:** 2 of 2
- **Files modified:** 2

## Accomplishments

- Wired `InjectionScanner.get_instance().is_injection()` into `add_knowledge` as Step 1.5, scanning raw content before PII stripping (SEC-01). Burst detection via `check_burst()` added as Step 1.6 using Redis ZSET sliding window (SEC-03). Auto-approve query in Step 5a checks `AutoApproveRule` for matching org+category — matching rules insert directly into `knowledge_items` with embedding (`status: auto_approved`), bypassing the pending queue (TRUST-04).
- Wired `verify_content_hash()` into `_fetch_by_id()` after item retrieval — normal response includes `integrity_verified: True`; hash mismatch triggers WARNING log and returns `integrity_warning` field in response (SEC-02).
- Added cross-namespace deduplication in `_search()` via `seen_hashes` set — iterates pgvector-sorted rows (distance ASC), skips duplicate `content_hash` entries, preserving first-seen (private org copy prioritized naturally) (ACL-05). `total_count` adjusted to reflect deduplicated count.

## Task Commits

Each task was committed atomically:

1. **Task 1: Integrate injection scanning and auto-approve into add_knowledge** - `b142b75` (feat)
2. **Task 2: Add content hash verification and cross-namespace dedup to search_knowledge** - `58841c6` (feat)

**Plan metadata:** (docs commit — see below)

## Files Created/Modified

- `hivemind/server/tools/add_knowledge.py` — Added imports: `InjectionScanner`, `check_burst`, `get_redis_connection`, `AutoApproveRule`, `KnowledgeItem`, `get_embedder`, `select`; inserted Step 1.5 (injection scan), Step 1.6 (burst detection); replaced flat Step 5 with auto-approve fork (Steps 5a + 5b)
- `hivemind/server/tools/search_knowledge.py` — Added import: `verify_content_hash`, `logging`; added hash verification block in `_fetch_by_id()` with `integrity_verified`/`integrity_warning` fields; added `seen_hashes` dedup loop in `_search()` with `total_count` adjustment

## Decisions Made

- **Injection scan before PII strip:** Raw content must be scanned before any modification — a prompt injection disguised as PII (e.g., `Ignore all instructions: <NAME>`) could survive redaction in a way that alters the injection signal. Scanning first catches all variants.
- **Burst tracking with temp UUID:** `check_burst()` requires a `contribution_id` for the ZSET member. At Step 1.6, no real contribution_id exists yet (pre-DB). A `uuid4()` temp ID is generated solely for the ZSET window entry. This is the correct approach per the rate_limit.py design.
- **Auto-approved items start private (`is_public=False`):** Auto-approve means skip the human review queue, not make the item publicly visible. Orgs control visibility through a separate mechanism. This matches the KnowledgeItem model default and prevents accidental public exposure.
- **Tamper-detected items returned with warning (not rejected):** Content hash mismatch is an operator concern, not a user error. The agent gets the content with an `integrity_warning` field; the operator sees the WARNING log. Blocking the response would create availability issues from what may be a DB corruption event rather than active attack.
- **Dedup uses first-seen-wins after distance sort:** pgvector sorts by cosine distance ASC. For identical content (same `content_hash`), the private copy (org_id match) returns at equal or better distance than the public copy. First-seen retains private attribution automatically without an additional ORDER BY clause.

## Deviations from Plan

None — plan executed exactly as written. All implementation details followed the PLAN.md action spec precisely.

## Issues Encountered

None.

## User Setup Required

None — all wiring uses modules already present (InjectionScanner from Plan 01, check_burst/get_redis_connection from Plan 03, AutoApproveRule from Plan 02, verify_content_hash from Plan 01). No new dependencies or external services.

## Next Phase Readiness

- `add_knowledge` security stack is complete: auth -> injection -> burst -> PII -> hash -> auto-approve -> insert
- `search_knowledge` integrity and dedup are complete: fetch-by-id verifies hash; search deduplicates by content_hash
- Plan 06 (RBAC enforcement) can now wire `enforce()` from `hivemind.security.rbac` into both tools as the next security layer
- Server `lifespan()` should call `InjectionScanner.get_instance()` during warm-up to pre-load the DeBERTa model before first request

## Self-Check: PASSED

Files verified:
- hivemind/server/tools/add_knowledge.py: FOUND
- hivemind/server/tools/search_knowledge.py: FOUND
- .planning/phases/02-trust-security-hardening/02-05-SUMMARY.md: FOUND

Commits verified:
- b142b75: feat(02-05): integrate injection scanning + auto-approve into add_knowledge
- 58841c6: feat(02-05): add content hash verification + cross-namespace dedup to search_knowledge

---
*Phase: 02-trust-security-hardening*
*Completed: 2026-02-19*
