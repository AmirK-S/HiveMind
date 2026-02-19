# Phase 3: Quality Intelligence & SDKs - Research

**Researched:** 2026-02-19
**Domain:** Quality scoring, hybrid search, bi-temporal data modeling, near-duplicate detection, REST API + Python/TypeScript SDKs
**Confidence:** MEDIUM-HIGH (core stack verified; some implementation details inferred from official docs and verified secondary sources)

---

## Summary

Phase 3 transforms HiveMind's commons from a passive store into a self-improving system. It introduces five distinct technical sub-domains that must be implemented concurrently and interact at the data layer: (1) a quality scoring system driven by behavioral signals, (2) hybrid BM25+vector search with RRF for higher-quality rankings, (3) bi-temporal knowledge tracking enabling point-in-time queries, (4) a three-stage near-duplicate detection pipeline, and (5) a REST API with generated Python and TypeScript SDKs.

The existing codebase (pgvector + PostgreSQL + FastAPI + Celery + SQLAlchemy) provides clean extension points for all five sub-domains without requiring new infrastructure. Quality scoring requires new database columns on `knowledge_items` and a Celery-based signal aggregation job. Hybrid search requires adding a BM25 index via ParadeDB's `pg_search` extension or the lighter `pg_textsearch` from Timescale, then fusing results via SQL CTEs with RRF. Bi-temporal tracking requires new `valid_at`/`invalid_at` (world-time) and `created_at`/`expired_at` (system-time) columns, handled as explicit nullable timestamps rather than PostgreSQL range types (which have SQLAlchemy friction). Near-duplicate detection uses `datasketch` for MinHash/LSH as the second stage, with cosine similarity as stage 1 (already implemented) and LLM confirmation as stage 3. SDKs are best generated from FastAPI's OpenAPI spec using `openapi-python-client` (Python) and `@hey-api/openapi-ts` (TypeScript).

**Primary recommendation:** Extend `knowledge_items` with quality + temporal columns in a single migration, add `pg_search` for BM25, implement quality signal aggregation as a Celery periodic task, and generate SDKs from the OpenAPI spec rather than hand-rolling client code.

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| MCP-06 | Agent reports outcome ("solved" / "did not help") after retrieval — explicit active signal for quality scoring | New MCP tool `report_outcome` posts to a `quality_signals` table; Celery aggregates signals into `quality_score` on `knowledge_items` |
| SDK-01 | REST API with API key auth and usage metering per billing period | FastAPI `/api/v1/` router with `APIKeyHeader` dependency; existing `ApiKey` model already has `request_count` + `billing_period_start`; metering middleware increments count |
| SDK-02 | Python SDK | Generate from OpenAPI spec using `openapi-python-client`; produces typed `AuthenticatedClient` + `api/` module per tag |
| SDK-03 | TypeScript SDK | Generate from OpenAPI spec using `@hey-api/openapi-ts`; produces typed fetch-based client with zero runtime overhead |
| KM-02 | Two retrieval tiers: pure (<200ms P95) and full pipeline with LLM reranking (<1.5s P95) | Pure tier: vector + BM25 + RRF in SQL; pgvector HNSW achieves sub-100ms P95 at moderate dataset sizes; full pipeline adds cross-encoder reranking as Celery task |
| KM-03 | Three-stage dedup: cosine similarity → MinHash/LSH → LLM confirmation (threshold 0.95) | Stage 1: existing `find_similar` in `PgVectorDriver`; Stage 2: `datasketch` MinHash LSH; Stage 3: LLM confirmation via OpenAI/Anthropic API call |
| KM-05 | Bi-temporal tracking: world-time (valid_at, invalid_at) + system-time (created_at, expired_at); invalidation marks expired, not deletes | New nullable timestamp columns on `knowledge_items`; Alembic migration with two-step (nullable → backfill → not-null); invalidation sets `invalid_at` / `expired_at` |
| KM-06 | Temporal queries ("what was known about X at time T") including version-scoped | SQL WHERE clause filtering on `valid_at <= T AND (invalid_at IS NULL OR invalid_at > T)` + optional `version` column filter |
| KM-07 | LLM-assisted conflict resolution: UPDATE / ADD / NOOP / VERSION_FORK outcomes; single-hop only; multi-hop flagged for human review | Conflict detector Celery task; LLM prompt with structured JSON output; VERSION_FORK creates sibling `knowledge_items` row with different `valid_at` range |
| QI-01 | Quality score 0-1 per knowledge item derived from behavioral signals | New `quality_score` Float column on `knowledge_items`; default 0.5 at approval; updated by signal aggregation job |
| QI-02 | Quality signals: retrieval frequency, explicit outcome reporting, contradiction rate, staleness, version freshness | New `quality_signals` table; `retrieval_count` + `helpful_count` + `not_helpful_count` denormalized on `knowledge_items` for dashboard display |
| QI-03 | Search results ranked by quality score combined with relevance | RRF already produces relevance score; multiply or additively combine with `quality_score` before final ORDER BY |
| QI-04 | Sleep-time distillation as background job; re-runs PII pipeline on generated summaries; maintains provenance links | Celery Beat periodic task; triggered by `pending_contributions` volume or conflict count threshold; PII pipeline singleton already available |
| QI-05 | Distillation merges duplicates, flags contradictions, generates summaries; quality pre-screening before human approval queue | Distillation task produces `distilled_summaries`; quality gate filters low-score items before they appear in CLI review queue |

