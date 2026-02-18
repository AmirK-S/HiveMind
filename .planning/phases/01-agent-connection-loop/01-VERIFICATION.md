---
phase: 01-agent-connection-loop
verified: 2026-02-18T22:15:00Z
status: passed
score: 15/15 must-haves verified
re_verification:
  previous_status: gaps_found
  previous_score: 14/15
  gaps_closed:
    - "TRUST-02 — User notification surfaces quality pre-screening signals and similar existing knowledge"
  gaps_remaining: []
  regressions: []
human_verification:
  - test: "Start the MCP server (uvicorn hivemind.server.main:app), connect an MCP client with a valid JWT, call add_knowledge with a content string, verify the response contains contribution_id and status='queued'"
    expected: "add_knowledge returns {contribution_id: <uuid>, status: 'queued', category: ..., message: 'Knowledge contribution queued for review.'} and the item appears in pending_contributions"
    why_human: "Requires running PostgreSQL with pgvector, live HTTP MCP connection, and JWT generation — cannot be verified with grep alone"
  - test: "Call add_knowledge with content that is >50% PII (e.g., a string that is mostly email addresses and phone numbers), verify the response has isError=True"
    expected: "Server returns isError=True with message about >50% redaction"
    why_human: "Requires live Presidio + GLiNER model inference"
  - test: "Call search_knowledge with a query string, verify cosine-ranked results are returned scoped to the agent's org"
    expected: "Results contain id, title, category, confidence, org_attribution, relevance_score. Results from other orgs' private namespaces do not appear."
    why_human: "Requires live PostgreSQL with pgvector, active embedding model, and data in knowledge_items"
  - test: "Run 'hivemind review --org-id <org_id>' after adding a pending contribution, verify the Rich Panel displays QI badge and similar existing knowledge alongside the PII-stripped content"
    expected: "Panel shows QI badge (e.g. 'QI: +++ High (85)'), similar items section, content, category, confidence, agent ID. questionary select prompt offers 6 actions. Approving moves item to knowledge_items."
    why_human: "Requires a running terminal session with a live database and pending data; Rich + questionary need a TTY"
  - test: "Call delete_knowledge with an item ID owned by a different agent within the same org, verify 404 response (not 403)"
    expected: "Response is isError=True with 'not found' message — no 403 Forbidden revealing item existence"
    why_human: "Requires live server with data from multiple agents"
---

# Phase 01: Agent Connection Loop Verification Report

**Phase Goal:** An agent can connect to HiveMind via MCP, contribute PII-stripped knowledge through a user approval gate, search and retrieve from the shared commons, and operate within an isolated org namespace — the core contribute/retrieve loop works end-to-end
**Verified:** 2026-02-18T22:15:00Z
**Status:** passed
**Re-verification:** Yes — after TRUST-02 gap closure

---

## Re-Verification Summary

| Item | Previous | Current | Change |
|------|----------|---------|--------|
| Score | 14/15 truths | 15/15 truths | +1 gap closed |
| TRUST-02 (similar existing knowledge) | PARTIAL | VERIFIED | Fixed |
| TRUST-02 (quality pre-screening signal) | PARTIAL | VERIFIED | Fixed |
| All other truths (1-14) | VERIFIED | VERIFIED | No regression |
| All artifacts (18 files) | VERIFIED | VERIFIED | No regression |
| All key links (13 connections) | WIRED | WIRED | No regression |

