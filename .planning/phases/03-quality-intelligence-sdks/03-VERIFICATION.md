---
phase: 03-quality-intelligence-sdks
verified: 2026-02-19T14:00:00Z
status: passed
score: 20/20 must-haves verified
gaps: []
human_verification:
  - test: "Verify quality score evolution over time with real agent traffic"
    expected: "Items receiving 'solved' outcomes should rank higher in search within 10 minutes of aggregation run"
    why_human: "Requires live DB with signal data and Celery Beat running — not verifiable statically"
  - test: "Verify RRF hybrid search latency meets <200ms P95 target"
    expected: "Search queries return in under 200ms at P95 under concurrent load"
    why_human: "Performance testing requires a running server with representative dataset and load generation"
  - test: "Verify distillation PII re-scan blocks actual PII in LLM-generated summaries"
    expected: "A generated summary containing a test email address should have it stripped before storage"
    why_human: "Requires running LLM and PII pipeline with a live database"
  - test: "Verify MinHash LSH singleton survives across requests in production mode"
    expected: "LSH index persisted in memory and finds near-duplicates across separate API calls"
    why_human: "Singleton in-memory state is process-local; needs integration test with actual add_knowledge calls"
---

# Phase 3: Quality Intelligence and SDKs Verification Report

**Phase Goal:** The commons becomes self-improving — quality scores surface the best knowledge, behavioral signals feed back into rankings, temporal tracking handles knowledge evolution, and developers can integrate via REST API and Python/TypeScript SDKs without MCP
**Verified:** 2026-02-19T14:00:00Z
**Status:** PASSED
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Quality scores (0-1) computed from behavioral signals and stored on KnowledgeItem | VERIFIED | `KnowledgeItem.quality_score` column present in `hivemind/db/models.py:186`; `compute_quality_score()` implemented with 40/25/20/15% weights in `hivemind/quality/scorer.py` |
| 2 | Behavioral signals (retrieval, outcome, contradiction) recorded in quality_signals table | VERIFIED | `QualitySignal` model in `hivemind/db/models.py:234`; `record_signal()` in `hivemind/quality/signals.py`; signals correctly insert via `get_session()` |
| 3 | Signals feed back into quality_score via periodic Celery aggregation | VERIFIED | `aggregate_quality_signals()` in `hivemind/quality/aggregator.py` queries items with new signals since last run and updates `quality_score`; registered as `hivemind.aggregate_quality_signals` task in `hivemind/webhooks/tasks.py:186` |
| 4 | Search results ranked by quality-boosted RRF (hybrid vector + text) | VERIFIED | `_search()` in `hivemind/server/tools/search_knowledge.py:299` implements two-CTE RRF with formula `rrf_score * (0.7 + 0.3 * quality_score)` entirely in SQL |
| 5 | Bi-temporal columns track knowledge validity over time | VERIFIED | `valid_at`, `invalid_at`, `expired_at` columns on `KnowledgeItem` in `hivemind/db/models.py:204-212`; migration `alembic/versions/006_quality_temporal.py` adds all columns |
| 6 | Temporal queries return knowledge valid at a specific point in time | VERIFIED | `build_temporal_filter()` in `hivemind/temporal/queries.py:40` returns 3 SQLAlchemy conditions; `search_knowledge` accepts `at_time` and `version` parameters |
| 7 | Agents can report outcome ("solved"/"did_not_help") via MCP tool | VERIFIED | `report_outcome` MCP tool in `hivemind/server/tools/report_outcome.py`; registered as 7th tool in `hivemind/server/main.py:206` |
| 8 | Outcome reporting increments helpful_count/not_helpful_count atomically | VERIFIED | Both MCP tool and REST endpoint use `sa.update(KnowledgeItem).values({counter_key: col + 1})` pattern |
| 9 | Outcome deduplication by run_id is idempotent | VERIFIED | Both `report_outcome.py` and `outcomes.py` check `QualitySignal` for existing `(item_id, run_id)` before inserting |
| 10 | Near-duplicate detection runs three stages before insertion | VERIFIED | `run_dedup_pipeline()` in `hivemind/dedup/pipeline.py` orchestrates cosine -> MinHash -> LLM; called from `add_knowledge.py:213` |
| 11 | Conflict resolution produces UPDATE/ADD/NOOP/VERSION_FORK outcomes | VERIFIED | `resolve_conflict()` and `apply_conflict_resolution()` in `hivemind/conflict/resolver.py`; multi-hop conflicts return FLAGGED_FOR_REVIEW |
| 12 | Sleep-time distillation merges duplicates, flags contradictions, generates summaries | VERIFIED | `run_distillation()` in `hivemind/quality/distillation.py:115` implements all 5 stages; PII re-scan mandatory on every LLM-generated summary |
| 13 | Distillation runs on Celery Beat schedule (30min) with threshold gate | VERIFIED | `hivemind.distill` registered in `hivemind/webhooks/tasks.py:212`; Beat schedule at `crontab(minute="*/30")` in `configure_celery()`; threshold check at distillation start |
| 14 | Developer can search/fetch knowledge via REST API with API key auth | VERIFIED | GET `/api/v1/knowledge/search` and GET `/api/v1/knowledge/{item_id}` in `hivemind/api/routes/knowledge.py`; `require_api_key` validates SHA-256 hash and increments `request_count` |
| 15 | Invalid/missing API keys return 401 | VERIFIED | `hivemind/api/auth.py:82-94` raises `HTTPException(401)` for missing or inactive keys; `APIKeyHeader(auto_error=False)` used for consistent 401 (not 403) |
| 16 | POST /api/v1/outcomes wired to real signal recording | VERIFIED | `hivemind/api/routes/outcomes.py` calls `record_signal()`, increments counter, and checks dedup — not a stub |
| 17 | Python SDK generated with typed client methods for search, fetch, report_outcome | VERIFIED | `sdks/python/hive_mind_client/api/rest_api/search_knowledge.py`, `get_knowledge_item.py`, `report_outcome.py` all exist with generated typed implementations |
| 18 | TypeScript SDK generated with typed fetch functions | VERIFIED | `sdks/typescript/src/client/sdk.gen.ts` exports `searchKnowledge`, `getKnowledgeItem`, `reportOutcome` with type-safe signatures and X-API-Key security |
| 19 | Makefile generate-sdks target regenerates both SDKs | VERIFIED | `Makefile` contains `generate-sdks`, `generate-python-sdk`, `generate-ts-sdk`, `check-sdk-drift` targets; uses explicit `.venv/bin/` paths |
| 20 | Quality pre-screening filters low-quality items before review queue | VERIFIED | `run_distillation()` step (e) queries pending items, computes preliminary score, flags items below 0.2 with `is_sensitive_flagged=True` |