</phase_requirements>

---

## Standard Stack

### Core (already in project)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| FastAPI | current | REST API routing, OpenAPI spec generation | Already used for MCP server; OpenAPI spec enables SDK generation |
| SQLAlchemy 2.0 async | >=2.0 | ORM + query building for new temporal columns | Already used; async session pattern established |
| Alembic | current | Schema migrations for new columns/tables | Already used; `.alembic/` directory present |
| Celery 5.x | 5.5.3 | Background distillation, signal aggregation, conflict resolution | Already configured with Redis broker |
| pgvector | current | Vector similarity search (HNSW, cosine distance) | Already in use with HNSW index on `knowledge_items` |

### New Additions Required
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pg_search (ParadeDB) | 0.18+ | BM25 full-text search extension for PostgreSQL | Required for KM-02 hybrid search tier |
| datasketch | 1.9.0 | MinHash + LSH for near-duplicate detection | Required for KM-03 stage 2 |
| openapi-python-client | latest | Generate Python SDK from FastAPI OpenAPI spec | Required for SDK-02 |
| @hey-api/openapi-ts | latest | Generate TypeScript SDK from FastAPI OpenAPI spec | Required for SDK-03 |

### Supporting (already in project)
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| Celery Beat | (bundled with Celery) | Periodic task scheduling for distillation | For scheduled background jobs |
| redis | current | Celery broker + result backend | Already configured |
| httpx | current | HTTP client for LLM API calls in conflict resolution | Already in pyproject.toml |
| Presidio | current | PII pipeline on distilled summaries | Already in project (QI-04 requirement) |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| pg_search (ParadeDB) | pg_textsearch (Timescale) | pg_textsearch is MIT-licensed and lighter; ParadeDB has richer features and better docs; either works for BM25 |
| pg_search | rank_bm25 Python library | Python-only BM25 misses sub-200ms target; SQL-native is required for the pure retrieval tier |
| datasketch | Custom Jaccard similarity | datasketch handles sub-linear LSH query cost; naive pairwise comparison is O(n²) and unusable at scale |
| openapi-python-client | hand-rolled SDK | Generated clients stay in sync with API changes; hand-rolled clients drift immediately |
| @hey-api/openapi-ts | openapi-typescript-codegen | openapi-typescript-codegen is abandoned; hey-api is the active maintained fork used by Vercel/PayPal |
| Celery Beat periodic | event-driven trigger | Celery Beat triggers by time; condition-based (volume threshold) must be implemented inside the task body, not the scheduler |

**Installation:**
```bash
# Python dependencies
pip install datasketch openapi-python-client

# TypeScript/Node SDK generation (dev-time only)
npm install -D @hey-api/openapi-ts

# PostgreSQL extension (on the database host)
# Option A: ParadeDB prebuilt binary (Ubuntu/Debian/RHEL)
# See https://docs.paradedb.com/documentation/getting-started/self-hosted
# Option B: pg_textsearch (MIT, simpler)
# git clone https://github.com/timescale/pg_textsearch
```

---

## Architecture Patterns

### Recommended Project Structure Extensions

```
hivemind/
├── api/                        # NEW: REST API layer (SDK-01)
│   ├── __init__.py
│   ├── router.py               # FastAPI APIRouter with /api/v1/ prefix
│   ├── auth.py                 # APIKeyHeader dependency (wraps existing api_key.py)
│   ├── middleware.py           # Usage metering middleware (increments request_count)
│   └── routes/
│       ├── knowledge.py        # GET/POST /knowledge, search, fetch-by-id
│       └── outcomes.py         # POST /outcomes (MCP-06 REST equivalent)
├── quality/                    # NEW: Quality Intelligence (QI-01 to QI-05)
│   ├── __init__.py
│   ├── scorer.py               # Quality score computation (weighted formula)
│   ├── signals.py              # Signal recording and retrieval
│   └── distillation.py        # Sleep-time distillation Celery task
├── dedup/                      # NEW: Three-stage dedup (KM-03)
│   ├── __init__.py
│   ├── cosine_stage.py         # Stage 1: reuse find_similar from PgVectorDriver
│   ├── minhash_stage.py        # Stage 2: datasketch MinHash LSH
│   └── llm_stage.py           # Stage 3: LLM confirmation prompt
├── temporal/                   # NEW: Bi-temporal logic (KM-05, KM-06)
│   ├── __init__.py
│   └── queries.py             # Point-in-time query helpers
├── conflict/                   # NEW: LLM-assisted conflict resolution (KM-07)
│   ├── __init__.py
│   └── resolver.py            # UPDATE/ADD/NOOP/VERSION_FORK logic
├── graph/
│   └── driver.py              # EXISTING: FalkorDBDriver stubs stay as-is
├── db/
│   └── models.py              # EXTEND: new columns on KnowledgeItem
└── webhooks/
    └── tasks.py               # EXTEND: new Celery tasks for distillation/conflict
```

### Pattern 1: REST API Layer Mounted on Existing FastAPI App

**What:** A separate `APIRouter` with `/api/v1/` prefix, API key auth via dependency injection, mounted on the existing FastAPI `app` in `server/main.py`.