---

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | PostgreSQL tables exist for pending_contributions and knowledge_items with all required columns | VERIFIED | models.py: PendingContribution (14 cols), KnowledgeItem (16 cols + deleted_at), DeploymentConfig. All columns present with correct types. |
| 2 | Every knowledge item has immutable provenance fields (source_agent_id, contributed_at, category, org_id, confidence_score, run_id, content_hash) | VERIFIED | models.py lines 80-91, 139-162: all 7 provenance fields present on both PendingContribution and KnowledgeItem. Doc states "set on INSERT and never updated." |
| 3 | Knowledge items are typed by category enum with framework/language/version metadata | VERIFIED | models.py: KnowledgeCategory enum (11 values), framework/language/version columns on both tables. |
| 4 | All tables have org_id column for namespace isolation | VERIFIED | models.py: org_id on PendingContribution (line 77), KnowledgeItem (line 133). Index on org_id on both main tables. |
| 5 | Async database sessions can be created and used for concurrent operations | VERIFIED | session.py: create_async_engine with pool_size=10/max_overflow=20, async_sessionmaker, asynccontextmanager get_session(). |
| 6 | Alembic migration creates pgvector extension, all tables, and HNSW index | VERIFIED | 001_initial_schema.py: CREATE EXTENSION IF NOT EXISTS vector, 3 tables, HNSW index (m=16, ef_construction=64), unique(content_hash, org_id), 4 indexes. 002_add_deleted_at.py: deleted_at column + partial index. |
| 7 | PII stripping detects and replaces emails, phone numbers, names, addresses with typed placeholders | VERIFIED | pii.py: AnalyzerEngine + GLiNERRecognizer (knowledgator/gliner-pii-base-v1.0) + operator config producing [EMAIL], [PHONE], [NAME], [LOCATION], [API_KEY], [CREDIT_CARD], [IP_ADDRESS], [USERNAME], [REDACTED]. |
| 8 | API keys/tokens/connection strings are detected and replaced | VERIFIED | pii.py _build_api_key_patterns(): 11 patterns covering AWS, GitHub classic, GitHub fine-grained, Google API, Stripe, Slack, JWT, RSA private key, generic secret assignment, connection strings, private URLs. |
| 9 | Content with >50% redacted tokens is auto-rejected | VERIFIED | pii.py lines 216-218: placeholder_count / total_tokens > 0.50 -> should_reject=True. add_knowledge.py lines 142-152: CallToolResult(isError=True) returned on rejection. |
| 10 | An agent can connect to HiveMind via MCP Streamable HTTP transport | VERIFIED | main.py: mcp.http_app(path="/mcp", transport="streamable-http", stateless_http=True, json_response=True). All 4 tools registered via Tool.from_function(). |
| 11 | add_knowledge PII-strips before DB insert and returns status='queued' | VERIFIED | add_knowledge.py: strip_pii() called line 139 before session.add() line 173. Returns {"status": "queued", "contribution_id": ...} line 178. |
| 12 | search_knowledge uses cosine similarity and returns summary-tier + fetch-mode | VERIFIED | search_knowledge.py: get_embedder().embed(query) line 229, cosine_distance line 233, summary tier (id/title/category/confidence/org_attribution/relevance_score) lines 262-275. Fetch mode via _fetch_by_id(). deleted_at IS NULL filter on both modes. |
| 13 | All queries scoped to org_id from JWT; agent can list/delete own contributions | VERIFIED | auth.py: decode_token() extracts org_id/agent_id from HS256 JWT. list_knowledge.py: filters by org_id AND source_agent_id. delete_knowledge.py: ownership check on org_id + source_agent_id, 404-not-403 for other orgs. |
| 14 | User approval gate: user sees PII-stripped contributions, can approve/reject/flag/override-category; approval generates embedding and moves to knowledge_items | VERIFIED | review.py: Rich Panel display, questionary 6-choice prompt, all actions wired. client.py approve_contribution(): get_embedder().embed() line 113, KnowledgeItem creation + session.delete(contribution) line 135. |
| 15 | TRUST-02 — User notification surfaces quality pre-screening signals and similar existing knowledge | VERIFIED | review.py lines 150-181: compute_qi_score() computes QI badge from confidence + is_sensitive_flagged + content length; find_similar_knowledge() runs cosine_distance against knowledge_items; both are rendered in the Rich Panel body at lines 170 and 181 respectively. |

**Score:** 15/15 truths verified

---

## TRUST-02 Gap Closure Evidence

**Previously failing sub-requirements:**

1. **Similar existing knowledge** — Now implemented in `hivemind/cli/client.py` lines 211-274 (`find_similar_knowledge()`):
   - Calls `get_embedder().embed(content)` to generate a real embedding of the pending contribution
   - Runs `KnowledgeItem.embedding.cosine_distance(embedding)` query against the knowledge_items table
   - Filters to items within cosine distance threshold (0.35 = 65% similarity floor)
   - Returns ranked list with `id`, `title`, `category`, `similarity` (%) and `org_id`
   - Items >= 80% similarity are highlighted in yellow as likely duplicates
   - Called per-item in the review loop (review.py lines 154-162) with graceful degradation on failure

2. **Quality pre-screening signal** — Now implemented in `hivemind/cli/client.py` lines 277-340 (`compute_qi_score()`):
   - Synthesises `confidence * 100` as base score
   - Applies -30 modifier for `is_sensitive_flagged=True` (PII may still be present)
   - Applies -20 modifier for very short content (<50 chars), +10 for detailed content (>200 chars)
   - Produces labeled badge: High (green, >=80) / Medium (yellow, >=50) / Low (red, <50) with icon
   - Displayed in the panel meta line as `QI: +++ High (85)` format (review.py line 170)