**Score:** 20/20 truths verified

---

## Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `alembic/versions/006_quality_temporal.py` | Migration adding quality + temporal columns and quality_signals table | VERIFIED | Exists, chains from revision 005, adds quality_score/retrieval_count/helpful_count/not_helpful_count/valid_at/invalid_at/expired_at and quality_signals table with backfill |
| `hivemind/quality/scorer.py` | Pure function compute_quality_score() returning float 0-1 | VERIFIED | 122 lines; implements 40% usefulness + 25% popularity (tanh) + 20% freshness (exp decay) - 15% contradiction + 10% version bonus; uses stdlib math only |
| `hivemind/quality/signals.py` | record_signal(), get_signals_for_item(), increment_retrieval_count() | VERIFIED | All three functions present; use async get_session() pattern; atomic SQL UPDATE for counter increment |
| `hivemind/db/models.py` | Updated KnowledgeItem with quality/temporal columns; QualitySignal model | VERIFIED | KnowledgeItem has quality_score (default 0.5), retrieval/helpful/not_helpful counts, valid_at/invalid_at/expired_at columns; QualitySignal model with knowledge_item_id FK, signal_type, agent_id, run_id, signal_metadata |
| `hivemind/api/auth.py` | require_api_key FastAPI dependency with SHA-256 hash lookup and billing reset | VERIFIED | SHA-256 hash comparison; billing period reset; atomic request_count increment in same DB session |
| `hivemind/api/router.py` | APIRouter at /api/v1/ prefix including sub-routers | VERIFIED | `api_router = APIRouter(prefix="/api/v1")` including knowledge_router and outcomes_router |
| `hivemind/api/routes/knowledge.py` | GET /knowledge/search and GET /knowledge/{item_id} endpoints | VERIFIED | Both endpoints present with Pydantic response schemas, operation_id set, delegates to `_search()`/`_fetch_by_id()` |
| `hivemind/api/routes/outcomes.py` | POST /outcomes wired to signal recording (not stub) | VERIFIED | Full implementation: UUID validation, org access check, deduplication by run_id, `record_signal()` call, atomic counter increment; returns 202 |
| `hivemind/server/tools/report_outcome.py` | MCP-06 outcome reporting tool | VERIFIED | Auth extraction, outcome validation, UUID validation, org isolation check, run_id deduplication, record_signal(), atomic counter increment |
| `hivemind/temporal/queries.py` | build_temporal_filter() and query_at_time() | VERIFIED | `build_temporal_filter()` returns 3 SQLAlchemy conditions (valid_at NULL or <=T, invalid_at NULL or >T, expired_at IS NULL); NULL valid_at treated as always-valid |
| `hivemind/server/tools/search_knowledge.py` | Hybrid RRF search with quality boosting and temporal support | VERIFIED | Two-CTE approach (vector + text) fused by RRF; quality boost `rrf_score * (0.7 + 0.3 * quality_score)` in SQL; at_time/version parameters; fire-and-forget retrieval count tracking |
| `hivemind/dedup/pipeline.py` | Three-stage dedup orchestration | VERIFIED | `run_dedup_pipeline()` orchestrates cosine -> MinHash -> LLM; returns ADD or DUPLICATE with stages_run list |
| `hivemind/dedup/minhash_stage.py` | MinHash LSH near-duplicate detection | VERIFIED | Singleton `_lsh_index`; `get_lsh_index()`, `minhash_for_text()`, `insert_into_lsh()`, `find_minhash_candidates()`, `rebuild_lsh_index()` |
| `hivemind/dedup/llm_stage.py` | LLM-based semantic duplicate confirmation | VERIFIED | `confirm_duplicate_llm()` calls Anthropic API with 10s timeout; graceful skip when no API key |
| `hivemind/conflict/resolver.py` | LLM conflict resolution with four outcomes | VERIFIED | `resolve_conflict()` with UPDATE/ADD/NOOP/VERSION_FORK/FLAGGED_FOR_REVIEW; `apply_conflict_resolution()` executes DB actions for each case |
| `hivemind/quality/aggregator.py` | Celery task for quality signal aggregation | VERIFIED | Incremental (only items with new signals since last_run); calls `compute_quality_score()`; updates KnowledgeItem.quality_score; stores timestamp in deployment_config |
| `hivemind/quality/distillation.py` | Sleep-time distillation Celery task | VERIFIED | 566 lines; all 5 stages implemented; PII re-scan mandatory on summaries; provenance links in JSONB tags; quality pre-screening with 0.2 threshold |
| `hivemind/webhooks/tasks.py` | Celery Beat schedule with both tasks | VERIFIED | `aggregate_quality_signals_task` at `hivemind.aggregate_quality_signals` (10min); `run_distillation_task` at `hivemind.distill` (30min); both registered and scheduled |
| `Makefile` | generate-sdks target | VERIFIED | Contains `generate-sdks`, `generate-openapi`, `generate-python-sdk`, `generate-ts-sdk`, `check-sdk-drift` targets with explicit `.venv/bin/` paths |
| `sdks/python/hive_mind_client/` | Generated Python SDK | VERIFIED | Generated package with `search_knowledge.py`, `get_knowledge_item.py`, `report_outcome.py` under `api/rest_api/`; `AuthenticatedClient` in `client.py` |
| `sdks/typescript/src/client/sdk.gen.ts` | Generated TypeScript SDK | VERIFIED | Exports `searchKnowledge`, `getKnowledgeItem`, `reportOutcome` with type-safe signatures; X-API-Key security header applied; targets `/api/v1/` endpoints |
| `scripts/export_openapi.py` | OpenAPI spec export without running server | VERIFIED | File exists; enables SDK generation from FastAPI app import without DB/Redis |