**When to use:** SDK-01 requirement; avoids MCP-specific transport for developer consumers.

```python
# hivemind/api/router.py
from fastapi import APIRouter, Depends, Security
from fastapi.security import APIKeyHeader

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=True)

router = APIRouter(prefix="/api/v1", tags=["rest-api"])

async def verify_api_key(api_key: str = Security(api_key_header)) -> ApiKey:
    # Look up hashed key in api_keys table
    key_hash = hashlib.sha256(api_key.encode()).hexdigest()
    async with get_session() as session:
        result = await session.execute(
            select(ApiKey).where(ApiKey.key_hash == key_hash, ApiKey.is_active == True)
        )
        record = result.scalar_one_or_none()
    if not record:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return record

# Mounted in server/main.py:
# app.include_router(api_router)
```

**Key insight:** The `ApiKey` model already exists with `request_count` + `billing_period_start`. Metering is an `add_api_route` middleware that increments `request_count` after each successful response. Reset logic checks `billing_period_reset_days` relative to `billing_period_start`.

### Pattern 2: Hybrid Search via BM25 + Vector RRF

**What:** Two CTEs — one BM25 (lexical), one vector cosine — each returning top-N rows ranked by their respective scores, fused by Reciprocal Rank Fusion formula `1/(60 + rank)`.

**When to use:** KM-02 pure retrieval tier; SQL-native keeps latency under 200ms by avoiding Python-side merging.

```sql
-- Source: https://www.paradedb.com/blog/hybrid-search-in-postgresql-the-missing-manual
WITH bm25_results AS (
  SELECT id,
         ROW_NUMBER() OVER (ORDER BY paradedb.score(id) DESC) AS bm25_rank
  FROM knowledge_items
  WHERE content @@@ paradedb.parse('query_text')
    AND (org_id = :org_id OR is_public = true)
    AND deleted_at IS NULL
  LIMIT 20
),
vector_results AS (
  SELECT id,
         ROW_NUMBER() OVER (ORDER BY embedding <=> :query_vector) AS vec_rank
  FROM knowledge_items
  WHERE (org_id = :org_id OR is_public = true)
    AND embedding IS NOT NULL
    AND deleted_at IS NULL
  LIMIT 20
),
rrf_fused AS (
  SELECT id, SUM(1.0 / (60 + rank)) AS rrf_score FROM (
    SELECT id, bm25_rank AS rank FROM bm25_results
    UNION ALL
    SELECT id, vec_rank AS rank FROM vector_results
  ) ranked GROUP BY id
),
quality_boosted AS (
  SELECT ki.id, rrf_fused.rrf_score * (0.7 + 0.3 * ki.quality_score) AS final_score
  FROM rrf_fused
  JOIN knowledge_items ki ON ki.id = rrf_fused.id
)
SELECT * FROM quality_boosted ORDER BY final_score DESC LIMIT :limit;
```

The `quality_boosted` CTE integrates QI-03 (quality × relevance combined ranking) directly in the query.

### Pattern 3: Quality Score Formula

**What:** A weighted combination of normalized behavioral signals, updated by a Celery periodic task.

**When to use:** QI-01, QI-02 — every time signal aggregation runs.

```python
# hivemind/quality/scorer.py
def compute_quality_score(
    retrieval_count: int,
    helpful_count: int,
    not_helpful_count: int,
    contradiction_rate: float,  # 0.0-1.0
    days_since_last_access: float,
    is_version_current: bool,
    staleness_half_life_days: float = 90.0,
) -> float:
    """Compute a 0-1 quality score from behavioral signals.

    Formula:
      usefulness = helpful / max(helpful + not_helpful, 1)
      popularity = tanh(retrieval_count / 50)  # saturates at ~200 retrievals
      freshness  = exp(-ln(2) * days_since_last_access / staleness_half_life_days)
      version_bonus = 0.1 if is_version_current else 0.0
      raw = 0.40 * usefulness + 0.25 * popularity + 0.20 * freshness
            - 0.15 * contradiction_rate + version_bonus
    """
    import math
    usefulness = helpful_count / max(helpful_count + not_helpful_count, 1)
    popularity = math.tanh(retrieval_count / 50)
    freshness = math.exp(-math.log(2) * days_since_last_access / staleness_half_life_days)
    raw = (
        0.40 * usefulness
        + 0.25 * popularity
        + 0.20 * freshness
        - 0.15 * contradiction_rate
        + (0.1 if is_version_current else 0.0)
    )
    return max(0.0, min(1.0, raw))
```

**Weights are tunable** — store them in `deployment_config` table so they can be adjusted without code changes.

### Pattern 4: Three-Stage Deduplication

**What:** Stage 1 (cosine) fast-rejects non-duplicates; Stage 2 (MinHash LSH) catches lexical near-duplicates that embeddings miss; Stage 3 (LLM) confirms with semantic understanding.

**When to use:** KM-03 — run during ingestion pipeline before inserting a new `PendingContribution`.