**Wiring verified:**
- `review.py` imports `compute_qi_score` and `find_similar_knowledge` from `hivemind.cli.client` (lines 31, 33)
- Both are called inside the review loop per-item (lines 150, 155)
- Both outputs are included in `panel_body` (lines 170, 181) which is passed to `console.print(Panel(panel_body, ...))` at line 188

---

## Required Artifacts

| Artifact | Min Lines | Actual Lines | Status | Details |
|----------|-----------|--------------|--------|---------|
| `pyproject.toml` | — | — | VERIFIED | fastmcp<3, sqlalchemy, asyncpg, pgvector, alembic, presidio, sentence-transformers, typer, rich, questionary, psycopg2-binary, CLI entry point |
| `hivemind/config.py` | — | 45 | VERIFIED | class Settings(BaseSettings), HIVEMIND_ prefix, 7 fields, module-level singleton |
| `hivemind/db/models.py` | 80 | 222 | VERIFIED | KnowledgeCategory (11 values), Base, PendingContribution, KnowledgeItem, DeploymentConfig, deleted_at column, HNSW index, unique constraint |
| `hivemind/db/session.py` | 15 | 48 | VERIFIED | engine, AsyncSessionFactory, get_session() asynccontextmanager |
| `alembic/env.py` | — | 104 | VERIFIED | register_vector, target_metadata = Base.metadata, async migrations |
| `hivemind/pipeline/pii.py` | 80 | 232 | VERIFIED | PIIPipeline singleton, strip_pii(), 11 API key patterns, typed placeholder operators, 50% rejection |
| `hivemind/pipeline/embedder.py` | 40 | 201 | VERIFIED | EmbeddingProvider ABC, SentenceTransformerProvider, get_embedder() singleton |
| `hivemind/server/main.py` | 40 | 198 | VERIFIED | FastMCP server, lifespan (PII+embedder warmup + deployment_config), all 4 tools registered, /health endpoint |
| `hivemind/server/auth.py` | 20 | 91 | VERIFIED | AuthContext dataclass, decode_token(), create_token(), HS256 JWT |
| `hivemind/server/tools/add_knowledge.py` | 50 | 183 | VERIFIED | add_knowledge MCP tool, full security pipeline |
| `hivemind/server/tools/search_knowledge.py` | 60 | 284 | VERIFIED | search_knowledge MCP tool, dual mode, cosine_distance, summary tier, cursor pagination |
| `hivemind/server/tools/list_knowledge.py` | 40 | 209 | VERIFIED | list_knowledge MCP tool, pending+approved, per-agent isolation |
| `hivemind/server/tools/delete_knowledge.py` | 30 | 135 | VERIFIED | delete_knowledge MCP tool, soft-delete, 404-not-403 |
| `hivemind/cli/review.py` | 80 | 285 | VERIFIED | review command, Rich panels with QI badge + similar knowledge section, questionary prompts, all 6 actions, gamification, session summary |
| `hivemind/cli/client.py` | 30 | 340 | VERIFIED | fetch_pending (FOR UPDATE SKIP LOCKED), approve_contribution (embedding gen), reject_contribution, flag_contribution, get_org_stats, find_similar_knowledge (cosine distance query), compute_qi_score (confidence + is_sensitive_flagged + content length) |
| `alembic/versions/001_initial_schema.py` | — | 221 | VERIFIED | CREATE EXTENSION vector, 3 tables, HNSW index, unique(content_hash, org_id) |
| `alembic/versions/002_add_deleted_at.py` | — | 53 | VERIFIED | deleted_at column, partial index WHERE deleted_at IS NULL |
| `hivemind/cli/__init__.py` | — | 26 | VERIFIED | Typer app, review command registered via app.command()(review) |

---

## Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| hivemind/db/session.py | hivemind/config.py | settings.database_url | WIRED | Line 19: from hivemind.config import settings, line 23: settings.database_url |
| alembic/env.py | hivemind/db/models.py | target_metadata = Base.metadata | WIRED | Line 27: from hivemind.db.models import Base, line 29: target_metadata = Base.metadata |
| hivemind/server/main.py | hivemind/pipeline/pii.py | PIIPipeline.get_instance() at lifespan | WIRED | Line 29: import PIIPipeline, line 60: PIIPipeline.get_instance() |
| hivemind/server/main.py | hivemind/pipeline/embedder.py | get_embedder() at lifespan | WIRED | Line 28: import get_embedder, line 65: get_embedder() |
| hivemind/server/tools/add_knowledge.py | hivemind/pipeline/pii.py | strip_pii() before DB insert | WIRED | Line 29: from hivemind.pipeline.pii import strip_pii, line 139: strip_pii(content) before session.add() |
| hivemind/server/tools/add_knowledge.py | hivemind/db/models.py | PendingContribution insert | WIRED | Line 27: import PendingContribution, lines 159-175: insert to pending_contributions |
| hivemind/server/tools/search_knowledge.py | hivemind/pipeline/embedder.py | get_embedder().embed(query) | WIRED | Line 33: import get_embedder, line 229: get_embedder().embed(query) |
| hivemind/server/tools/search_knowledge.py | hivemind/db/models.py | KnowledgeItem cosine_distance query | WIRED | Line 30: import KnowledgeItem, line 233: KnowledgeItem.embedding.cosine_distance(query_embedding) |
| hivemind/server/tools/delete_knowledge.py | hivemind/db/models.py | KnowledgeItem soft-delete with org_id check | WIRED | Lines 110-113: WHERE org_id == auth.org_id AND source_agent_id == agent_id, line 125: item.deleted_at = now() |
| hivemind/cli/review.py | hivemind/cli/client.py | fetch_pending, approve_contribution, reject_contribution, compute_qi_score, find_similar_knowledge | WIRED | Lines 29-37: all 7 functions imported; compute_qi_score called line 150, find_similar_knowledge called line 155, all rendered in panel_body lines 170/181 |
| hivemind/cli/client.py | hivemind/pipeline/embedder.py | get_embedder().embed() at approval + similarity lookup | WIRED | Line 26: import get_embedder, line 113: embed at approval, line 240: embed in find_similar_knowledge |
| hivemind/server/main.py | hivemind/server/tools/list_knowledge.py | Tool registration import | WIRED | Line 32: import list_knowledge, line 164: mcp.add_tool(Tool.from_function(list_knowledge)) |
| hivemind/server/main.py | hivemind/server/tools/delete_knowledge.py | Tool registration import | WIRED | Line 31: import delete_knowledge, line 165: mcp.add_tool(Tool.from_function(delete_knowledge)) |

---

## Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| MCP-01 | 01-03 | Agent can connect via MCP Streamable HTTP | SATISFIED | main.py: mcp.http_app(transport="streamable-http"), /mcp endpoint, stateless_http=True |
| MCP-02 | 01-03 | Agent can contribute via add_knowledge tool | SATISFIED | add_knowledge.py: full PII-strip -> quarantine pipeline, returns contribution_id |
| MCP-03 | 01-03 | Agent can search via search_knowledge with tiered response | SATISFIED | search_knowledge.py: summary tier (id/title/category/confidence/org_attribution/relevance_score) + fetch mode |
| MCP-04 | 01-04 | Agent can list contributed knowledge via list_knowledge | SATISFIED | list_knowledge.py: pending + approved, per-agent isolation, cursor pagination |
| MCP-05 | 01-04 | Agent can delete own knowledge via delete_knowledge | SATISFIED | delete_knowledge.py: soft-delete via deleted_at, ownership check, 404-not-403 |
| TRUST-01 | 01-02 | All inbound knowledge PII-stripped using Presidio + GLiNER + API secret patterns | SATISFIED | pii.py: AnalyzerEngine + GLiNERRecognizer + 11 PatternRecognizer patterns + typed placeholders |
| TRUST-02 | 01-04 | User notification surfaces quality pre-screening signals and similar existing knowledge | SATISFIED | client.py: compute_qi_score() (confidence + is_sensitive_flagged + content length -> labeled badge) + find_similar_knowledge() (cosine_distance query). Both rendered in review.py panel_body lines 170/181. |
| TRUST-03 | 01-04 | User can approve or reject each contribution before it enters commons | SATISFIED | review.py: questionary prompts for approve (private/public), category override, flag, reject, skip. client.py approve_contribution() moves to knowledge_items. |
| ACL-01 | 01-01, 01-03 | Each org has private namespace isolated from others | SATISFIED | org_id indexed on all tables; search scoped to (org_id == :org_id OR is_public == True); JWT extracts org_id — never from tool args |
| KM-01 | 01-01 | Every item has immutable provenance fields | SATISFIED | models.py: source_agent_id, contributed_at, category, org_id, confidence, run_id, content_hash on both tables. Documented as "set on INSERT and never updated." |
| KM-04 | 01-01 | Knowledge typed by category enum with framework/language/version metadata | SATISFIED | KnowledgeCategory (11 values), framework/language/version on both tables |
| KM-08 | 01-02 | Embedding model pinned at deployment, abstraction layer decouples storage from model version | SATISFIED | embedder.py: EmbeddingProvider ABC + SentenceTransformerProvider. main.py lifespan stores embedding_model_name + embedding_model_revision to deployment_config at startup. |
| INFRA-01 | 01-01 | PostgreSQL + pgvector as primary store | SATISFIED | 001_initial_schema.py: CREATE EXTENSION vector, VECTOR(384) column, HNSW index |
| INFRA-05 | 01-01, 01-04 | Concurrent multi-agent writes handled safely | SATISFIED | client.py fetch_pending(): .with_for_update(skip_locked=True) prevents double-processing. Async engine pool_size=10/max_overflow=20 for concurrent MCP writes. |