---

## Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `hivemind/quality/scorer.py` | `hivemind/db/models.py` | Not directly — pure function, no DB calls | VERIFIED | Intentional design: scorer is a pure function; called by aggregator which imports models separately |
| `hivemind/quality/signals.py` | `hivemind/db/models.py` | Imports `KnowledgeItem`, `QualitySignal` | VERIFIED | Line 19: `from hivemind.db.models import KnowledgeItem, QualitySignal` |
| `hivemind/api/auth.py` | `hivemind/db/models.py` | Validates API key against ApiKey model | VERIFIED | Line 29: `from hivemind.db.models import ApiKey`; uses SHA-256 hash lookup |
| `hivemind/api/middleware.py` | `hivemind/db/models.py` | Metering integrated into auth dependency | VERIFIED | Metering is in `auth.py` (same session as key lookup); middleware.py is a design doc stub — this was an intentional architectural decision documented in 03-02-SUMMARY.md |
| `hivemind/server/main.py` | `hivemind/api/router.py` | `app.include_router(api_router)` | VERIFIED | Line 255: `app.include_router(api_router)` |
| `hivemind/server/tools/report_outcome.py` | `hivemind/quality/signals.py` | Calls `record_signal()` | VERIFIED | Line 34: `from hivemind.quality.signals import record_signal`; called at line 187 |
| `hivemind/temporal/queries.py` | `hivemind/db/models.py` | Filters on valid_at/invalid_at/expired_at | VERIFIED | Line 34: `from hivemind.db.models import KnowledgeItem`; conditions reference `KnowledgeItem.valid_at`, `KnowledgeItem.invalid_at`, `KnowledgeItem.expired_at` |
| `hivemind/server/tools/search_knowledge.py` | `hivemind/temporal/queries.py` | Applies temporal filter to search query | VERIFIED | Line 55: `from hivemind.temporal.queries import build_temporal_filter`; applied at line 386 |
| `hivemind/server/tools/search_knowledge.py` | `hivemind/db/models.py` | Uses quality_score in ranking formula | VERIFIED | `KnowledgeItem.quality_score` used in `rrf_scores.c.rrf_score * (0.7 + 0.3 * KnowledgeItem.quality_score)` at line 452 |
| `hivemind/quality/aggregator.py` | `hivemind/quality/scorer.py` | Calls compute_quality_score() | VERIFIED | Line 51 (lazy import): `from hivemind.quality.scorer import compute_quality_score`; called at line 175 |
| `hivemind/webhooks/tasks.py` | `hivemind/quality/aggregator.py` | Schedules aggregation task in Celery Beat | VERIFIED | Task registered at `hivemind.aggregate_quality_signals`; lazy import `from hivemind.quality.aggregator import aggregate_quality_signals` |
| `hivemind/quality/distillation.py` | `hivemind/pipeline/pii.py` | Re-scans generated summaries through PII pipeline | VERIFIED | Line 418: `from hivemind.pipeline.pii import PIIPipeline`; `PIIPipeline.get_instance().strip(summary_text)` called on every generated summary |
| `hivemind/dedup/pipeline.py` | `hivemind/dedup/cosine_stage.py` | Calls cosine similarity as stage 1 | VERIFIED | Line 23: `from hivemind.dedup.cosine_stage import find_cosine_candidates`; called at line 58 |
| `hivemind/dedup/pipeline.py` | `hivemind/dedup/minhash_stage.py` | Calls MinHash LSH as stage 2 | VERIFIED | Line 25: `from hivemind.dedup.minhash_stage import find_minhash_candidates`; called at line 76 |
| `hivemind/dedup/pipeline.py` | `hivemind/dedup/llm_stage.py` | Calls LLM confirmation as stage 3 | VERIFIED | Line 24: `from hivemind.dedup.llm_stage import confirm_duplicate_llm`; called at line 113 |
| `hivemind/server/tools/add_knowledge.py` | `hivemind/dedup/pipeline.py` | Runs dedup before insertion | VERIFIED | Line 210: `from hivemind.dedup.pipeline import run_dedup_pipeline`; called at line 213 before any DB insert |
| `Makefile` | `hivemind/server/main.py` | Fetches OpenAPI spec from server via scripts/export_openapi.py | VERIFIED | `generate-openapi` target calls `.venv/bin/python scripts/export_openapi.py` which imports `app` from `hivemind.server.main` |
| `sdks/python` | `/api/v1/` | Generated client targets REST API endpoints | VERIFIED | `search_knowledge.py`, `get_knowledge_item.py`, `report_outcome.py` all reference `/api/v1/knowledge/search`, `/api/v1/knowledge/{item_id}`, `/api/v1/outcomes` |