```python
# hivemind/dedup/minhash_stage.py
from datasketch import MinHash, MinHashLSH

# Build LSH index from existing knowledge items (rebuild on schedule or incrementally)
lsh = MinHashLSH(threshold=0.95, num_perm=128)

def make_minhash(text: str, num_perm: int = 128) -> MinHash:
    m = MinHash(num_perm=num_perm)
    for token in text.lower().split():
        m.update(token.encode("utf8"))
    return m

async def find_minhash_candidates(content: str, top_k: int = 10) -> list[str]:
    """Returns IDs of existing items with Jaccard similarity >= 0.95."""
    mh = make_minhash(content)
    return lsh.query(mh)  # Returns list of item IDs
```

**Important LSH limitation:** The `threshold` parameter is fixed at LSH initialization and cannot be changed without rebuilding the index. For KM-03's 0.95 threshold, set `MinHashLSH(threshold=0.95, num_perm=128)`. Higher `num_perm` increases accuracy but also memory and compute cost.

**LSH index persistence:** For production, use `datasketch`'s Redis storage backend so the index survives restarts:
```python
lsh = MinHashLSH(
    threshold=0.95, num_perm=128,
    storage_config={"type": "redis", "redis": {"host": "localhost", "port": 6379}}
)
```

### Pattern 5: Bi-temporal Column Design

**What:** Two independent timelines per knowledge item. World-time: when the fact was true in the real world. System-time: when HiveMind ingested and expired it.

**When to use:** KM-05, KM-06 — every `knowledge_items` row needs these four columns.

```python
# Addition to hivemind/db/models.py (KnowledgeItem class)
# World-time (valid_at = when fact became true; invalid_at = when it stopped being true)
valid_at: Mapped[datetime.datetime] = mapped_column(
    DateTime(timezone=True), nullable=True, default=None
)
invalid_at: Mapped[datetime.datetime | None] = mapped_column(
    DateTime(timezone=True), nullable=True, default=None
)

# System-time (expired_at = when this row was superseded in HiveMind)
# created_at already exists as contributed_at (reuse; do NOT add a duplicate)
expired_at: Mapped[datetime.datetime | None] = mapped_column(
    DateTime(timezone=True), nullable=True, default=None
)
```

**Point-in-time query pattern (KM-06):**
```python
# "What was known about X at time T?"
stmt = select(KnowledgeItem).where(
    KnowledgeItem.valid_at <= target_time,
    (KnowledgeItem.invalid_at.is_(None)) | (KnowledgeItem.invalid_at > target_time),
    KnowledgeItem.expired_at.is_(None),  # only current system-time rows
    (KnowledgeItem.org_id == org_id) | (KnowledgeItem.is_public == True),
)
```

**Design rationale:** Using four explicit nullable timestamp columns instead of PostgreSQL `TSTZRANGE` avoids SQLAlchemy friction (confirmed by multiple GitHub issues with TSTZRANGE type handling). PostgreSQL 18 adds `WITHOUT OVERLAPS` temporal constraints but HiveMind currently targets PostgreSQL 14+, so range-type primary keys are not yet usable. Plain nullable columns are portable and equally queryable.

### Pattern 6: SDK Generation Pipeline

**What:** A `make generate-sdks` Makefile target that (1) fetches the OpenAPI JSON from the running server and (2) runs both generators.

**When to use:** SDK-02, SDK-03 — run once after REST API is implemented; re-run when API changes.

```makefile
# Makefile
generate-sdks:
	# Python SDK
	openapi-python-client generate \
	  --url http://localhost:8000/openapi.json \
	  --output-path sdks/python \
	  --overwrite
	# TypeScript SDK
	npx @hey-api/openapi-ts \
	  -i http://localhost:8000/openapi.json \
	  -o sdks/typescript/src/client
```

**Custom operation IDs** in FastAPI prevent ugly generated method names:
```python
# server/main.py or api/router.py
def custom_generate_unique_id(route: APIRoute) -> str:
    return f"{route.tags[0]}-{route.name}"

app = FastAPI(generate_unique_id_function=custom_generate_unique_id)
```

### Pattern 7: Outcome Reporting MCP Tool (MCP-06)

**What:** A new MCP tool `report_outcome` that records whether a retrieved item helped solve the agent's problem.

**When to use:** MCP-06 — exposed as both an MCP tool and a REST endpoint.

```python
# hivemind/server/tools/report_outcome.py
async def report_outcome(
    item_id: str,
    outcome: str,  # "solved" | "did_not_help"
    run_id: str | None = None,
) -> dict:
    """Report whether a retrieved knowledge item solved the agent's problem.

    Args:
        item_id: UUID of the knowledge item that was retrieved.
        outcome: "solved" if the item helped, "did_not_help" if it didn't.
        run_id:  Optional agent run identifier for deduplication.

    Records a quality signal in the quality_signals table. Signal aggregation
    runs via Celery to update the item's quality_score (QI-01, QI-02).
    """
```

### Pattern 8: Sleep-Time Distillation (QI-04)

**What:** A Celery periodic task that runs distillation when volume or conflict count exceeds a threshold. The task evaluates the condition inside the task body, not in the scheduler.

**When to use:** QI-04, QI-05 — distillation is not continuous; it batches work.