**Orphaned requirements (mapped to Phase 1 in REQUIREMENTS.md but not in any plan's requirements field):** None — all 14 required IDs are claimed and implemented.

---

## Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| alembic/versions/001_initial_schema.py | 152 | `sa.Column("embedding", sa.Text, nullable=True)  # placeholder; overridden below` | Info | Intentional: column immediately dropped and replaced with VECTOR(384) via raw SQL on lines 165-168. Not a stub — it's a two-step DDL workaround for pgvector column creation. |

No blockers. No stubs. No empty implementations. No TODO/FIXME comments in production code. New TRUST-02 code scanned and clean.

---

## Human Verification Required

### 1. End-to-End MCP Contribution Flow

**Test:** Start the server (`uvicorn hivemind.server.main:app --host 0.0.0.0 --port 8000`), generate a JWT with `create_token("acme", "agent-1")`, send an MCP request to `add_knowledge` with valid content and category.
**Expected:** Response JSON contains `{"contribution_id": "<uuid>", "status": "queued", ...}`. A row appears in `pending_contributions` with PII-stripped content (raw content not stored).
**Why human:** Requires live PostgreSQL + pgvector, FastMCP HTTP transport, and JWT generation.

### 2. PII Auto-Reject at >50% Threshold

**Test:** Call `add_knowledge` with content that is majority PII (e.g., a list of 20 email addresses and nothing else).
**Expected:** Server returns `isError=True` with "too much content was identified as sensitive and redacted (>50%)" message. No row inserted to pending_contributions.
**Why human:** Requires live Presidio + GLiNER inference; cannot verify placeholder ratio without running the model.

### 3. Semantic Search Returning Ranked Results

**Test:** After approving a contribution via `hivemind review`, call `search_knowledge` with a semantically similar query. Verify the approved item appears in results ranked by relevance_score.
**Expected:** Results include the approved item with a relevance_score close to 1.0. Results from a different org's private items do not appear.
**Why human:** Requires live PostgreSQL, pgvector cosine_distance, and sentence-transformers model.

### 4. CLI Review with QI Badge and Similar Knowledge

**Test:** Run `hivemind review --org-id acme` with a pending contribution and at least one approved item in the DB. Walk through: view panel, verify QI badge appears (e.g., `QI: +++ High (85)`), verify similar items section shows near-duplicate matches or "No similar items" message. Choose "Approve (public commons)".
**Expected:** Rich Panel shows QI badge on meta line, similar knowledge section before agent/timestamp footer. After approval, gamification message appears. Item moves to knowledge_items with is_public=True and embedding populated.
**Why human:** Interactive terminal session required; Rich + questionary need a TTY; requires live DB with both pending and approved items.

### 5. Cross-Org Isolation (404-not-403)

**Test:** Agent from org A calls `delete_knowledge` with an item ID that belongs to org B. Verify the response is a 404-style error (not 403).
**Expected:** `isError=True` with "not found" message. No information about org B's item is revealed.
**Why human:** Requires multi-org test data and a live server session.

---

## Gaps Summary

No gaps. All 15 observable truths are verified. All 14 phase requirement IDs are satisfied. The single TRUST-02 gap from the previous verification has been closed.

**TRUST-02 closure detail:**

The previous verification found that `hivemind review` showed PII-stripped content and confidence but did not surface (a) similar existing knowledge or (b) a quality pre-screening signal beyond the raw confidence number.

Both sub-features are now implemented and wired:

- `find_similar_knowledge()` in `hivemind/cli/client.py` (lines 211-274) embeds the pending contribution using the live sentence-transformers model and runs a cosine distance query against `knowledge_items`, returning the top-3 most similar items above a 65% similarity threshold. Items >= 80% similarity are flagged in yellow as likely duplicates.

- `compute_qi_score()` in `hivemind/cli/client.py` (lines 277-340) synthesises confidence, `is_sensitive_flagged` status, and content length into a 0-100 Quality Index score with a High/Medium/Low badge and icon.

Both outputs are rendered in `review.py`'s panel body before presenting the 6-action questionary prompt.

---

*Verified: 2026-02-18T22:15:00Z*
*Verifier: Claude (gsd-verifier)*