---

## Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| MCP-06 | 03-03 | Agent can report outcome ("solved"/"did_not_help") as explicit active confirmation signal | SATISFIED | `report_outcome` MCP tool in `hivemind/server/tools/report_outcome.py`; registered in `main.py`; records quality signals and increments denormalized counters |
| SDK-01 | 03-02 | Developer can interact via REST API with API key auth and usage metering | SATISFIED | GET `/api/v1/knowledge/search`, GET `/api/v1/knowledge/{item_id}`, POST `/api/v1/outcomes`; `require_api_key` validates and meters each request |
| SDK-02 | 03-07 | Developer can integrate via Python SDK | SATISFIED | Generated Python SDK in `sdks/python/hive_mind_client/` with typed `search_knowledge`, `get_knowledge_item`, `report_outcome` methods; `AuthenticatedClient` with X-API-Key support |
| SDK-03 | 03-07 | Developer can integrate via TypeScript SDK | SATISFIED | Generated TypeScript SDK in `sdks/typescript/src/client/sdk.gen.ts` with typed `searchKnowledge`, `getKnowledgeItem`, `reportOutcome` functions; X-API-Key security applied |
| KM-02 | 03-05 | Retrieval latency: pure retrieval <200ms P95; full pipeline <1.5s P95 | SATISFIED (pending human) | Hybrid RRF implemented entirely in SQL (two CTEs, no LLM in hot path); quality boost computed in SQL; retrieval signals fire-and-forget; actual latency requires live load test |
| KM-03 | 03-04 | Near-duplicate detection: cosine -> MinHash -> LLM above configurable threshold | SATISFIED | Three-stage pipeline in `hivemind/dedup/pipeline.py`; integrated into `add_knowledge.py` before DB insert; LLM stage optional and gracefully degrading |
| KM-05 | 03-01 | Bi-temporal tracking: world-time (valid_at, invalid_at) and system-time (contributed_at, expired_at) | SATISFIED | All four columns present on KnowledgeItem; migration 006 adds them; expired_at used for system-time invalidation; invalid_at used for world-time invalidation in VERSION_FORK |
| KM-06 | 03-03 | Temporal queries "what was known at time T" including version-scoped queries | SATISFIED | `build_temporal_filter()` returns 3 conditions; `search_knowledge` accepts at_time + version parameters; NULL valid_at treated as always-valid for backward compatibility |
| KM-07 | 03-04 | LLM conflict resolution with UPDATE/ADD/NOOP/VERSION_FORK; multi-hop flagged for human review | SATISFIED | `resolve_conflict()` in `hivemind/conflict/resolver.py`; `apply_conflict_resolution()` executes DB actions; `is_direct_conflict=false` routes to FLAGGED_FOR_REVIEW |
| QI-01 | 03-01 | Each knowledge item has a quality score (0-1) derived from behavioral signals | SATISFIED | `quality_score` column on KnowledgeItem with server_default=0.5; `compute_quality_score()` computes float 0-1 from weighted signals |
| QI-02 | 03-01, 03-05 | Quality signals include retrieval frequency, outcome reports, contradiction rate, staleness, version freshness | SATISFIED | `record_signal()` for retrieval/outcome/contradiction; `increment_retrieval_count()` for denormalized counter; aggregation uses all five signal types |
| QI-03 | 03-05 | Search results ranked by quality score combined with relevance | SATISFIED | `final_score = rrf_score * (0.7 + 0.3 * quality_score)` applied in SQL; quality-boosted RRF replaces raw cosine similarity |
| QI-04 | 03-06 | Sleep-time distillation triggered by volume/conflict thresholds; PII re-scan on summaries; provenance links for erasure propagation | SATISFIED | `run_distillation()` checks thresholds before any work; mandatory `PIIPipeline.strip()` on every LLM summary; `source_item_ids` in tags for provenance |
| QI-05 | 03-06 | Distillation merges duplicates, flags contradictions, generates summaries, quality pre-screening | SATISFIED | All five distillation stages implemented; duplicates expired (not deleted) via expired_at; contradiction clusters flagged; summaries generated with PII re-scan; low-quality items flagged with is_sensitive_flagged |