```python
# hivemind/webhooks/tasks.py (addition)
@celery_app.task(name="hivemind.distill")
def run_distillation():
    """Sleep-time distillation — called by Celery Beat every N minutes.

    Evaluates volume/conflict thresholds inside the task and short-circuits
    if conditions are not met (Celery Beat only supports time-based triggering;
    condition logic must live in the task body).
    """
    pending_count = _count_pending()
    conflict_count = _count_unresolved_conflicts()
    threshold = int(deployment_config("distillation_volume_threshold", default="50"))

    if pending_count < threshold and conflict_count < 5:
        return {"status": "skipped", "reason": "below threshold"}

    # Run distillation: dedup, summarize, PII re-scan, quality pre-screen
    ...
```

**Celery Beat limitation (confirmed):** Celery Beat cannot trigger tasks based on application state. It only supports time-based schedules (fixed interval, crontab, solar). The condition evaluation must happen inside the task body. This is the correct pattern; do not attempt to implement event-driven Celery Beat.

### Anti-Patterns to Avoid

- **Hand-rolling BM25 in Python:** Python-side BM25 via `rank_bm25` library breaks the sub-200ms pure retrieval SLA. BM25 scoring must run inside PostgreSQL as a SQL operator.
- **Synchronous LSH index in request path:** Building the MinHash index synchronously per-request is O(n). Build and cache the LSH index as a singleton with periodic rebuilds.
- **Storing TSTZRANGE columns without testing SQLAlchemy compatibility:** Multiple GitHub issues confirm `DateTimeTZRange` causes DataError on insert in certain SQLAlchemy versions. Use four separate `DateTime(timezone=True)` columns instead.
- **Generating SDKs from the MCP spec instead of the REST spec:** The MCP protocol and the REST API have different shapes. SDKs should target the REST API's OpenAPI spec at `/openapi.json`.
- **Applying quality × relevance as post-processing in Python:** Computing quality-boosted ranking after fetching rows from DB defeats the latency target. The `quality_boosted` CTE must be part of the SQL query.
- **Rebuilding the full LSH index on every ingestion:** Incremental LSH insertion is supported by `datasketch` via `lsh.insert(key, minhash)`. Only rebuild the full index on startup or after deletion events.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| BM25 indexing in PostgreSQL | Custom trigram/tsvector scoring | `pg_search` (ParadeDB) or `pg_textsearch` (Timescale) | BM25 field normalization and IDF computation have subtle edge cases; production extensions handle term frequencies correctly |
| MinHash locality-sensitive hashing | Custom shingle hashing | `datasketch.MinHashLSH` | False positive/negative rate, threshold calibration, and Redis persistence are non-trivial; datasketch is battle-tested at LLM dataset scale |
| Python/TypeScript client SDKs | Manual typed HTTP clients | `openapi-python-client` + `@hey-api/openapi-ts` | Generated clients stay in sync with the OpenAPI spec automatically; hand-written clients immediately drift on API changes |
| Quality score decay functions | Custom exponential decay | Standard `math.exp(-lambda * t)` formula | No library needed; the formula is trivial; what matters is choosing the right half-life constant and storing it in config |
| Reciprocal Rank Fusion | Custom score normalization | SQL CTE pattern with `SUM(1.0 / (60 + rank))` | RRF is scale-independent and handles different score ranges automatically; custom normalization requires knowing min/max scores in advance |
| Temporal point-in-time queries | Custom "as-of" table with triggers | Explicit `valid_at`/`invalid_at` columns with WHERE clause | Trigger-based approaches add write-time complexity and are hard to test; explicit nullable columns are simple, inspectable, and supported by all ORM tools |

**Key insight:** The three most deceptively complex problems in this phase are BM25 (field normalization pitfalls), LSH (false positive rate calibration), and SDK sync (drift prevention). All three have mature off-the-shelf solutions.

---

## Common Pitfalls

### Pitfall 1: LSH Threshold Cannot Change After Index Creation

**What goes wrong:** You create the `MinHashLSH` index with `threshold=0.8` during development, then realize the requirement is `0.95`. You update the threshold in code but the index still returns results at the old threshold.

**Why it happens:** The LSH band/row calculation is fixed at `__init__` time. `datasketch` uses the threshold to compute the optimal number of bands, which determines bucket grouping. Changing the object after creation has no effect.

**How to avoid:** Always initialize from the configured threshold constant. Store `minhash_threshold` in `deployment_config`. If the threshold changes, drop and rebuild the index.

**Warning signs:** Dedup is accepting items that are clearly identical, or blocking items that are clearly different.

### Pitfall 2: ParadeDB pg_search Requires Extension on the DB Host

**What goes wrong:** `CREATE EXTENSION pg_search` fails in development or CI because the extension binaries are not installed.

**Why it happens:** `pg_search` is a Rust-based extension compiled with `pgrx`. It cannot be installed via `pip` or `npm`; it requires OS-level installation or a Docker image that includes it.

**How to avoid:** Use ParadeDB's Docker image (`paradedb/paradedb`) for local development and CI. For production, use prebuilt binaries for the target OS (Ubuntu/Debian/RHEL supported). Add `pg_textsearch` as a fallback plan — it is PL/pgSQL-based and installable without binary dependencies.

**Warning signs:** `CREATE EXTENSION pg_search` returns `ERROR: could not open extension control file`.

### Pitfall 3: BM25 + Vector Counts Don't Match for RRF

**What goes wrong:** BM25 returns 5 results (query terms not found in most items), vector returns 20 results. RRF treats both the same, but the 5 BM25 results get disproportionate weight.

