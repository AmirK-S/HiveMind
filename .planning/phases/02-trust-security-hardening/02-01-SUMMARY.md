---
phase: 02-trust-security-hardening
plan: 01
subsystem: pipeline
tags: [transformers, deberta, presidio, pii, injection, integrity, sha256, markdown]

# Dependency graph
requires:
  - phase: 01-agent-connection-loop
    provides: PIIPipeline singleton pattern (pii.py) reused for InjectionScanner pattern

provides:
  - InjectionScanner singleton with DeBERTa-v3 prompt injection classification (injection.py)
  - compute_content_hash and verify_content_hash SHA-256 helpers (integrity.py)
  - PIIPipeline.strip() with two-pass PII validation and markdown-aware code block preservation

affects:
  - 02-05 (MCP tools wiring — injection scanner + integrity verification integrate here)
  - 02-06 (any plan wiring add_knowledge.py must call InjectionScanner before PII strip)

# Tech tracking
tech-stack:
  added: []  # transformers and torch already installed; no new dependencies
  patterns:
    - "Lazy import singleton: all heavy imports deferred to __init__; module-level import is instant"
    - "UUID placeholder pattern: fenced code blocks replaced with __CODE_BLOCK_{hex}__ before NLP analysis"
    - "Two-pass PII validation: Pass 1 standard strip, Pass 2a residual re-strip, Pass 2b verbatim check"
    - "Length-gated verbatim check: only PII values with len >= 4 trigger false-positive-safe replacement"

key-files:
  created:
    - hivemind/pipeline/injection.py
    - hivemind/pipeline/integrity.py
  modified:
    - hivemind/pipeline/pii.py

key-decisions:
  - "InjectionScanner.is_injection() returns (bool, float) tuple so callers can log confidence score without re-running model"
  - "Fenced code blocks extracted before inline spans (Pitfall 5): triple-backtick fenced blocks are placeholded first so inline regex never sees them"
  - "Verbatim PII check uses len >= 4 threshold (Pitfall 4): short fragments like single letters cause false positives in natural language"
  - "Narrative-only PII analysis: code blocks are never analyzed or stripped (TRUST-06) — PII inside code is preserved intentionally"

patterns-established:
  - "Singleton with lazy imports: class-level _instance + get_instance() classmethod, all heavy imports inside __init__ only"
  - "Code block extraction order: _FENCED_CODE_RE runs before _INLINE_CODE_RE to avoid nested backtick edge cases"
  - "Two-pass validation: re-analyze anonymized text (Pass 2a) + verbatim substring check on original PII values (Pass 2b)"

requirements-completed: [TRUST-05, TRUST-06, SEC-01, SEC-02]

# Metrics
duration: 2min
completed: 2026-02-19
---

# Phase 2 Plan 01: Trust & Security Hardening - Pipeline Modules Summary

**DeBERTa-v3 prompt injection scanner singleton, SHA-256 integrity helpers, and two-pass markdown-aware PII stripping with UUID code block preservation**

## Performance

- **Duration:** ~2 min
- **Started:** 2026-02-19T03:29:44Z
- **Completed:** 2026-02-19T03:31:48Z
- **Tasks:** 2 of 2
- **Files modified:** 3

## Accomplishments

- Created `InjectionScanner` singleton using `ProtectAI/deberta-v3-base-prompt-injection-v2` via transformers pipeline. All heavy imports deferred to `__init__` following the established PIIPipeline lazy-import pattern. `is_injection()` returns `(bool, float)` so callers get both the reject decision and the confidence score.
- Created `compute_content_hash()` and `verify_content_hash()` using stdlib `hashlib.sha256` — zero new dependencies. Designed for retrieval-time tamper detection (hash stored at insert time in Phase 1; verified at fetch time in Phase 2).
- Extended `PIIPipeline.strip()` with TRUST-05 two-pass validation and TRUST-06 markdown-aware code block preservation. Fenced and inline code blocks are extracted to UUID placeholders before any NLP analysis and reinjected intact after — PII inside code is never stripped.

## Task Commits

Each task was committed atomically:

1. **Task 1: Create prompt injection scanner and content integrity modules** - `7a51a46` (feat)
2. **Task 2: Extend PII pipeline with two-pass validation and markdown-aware code block preservation** - `8b9983e` (feat)

**Plan metadata:** (docs commit — see below)

## Files Created/Modified

- `hivemind/pipeline/injection.py` - InjectionScanner singleton with DeBERTa-v3 text-classification pipeline, `_MAX_INPUT_CHARS = 2000` OOM guard, `is_injection(text, threshold) -> (bool, float)` (SEC-01)
- `hivemind/pipeline/integrity.py` - `compute_content_hash(content) -> str` and `verify_content_hash(content, stored_hash) -> bool` using stdlib hashlib only (SEC-02)
- `hivemind/pipeline/pii.py` - Added `_FENCED_CODE_RE`, `_INLINE_CODE_RE`, `_extract_code_blocks()`, `_reinject_code_blocks()`, `import uuid`; rewrote `strip()` with two-pass validation + code block preservation (TRUST-05, TRUST-06)

## Decisions Made

- `is_injection()` returns `(bool, float)` instead of just `bool` — callers in MCP tools (Plan 05) can log the confidence score for audit trails without re-running the model.
- Fenced code block regex applied before inline regex (Pitfall 5 from research): avoids the edge case where triple-backtick markers are matched by the inline single-backtick pattern.
- Verbatim PII check threshold is `len(pii_value) >= 4` (Pitfall 4 from research): single-character or very short PII fragments cause false positives replacing common words; 4 characters is the minimum meaningful PII length.
- Narrative-only PII analysis: only the non-code text is analyzed (TRUST-06). PII inside code blocks is intentionally preserved — stripping an email from inside a code example would corrupt the code.

## Deviations from Plan

None — plan executed exactly as written. All implementation details followed the PLAN.md action spec and Phase 2 research patterns.

## Issues Encountered

None.

## User Setup Required

None — no external service configuration required. The DeBERTa model (`ProtectAI/deberta-v3-base-prompt-injection-v2`) will be auto-downloaded from Hugging Face on first `InjectionScanner.get_instance()` call (typically in server `lifespan()`).

## Next Phase Readiness

- `InjectionScanner`, `compute_content_hash`, `verify_content_hash`, `_extract_code_blocks`, `_reinject_code_blocks` are all importable and testable in isolation.
- Ready for Plan 02 wiring — no blockers.
- Plan 05 will wire `InjectionScanner.get_instance().is_injection()` into `add_knowledge` tool before PII stripping.
- Plan 05 will wire `verify_content_hash()` into `fetch_by_id` path for tamper detection.

---
*Phase: 02-trust-security-hardening*
*Completed: 2026-02-19*