**All 15 requirement IDs from phase plans accounted for and SATISFIED.**

---

## Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `hivemind/api/middleware.py` | N/A | Design doc stub — metering was intentionally moved into auth.py | INFO | No impact — metering is correctly implemented in `hivemind/api/auth.py`; middleware.py is a design documentation note, not a broken implementation |
| `hivemind/dedup/minhash_stage.py` | 109 | `return []` on rebuild_lsh_index exception path | INFO | Graceful degradation, not a functional stub — the return is in a try/except that handles unavailable DB |
| `hivemind/db/models.py` | 68 | `pass` in Base class | INFO | Standard SQLAlchemy DeclarativeBase pattern; not a stub |

No blocker anti-patterns found. The `hivemind/api/middleware.py` stub was an intentional design choice documented in 03-02-SUMMARY.md — metering was colocated into `require_api_key` for atomicity and testability.

---

## Human Verification Required

### 1. Quality Score Evolution Under Real Traffic

**Test:** Run two agents against a live HiveMind instance. Have Agent A add a knowledge item and Agent B search for it and report `solved`. Wait 10 minutes for the Celery Beat aggregation cycle.
**Expected:** The item's `quality_score` increases above 0.5 (the neutral prior). On the next search, the item ranks higher than similar items without outcome signals.
**Why human:** Requires a running database, Celery worker, and real agent traffic — not verifiable statically.