**Why it happens:** RRF assumes both retrievers return roughly the same number of candidates. When one retriever returns far fewer results, its candidates cluster at low rank numbers and get boosted unfairly.

**How to avoid:** Always cap both CTEs at the same `LIMIT` (e.g., 20). Items with no BM25 match get zero contribution from the BM25 CTE, not a negative score. This is the correct RRF behavior — the final score naturally weights the semantic signal more heavily when BM25 produces fewer matches.

**Warning signs:** Known keyword-heavy queries return only semantic matches; exact-phrase queries score lower than expected.

### Pitfall 4: Temporal Columns Break Existing NULL Constraint Assumptions

**What goes wrong:** You add `valid_at NOT NULL` to `knowledge_items` and the Alembic migration fails because existing rows have no value.

**Why it happens:** Non-nullable columns on existing tables require backfilling before adding the constraint.

**How to avoid:** Always add temporal columns as nullable first. Backfill with a reasonable default (e.g., `contributed_at` for `valid_at`). Only then add NOT NULL if required. The requirement spec says `valid_at`/`invalid_at` track when facts are true — `NULL` on `invalid_at` is semantically correct ("still valid").

**Warning signs:** Alembic migration fails with `NOT NULL constraint` violation.

### Pitfall 5: SDK Drift from API

**What goes wrong:** The REST API gains a new endpoint or changes a response field. The generated SDKs are not regenerated. SDK consumers get runtime type errors or silently receive unexpected data.

**Why it happens:** SDK generation is a one-time step, not a continuous process, unless automated.

**How to avoid:** Add SDK generation to CI. Run `openapi-python-client generate` and `npx @hey-api/openapi-ts` in a CI step and commit the result. Fail the build if the generated output differs from the committed output (use `git diff --exit-code sdks/`).

**Warning signs:** SDK method signatures don't match what the API documentation shows.

### Pitfall 6: Celery Beat Volume-Threshold Trigger Misunderstood

**What goes wrong:** Developer tries to make Celery Beat trigger distillation "when pending_contributions > 50" by adding custom scheduler logic. This is unsupported and architecturally wrong.

**Why it happens:** Celery Beat is a time-based scheduler only. It does not monitor application state.

**How to avoid:** Schedule the Celery Beat task to run every 10-30 minutes via crontab. Inside the task body, check `pending_count >= threshold` and return early if not met. This is the documented pattern and requires zero custom Beat code.

**Warning signs:** Any code that subclasses `celery.beat.Scheduler` to add condition logic.

### Pitfall 7: Quality Score Not Initialized at Approval

**What goes wrong:** `quality_score` is NULL for newly approved items. The RRF quality-boosted query multiplies by NULL and the item never appears in search results.

**Why it happens:** New items haven't received any behavioral signals yet.

**How to avoid:** Set `quality_score = 0.5` (neutral prior) as the column default in the ORM model. The score is updated by the signal aggregation job only when signals are received. 0.5 means "unknown quality" — items are not penalized before they've been used.

**Warning signs:** New items don't appear in search results even when semantically relevant.

---

## Code Examples

Verified patterns from official sources:

### Hybrid Search RRF Query (SQL)
```sql
-- Source: https://www.paradedb.com/blog/hybrid-search-in-postgresql-the-missing-manual
WITH bm25_ranked AS (
  SELECT id,
         ROW_NUMBER() OVER (ORDER BY paradedb.score(id) DESC) AS rank
  FROM knowledge_items
  WHERE content @@@ paradedb.parse(:query)
  LIMIT 20
),
vector_ranked AS (
  SELECT id,
         ROW_NUMBER() OVER (ORDER BY embedding <=> :query_vector) AS rank
  FROM knowledge_items
  WHERE embedding IS NOT NULL
  LIMIT 20
),
rrf AS (
  SELECT id, SUM(1.0 / (60 + rank)) AS rrf_score
  FROM (
    SELECT id, rank FROM bm25_ranked
    UNION ALL
    SELECT id, rank FROM vector_ranked
  ) combined
  GROUP BY id
)
SELECT ki.*, rrf.rrf_score * (0.7 + 0.3 * ki.quality_score) AS final_score
FROM rrf
JOIN knowledge_items ki USING (id)
WHERE (ki.org_id = :org_id OR ki.is_public = true)
  AND ki.deleted_at IS NULL
ORDER BY final_score DESC
LIMIT :limit;
```

### FastAPI REST API Key Header Auth
```python
# Source: https://fastapi.tiangolo.com/tutorial/security/ + existing ApiKey model
from fastapi import Depends, HTTPException, Security
from fastapi.security import APIKeyHeader

API_KEY_HEADER = APIKeyHeader(name="X-API-Key", auto_error=True)

async def require_api_key(
    api_key: str = Security(API_KEY_HEADER),
    session: AsyncSession = Depends(get_session),
) -> ApiKey:
    key_hash = hashlib.sha256(api_key.encode()).hexdigest()
    result = await session.execute(
        select(ApiKey).where(
            ApiKey.key_hash == key_hash,
            ApiKey.is_active == True,
        )
    )
    record = result.scalar_one_or_none()
    if not record:
        raise HTTPException(status_code=401, detail="Invalid or inactive API key")
    return record
```

