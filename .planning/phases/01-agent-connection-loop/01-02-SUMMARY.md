---
phase: 01-agent-connection-loop
plan: "02"
subsystem: pipeline
tags: [presidio, gliner, pii, sentence-transformers, embeddings, nlp]

requires: []

provides:
  - "PIIPipeline singleton: Presidio + GLiNER + 11 custom API key/secret patterns, typed placeholder output, 50% rejection threshold"
  - "EmbeddingProvider ABC with SentenceTransformerProvider (all-MiniLM-L6-v2, 384 dims, cosine-normalized)"
  - "get_embedder() singleton accessor for safe model reuse"
  - "strip_pii() convenience function for any caller"

affects:
  - "01-03-PLAN.md (add_knowledge and search_knowledge tools use both modules)"
  - "01-04-PLAN.md (CLI approval workflow depends on strip_pii being pre-applied)"

tech-stack:
  added:
    - "presidio-analyzer[gliner] — PII detection engine with GLiNER zero-shot NER support"
    - "presidio-anonymizer — PII replacement with typed placeholder operators"
    - "gliner — GLiNER model inference (knowledgator/gliner-pii-base-v1.0)"
    - "sentence-transformers — SentenceTransformer model loading and encoding"
  patterns:
    - "Singleton pattern for expensive ML models (PIIPipeline._instance, _EmbedderSingleton._instance)"
    - "Abstract interface over concrete implementation for embedding providers (EmbeddingProvider ABC)"
    - "Lazy import of settings inside get_embedder() to avoid circular imports"
    - "Post-strip token counting for 50% rejection threshold (not pre-strip)"
    - "normalize_embeddings=True for cosine_distance compatibility with pgvector"

key-files:
  created:
    - "hivemind/pipeline/__init__.py"
    - "hivemind/pipeline/pii.py"
    - "hivemind/pipeline/embedder.py"
  modified: []

key-decisions:
  - "Silent PII stripping: no logging of detected entities, no before/after comparison — user only sees clean version"
  - "50% rejection threshold uses POST-strip token count (not original) to avoid inflation from multi-word -> single-token collapse"
  - "normalize_embeddings=True chosen because pgvector cosine_distance requires unit vectors for equivalence with dot product"
  - "model_revision detected at runtime via HuggingFace hub best-effort, stored in deployment_config for KM-08 drift detection"
  - "Lazy settings import in get_embedder() avoids circular dependency between pipeline and config modules"

patterns-established:
  - "Singleton ML models: class with _instance class variable and get_instance() classmethod — prevents GLiNER 400MB reload per request"
  - "PII strip before any storage: strip_pii() returns (cleaned_text, should_reject) — callers must check should_reject before queuing"
  - "Embedding normalization convention: always normalize_embeddings=True — callers must not renormalize"

requirements-completed:
  - TRUST-01
  - KM-08

duration: 3min
completed: 2026-02-18
---

# Phase 01 Plan 02: PII Pipeline and Embedding Provider Summary

**Presidio + GLiNER + 11 API key pattern PII pipeline with 50% auto-reject, plus SentenceTransformer embedding abstraction with cosine-normalized vectors for pgvector**

## Performance

- **Duration:** 3 min
- **Started:** 2026-02-18T20:59:33Z
- **Completed:** 2026-02-18T21:02:14Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments

- PII stripping pipeline built as singleton: Presidio AnalyzerEngine + GLiNERRecognizer (knowledgator/gliner-pii-base-v1.0) + PatternRecognizer with 11 secret patterns. Typed placeholders ([EMAIL], [PHONE], [NAME], [LOCATION], [API_KEY], [CREDIT_CARD], [IP_ADDRESS], [USERNAME]) plus [REDACTED] fallback. Auto-reject fires when placeholder tokens exceed 50% of post-strip content.
- EmbeddingProvider ABC defined with full interface (embed, embed_batch, model_id, model_revision, dimensions). SentenceTransformerProvider implements it with all-MiniLM-L6-v2, detecting dimensions dynamically and attempting HuggingFace commit hash retrieval for KM-08 deployment pinning.
- Both modules are database-free pure-function modules, importable without starting any service.

## Task Commits

Each task was committed atomically:

1. **Task 1: PII stripping pipeline** - `7dd60ef` (feat)
2. **Task 2: Embedding provider abstraction** - `80f1e3b` (feat)

**Plan metadata:** (see final docs commit)

## Files Created/Modified

- `hivemind/pipeline/__init__.py` - Pipeline package init with module docstring
- `hivemind/pipeline/pii.py` - PIIPipeline singleton (208 lines): Presidio + GLiNER + 11 API key patterns, typed placeholder operators, 50% rejection logic, strip_pii() convenience function
- `hivemind/pipeline/embedder.py` - EmbeddingProvider ABC + SentenceTransformerProvider + get_embedder() singleton (201 lines)

## Decisions Made

- Post-strip token count used for rejection ratio (not pre-strip): multi-word names collapse to single [NAME] token, so pre-strip count would falsely inflate the ratio
- normalize_embeddings=True is mandatory for pgvector cosine_distance correctness — this is enforced at the provider level so no caller can forget it
- Revision detection is best-effort (walks model._modules, falls back to huggingface_hub.model_info) — returns None gracefully if unavailable, deployment_config stores whatever is available

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required. Both modules are pure Python with no network calls at import time. GLiNER model (~400 MB) and sentence-transformers model (~22 MB) will be downloaded by HuggingFace on first PIIPipeline.get_instance() and get_embedder() call respectively.

## Next Phase Readiness

- `hivemind.pipeline.pii.strip_pii()` ready for use in Plan 03 `add_knowledge` MCP tool
- `hivemind.pipeline.embedder.get_embedder()` ready for use in Plan 03 `search_knowledge` MCP tool and Plan 03 `add_knowledge` embedding generation
- Both modules import cleanly without database or server dependencies
- No blockers for Plan 03

---
*Phase: 01-agent-connection-loop*
*Completed: 2026-02-18*