### 2. Hybrid Search Latency Under Load

**Test:** Send 100 concurrent search requests to `GET /api/v1/knowledge/search` against a populated database (~10,000 items) and measure P95 latency.
**Expected:** P95 latency under 200ms with quality-boosted RRF (no LLM in hot path).
**Why human:** Performance testing requires representative dataset, live server, and load generation tools.

### 3. Distillation PII Re-scan on Real LLM Output

**Test:** Seed a cluster of 3+ similar knowledge items. Enable an Anthropic API key. Run the distillation task. Inspect generated summary for PII presence.
**Expected:** If the LLM includes any PII patterns in the summary, they should be stripped before the summary is stored as a new KnowledgeItem.
**Why human:** Requires live LLM call, live PII pipeline, and live database — not testable statically.

### 4. MinHash LSH Singleton Persistence Across Requests

**Test:** Call `add_knowledge` to insert two near-lexically-identical items in separate API calls. Verify that the second call detects the MinHash similarity to the first.
**Expected:** The LSH singleton persists the first item's MinHash in memory and the second call finds it as a near-duplicate candidate.
**Why human:** Requires live server with two real API calls in the same worker process. Static analysis cannot verify in-process singleton state across requests.

---

## Gaps Summary

No gaps found. All 20 observable truths are VERIFIED across all three levels:
- Level 1 (Exists): All artifact files are present on disk
- Level 2 (Substantive): All files contain real implementations, not stubs or placeholders
- Level 3 (Wired): All key connections between modules are verified in the code

The one deviation worth noting: `hivemind/api/middleware.py` is a documentation stub rather than functional code, but this is intentional — the metering functionality it was originally planned to provide was correctly moved into `hivemind/api/auth.py` for atomicity and testability, as documented in the 03-02-SUMMARY.md. The goal (usage metering per request) is fully achieved.

**Phase 3 goal achieved:** The commons is self-improving. Quality scores surface the best knowledge (QI-01, QI-03), behavioral signals feed back into rankings via Celery aggregation (QI-02), temporal tracking handles knowledge evolution with full bi-temporal support (KM-05, KM-06), near-duplicate detection prevents redundancy (KM-03), conflict resolution handles contradictions intelligently (KM-07), distillation maintains the commons at scale (QI-04, QI-05), and developers can integrate via REST API (SDK-01) and generated Python/TypeScript SDKs (SDK-02, SDK-03) without MCP.

---

_Verified: 2026-02-19T14:00:00Z_
_Verifier: Claude (gsd-verifier)_