### MinHash LSH Near-Duplicate Check
```python
# Source: https://ekzhu.com/datasketch/lsh.html
from datasketch import MinHash, MinHashLSH

# Initialize once (singleton pattern, like get_embedder())
_lsh_index: MinHashLSH | None = None

def get_lsh_index() -> MinHashLSH:
    global _lsh_index
    if _lsh_index is None:
        _lsh_index = MinHashLSH(threshold=0.95, num_perm=128)
    return _lsh_index

def minhash_for_text(text: str) -> MinHash:
    m = MinHash(num_perm=128)
    for token in text.lower().split():
        m.update(token.encode("utf8"))
    return m

async def stage2_find_candidates(content: str) -> list[str]:
    lsh = get_lsh_index()
    mh = minhash_for_text(content)
    return lsh.query(mh)  # Returns item IDs with Jaccard >= 0.95
```

### TypeScript SDK Generation
```bash
# Source: https://heyapi.dev/openapi-ts/get-started
# Generate TypeScript client from running server
npx @hey-api/openapi-ts \
  -i http://localhost:8000/openapi.json \
  -o sdks/typescript/src/client \
  --plugins @hey-api/typescript @hey-api/sdk

# Usage in TypeScript consumer:
# import { KnowledgeService } from './client';
# const results = await KnowledgeService.searchKnowledge({ query: "redis timeouts" });
```

### Python SDK Generation
```bash
# Source: https://github.com/openapi-generators/openapi-python-client
# Install generator
pip install openapi-python-client

# Generate from running server
openapi-python-client generate \
  --url http://localhost:8000/openapi.json \
  --output-path sdks/python \
  --overwrite

# Usage in Python consumer:
# from hivemind_client import AuthenticatedClient
# from hivemind_client.api.rest_api import search_knowledge
# client = AuthenticatedClient(base_url="https://...", token="hm_...")
# response = search_knowledge.sync(client=client, query="redis timeouts")
```

### Bi-temporal Point-in-Time Query
```python
# Source: research synthesis from SQL:2011 patterns and SQLAlchemy docs
from sqlalchemy import select, or_

async def query_at_time(
    query_embedding: list[float],
    org_id: str,
    at_time: datetime.datetime,
    version: str | None = None,
) -> list[KnowledgeItem]:
    """Return knowledge as it was known at `at_time`."""
    async with get_session() as session:
        stmt = select(KnowledgeItem).where(
            # World-time filter: fact was valid at the target time
            KnowledgeItem.valid_at <= at_time,
            or_(
                KnowledgeItem.invalid_at.is_(None),
                KnowledgeItem.invalid_at > at_time,
            ),
            # System-time filter: only rows that hadn't been expired yet
            KnowledgeItem.expired_at.is_(None),
            # Org isolation
            or_(
                KnowledgeItem.org_id == org_id,
                KnowledgeItem.is_public == True,
            ),
            KnowledgeItem.deleted_at.is_(None),
        )
        if version:
            stmt = stmt.where(KnowledgeItem.version == version)
        result = await session.execute(stmt)
        return result.scalars().all()
```

### Celery Beat Schedule for Distillation
```python
# hivemind/webhooks/tasks.py — add to configure_celery()
from celery.schedules import crontab

def configure_celery(broker_url: str) -> None:
    celery_app.conf.broker_url = broker_url
    celery_app.conf.result_backend = broker_url
    celery_app.conf.beat_schedule = {
        "distillation-every-30m": {
            "task": "hivemind.distill",
            "schedule": crontab(minute="*/30"),  # every 30 minutes
        },
        "quality-signal-aggregation": {
            "task": "hivemind.aggregate_quality_signals",
            "schedule": crontab(minute="*/10"),  # every 10 minutes
        },
    }
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| ts_vector / ts_rank for FTS in Postgres | BM25 via pg_search or pg_textsearch | 2023-2024 | True BM25 scoring with IDF; much better relevance than ts_rank |
| openapi-typescript-codegen | @hey-api/openapi-ts (maintained fork) | 2023 | hey-api is actively maintained; original repo abandoned |
| Custom hand-written SDK clients | Generated from OpenAPI spec | Ongoing | Generated clients never drift; type-safe without manual effort |
| ELO/TrueSkill for quality scoring | Weighted multi-signal formula + exponential decay | Current | Simpler to reason about; signals are multi-dimensional, not head-to-head |
| Mutable knowledge rows (UPDATE in place) | Bi-temporal immutable rows with `invalid_at` | SQL:2011 standard | Preserves audit trail; enables point-in-time queries; matches Phase 1's immutable provenance design |

**Deprecated/outdated:**
- `openapi-typescript-codegen`: Abandoned; use `@hey-api/openapi-ts` which forked from it and is actively maintained
- `rank_bm25` Python library: Suitable only for in-memory use; cannot meet sub-200ms P95 in the retrieval hot path
- PostgreSQL `temporal_tables` C extension: Not available on managed cloud PostgreSQL (AWS RDS, Neon, Supabase); use explicit nullable columns instead

---

## Open Questions

1. **Which BM25 extension: ParadeDB `pg_search` vs Timescale `pg_textsearch`?**
   - What we know: Both implement BM25; ParadeDB is Rust-based (pgrx) with richer features; pg_textsearch is PL/pgSQL and easier to install; pg_textsearch is MIT-licensed; ParadeDB has a dual license (AGPL + commercial)
   - What's unclear: Whether pg_textsearch achieves equivalent query performance to pg_search for the sub-200ms target
   - Recommendation: Start with pg_textsearch for lower installation friction; benchmark against pg_search. If pg_textsearch performance is sufficient, prefer it for license simplicity.

2. **LLM for conflict resolution and dedup Stage 3: which provider/model?**
   - What we know: The codebase uses `httpx` for HTTP calls; no LLM provider is currently configured; both OpenAI and Anthropic have structured output modes
   - What's unclear: Whether to use a local model (Ollama) or cloud API; budget constraints not specified
   - Recommendation: Use Anthropic Claude Haiku (fast, cheap) with `response_format={"type": "json_object"}` for structured conflict resolution output. Abstract behind an `LLMClient` interface so the provider can be swapped via config.

3. **LSH index persistence strategy during writes**
   - What we know: `datasketch` supports Redis storage backend; the index must reflect currently-active knowledge items; deletions must remove items from the index
   - What's unclear: Whether to use in-process LSH (fast but lost on restart) or Redis-backed LSH (persistent but adds Redis dependency for a new use case)
   - Recommendation: Use in-process singleton with a Celery periodic rebuild task. The rebuild cost is acceptable at small-to-moderate scale. Migrate to Redis-backed LSH if the index rebuild takes >5 seconds.

4. **API versioning strategy for REST layer**
   - What we know: FastAPI supports `include_router(prefix="/api/v1")` for URL-based versioning; MCP tools are already at an implicit v1
   - What's unclear: Whether to version the SDK-facing REST API separately from the MCP protocol version
   - Recommendation: Start with `/api/v1/` prefix. Version the REST API independently from the MCP layer. SDK-02/SDK-03 consumers should pin to a specific API version in their SDK configuration.

5. **Quality score initial value for backfilled existing items**
   - What we know: Existing `knowledge_items` have no quality signals; the column default is `0.5`
   - What's unclear: Whether existing `confidence` field (0.8 default) should seed the quality score
   - Recommendation: Seed `quality_score = confidence * 0.5` for existing items during migration. This gives items with high agent confidence a slight head start (0.4) over neutral (0.5) but doesn't grant unearned authority. The signal aggregation job will correct this over time.

---

## Sources

### Primary (HIGH confidence)
- FastAPI official docs (`https://fastapi.tiangolo.com/advanced/generate-clients/`) — SDK generation patterns, OpenAPI spec usage, custom operation ID generation
- datasketch official docs (`https://ekzhu.com/datasketch/lsh.html`) — MinHash LSH API, threshold parameter behavior, Redis storage backend
- Celery 5.x official docs (`https://docs.celeryq.dev/en/stable/userguide/periodic-tasks.html`) — Celery Beat scheduling, crontab configuration, condition-based triggering limitation
- PostgreSQL temporal constraints guide (`https://betterstack.com/community/guides/databases/postgres-temporal-constraints/`) — `WITHOUT OVERLAPS`, `@>` containment operator, point-in-time query patterns
- SQLAlchemy 2.0 official docs — `TSTZRANGE` type support confirmed; existing project uses `DateTime(timezone=True)` pattern throughout

### Secondary (MEDIUM confidence)
- ParadeDB hybrid search guide (`https://www.paradedb.com/blog/hybrid-search-in-postgresql-the-missing-manual`) — RRF SQL pattern, BM25+vector fusion approach (verified against Wikipedia RRF formula)
- Aiven bi-temporal blog (`https://aiven.io/blog/two-dimensional-time-with-bitemporal-data`) — effective/asserted time modeling with PostgreSQL range types (verified against SQL:2011 Wikipedia article)
- @hey-api/openapi-ts docs (`https://heyapi.dev/openapi-ts/get-started`) — TypeScript SDK generation, supported HTTP clients, configuration approach
- openapi-python-client GitHub (`https://github.com/openapi-generators/openapi-python-client`) — Python SDK generation, generated structure, usage pattern
- pgvector HNSW benchmark (`https://mastra.ai/blog/pgvector-perf`) — P95 latency data points for IVFFlat; HNSW benchmarks less detailed in that post

### Tertiary (LOW confidence — flag for validation)
- Quality score weighting formula (0.40 usefulness / 0.25 popularity / 0.20 freshness / 0.15 contradiction): Synthesized from general ML ranking literature; weights are illustrative and MUST be tuned against real usage data. Store in `deployment_config` to allow tuning without code changes.
- pg_textsearch performance parity with pg_search for sub-200ms target: No direct benchmark found comparing both at HiveMind's expected dataset size.

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all libraries are established and in-use or well-documented
- Architecture: MEDIUM-HIGH — patterns verified against official docs; SQL RRF pattern from ParadeDB directly
- Pitfalls: HIGH — most identified from official limitations (LSH threshold immutability, Celery Beat time-only, TSTZRANGE SQLAlchemy friction) with official source backing
- Quality score formula: LOW — no canonical reference; treat as starting hypothesis subject to tuning

**Research date:** 2026-02-19
**Valid until:** 2026-04-19 (60 days — stable libraries; pg_search releases frequently but API is stable)
