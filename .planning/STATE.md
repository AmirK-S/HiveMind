# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-02-18)

**Core value:** Agents stop learning alone — when one agent solves a problem, every connected agent benefits
**Current focus:** Phase 4 in progress — 04-05 complete; LangChain/CrewAI/OpenClaw framework wrappers shipped

## Current Position

Phase: 4 of 4 (Dashboard & Distribution)
Plan: 5 of 6 in current phase (04-05 done)
Status: Phase 4 active — framework wrappers shipped, dashboard + publishing plan remains
Last activity: 2026-02-19 — Completed 04-05: LangChain HiveMindRetriever, CrewAI HiveMindTool, OpenClaw SKILL.md framework wrappers

Progress: [██████████] 96% (19 of ~25 total plans done)

## Performance Metrics

**Velocity:**
- Total plans completed: 17
- Average duration: ~3 min
- Total execution time: ~58 min

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 01-agent-connection-loop | 5 | ~17 min | ~3 min |
| 02-trust-security-hardening | 6 | ~17 min | ~3 min |
| 03-quality-intelligence-sdks | 6 (of 7) | ~24 min | ~4 min |

**Recent Trend:**
- Last 17 plans: 01-01 (~3 min), 01-02 (~3 min), 01-03 (~8 min), 01-04 (~3 min), 01-05 (~3 min), 02-01 (~2 min), 02-02 (~2 min), 02-03 (~4 min), 02-04 (~3 min), 02-05 (~3 min), 02-06 (~3 min), 03-01 (~3 min), 03-02 (~3 min), 03-03 (~4 min), 03-04 (~6 min), 03-05 (~4 min), 03-06 (~4 min)
- Trend: Stable

*Updated after each plan completion*
| Phase 03 P05 | 4 min | 2 tasks | 4 files |
| Phase 03-quality-intelligence-sdks P07 | 8 | 2 tasks | 30 files |
| Phase 04-dashboard-distribution P04 | 2 | 3 tasks | 7 files |

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- [Roadmap]: Phase 1 kept deliberately light (14 reqs) — core MCP loop + basic trust only, no advanced security or access control
- [Roadmap]: Legal/compliance (LEGAL-01 through LEGAL-08) and INFRA-06 (EU data residency) deferred to v2 — ship fast, no European compliance overhead
- [Roadmap]: Trust requirements simplified to product-focused (PII stripping + approval gate) not GDPR formalism
- [Pre-build]: Graphiti + FalkorDB + Presidio + GLiNER + FastAPI + Celery + PostgreSQL/pgvector + Next.js recommended by research
- [01-01]: asyncpg pin changed from <0.29.0 to >=0.30.0 — Python 3.14 cannot build older C extension; 0.31.0 fully compatible with SQLAlchemy 2.x
- [01-01]: Unique constraint on (content_hash, org_id) not just content_hash — allows two orgs to contribute identical knowledge without UniqueViolation
- [01-02]: Post-strip token count used for 50% rejection ratio — pre-strip count would inflate ratio when multi-word names collapse to single [NAME] token
- [01-02]: normalize_embeddings=True enforced at EmbeddingProvider level — pgvector cosine_distance requires unit vectors
- [01-02]: get_embedder() uses lazy settings import to avoid circular dependency between hivemind.pipeline and hivemind.config
- [Phase 01-03]: get_http_headers() from fastmcp.server.dependencies used for Authorization header extraction in tool functions — no middleware+contextvars needed
- [Phase 01-03]: Tool.from_function(fn) is correct FastMCP v2 API for registering plain async functions as MCP tools via mcp.add_tool()
- [Phase 01-03]: Lazy presidio/spacy imports in PIIPipeline.__init__ — Python 3.14 Pydantic v1 incompatibility fixed by deferring import to first instantiation
- [Phase 01-05]: Cosine distance threshold 0.35 (65% similarity) chosen as near-duplicate signal boundary for review panel
- [Phase 01-05]: try/except wraps find_similar_knowledge() in review.py only — keeps client pure, ensures CLI never crashes on embedding failure
- [Phase 01-05]: QI badge is informational only, not a blocker — maintains positive, rewarding tone
- [02-01]: InjectionScanner.is_injection() returns (bool, float) tuple — callers can log confidence score without re-running model
- [02-01]: Fenced code block regex applied before inline regex (Pitfall 5) — prevents triple-backtick markers matching inline single-backtick pattern
- [02-01]: Verbatim PII check threshold is len(pii_value) >= 4 (Pitfall 4) — avoids false positives from single-character PII fragments
- [02-01]: Narrative-only PII analysis in strip() (TRUST-06) — PII inside code blocks is preserved intentionally; stripping it would corrupt code examples
- [02-02]: create_type=False used in 004_auto_approve_rules migration to reference existing knowledgecategory enum — prevents "type already exists" error on upgrade
- [02-02]: WebhookEndpoint.event_types stored as JSONB (not a join table) — subscription lists are small, no relational queries needed in Phase 2 scope
- [02-02]: ApiKey.key_hash has both UniqueConstraint and explicit Index — constraint enforces uniqueness, index provides stable name for future DDL operations
- [Phase 02-trust-security-hardening]: fastapi-limiter 0.2.0 API change: no FastAPILimiter.init(redis); uses pyrate-limiter Limiter objects; init_rate_limiter() stores Redis for ZSET burst detection; endpoint RateLimiter deps in Plan 06
- [Phase 02-trust-security-hardening]: casbin-async-sqlalchemy-adapter strips +asyncpg from database_url; adapter auto-creates casbin_rule table on first load_policy()
- [Phase 02-trust-security-hardening]: seed_default_policies() default-permissive: admin (full *) and contributor (read+write) roles seeded per namespace to prevent lockout of existing orgs
- [02-04]: PgVectorDriver wraps existing query patterns from search_knowledge.py and cli/client.py — no duplication, ABC-compliant wrappers
- [02-04]: FalkorDBDriver raises NotImplementedError on all methods except health_check — prevents accidental use while scaffolding Phase 3
- [02-04]: Lazy imports for graphiti_core inside FalkorDBDriver — optional dep, prevents ImportError when using PgVectorDriver
- [02-04]: dispatch_webhooks uses sync SessionFactory (cli pattern) — called from sync CLI approval flow, not async server context
- [Phase 02-05]: Injection scan runs on raw content before PII strip (Step 1.5) — injection patterns may survive redaction if scanned post-strip
- [Phase 02-05]: check_burst() called with temp uuid4() at Step 1.6 — real contribution_id not available pre-DB commit; temp UUID used for ZSET burst tracking only
- [Phase 02-05]: Auto-approved items set is_public=False — auto-approve means skip queue not public release; orgs control visibility separately
- [Phase 02-05]: Tamper-detected items returned with integrity_warning field (not blocked) — DB corruption vs active attack; operator sees WARNING log
- [Phase 02-trust-security-hardening]: decode_token_async() added as parallel async entry point alongside decode_token() (JWT-only) — avoids modifying existing callers while supporting dual JWT+API-key auth
- [Phase 02-trust-security-hardening]: AuthContext.tier defaults to None — JWT-authenticated contexts remain backward compatible; tier only populated by API key auth
- [Phase 02-trust-security-hardening]: publish_knowledge returns 404 for cross-org items regardless of existence — prevents org discovery via error message difference (ACL-01)
- [Phase 03-01]: signal_metadata attribute (not metadata): SQLAlchemy reserves 'metadata' on DeclarativeBase; ORM attr renamed to signal_metadata while DB column stays 'metadata' via mapped_column('metadata', JSONB)
- [Phase 03-01]: Four explicit nullable DateTime(tz) columns for bi-temporal (not TSTZRANGE): SQLAlchemy DataError friction with DateTimeTZRange; valid_at/invalid_at/expired_at nullable (NULL = no world-time data for existing items)
- [Phase 03-01]: Quality weights as config-time Settings fields (not deployment_config): environment variables only — weight changes require restart, not runtime DB write
- [03-02]: Metering integrated into require_api_key dependency (not Starlette middleware) — same DB session as auth, testable via dependency override, avoids BaseHTTPMiddleware streaming pitfalls
- [03-02]: APIKeyHeader(auto_error=False) used so 401 (not 403) is returned for missing/invalid keys — uniform error message for both absent and invalid API keys
- [03-02]: billing_period_start may be naive UTC — normalised with replace(tzinfo=UTC) before comparison to avoid TypeError on timezone-aware subtraction
- [03-02]: REST layer is thin HTTP adapter over _search/_fetch_by_id — no query logic duplication between MCP and REST surfaces
- [Phase 03-03]: Deduplication check scopes to outcome signal types only — same run can legitimately retrieve multiple items but should not double-report outcomes
- [Phase 03-03]: NULL valid_at items always pass temporal filter (OR condition) — backward compat: pre-migration items treated as always-valid
- [Phase 03-03]: version filter only applied when at_time is also provided — version alone without temporal anchor is ambiguous
- [03-04]: anthropic_api_key as Settings field (empty default) — LLM stages in dedup and conflict resolver degrade gracefully when key absent; HIVEMIND_ANTHROPIC_API_KEY env var
- [03-04]: NOOP returns dict with status=duplicate_detected (not isError) — NOOP is correct behavior (duplicate detected), not an error condition
- [03-04]: VERSION_FORK captures valid_at at resolution time via _fork_valid_at — world-time fork requires new item's valid_at set at resolution not insert time
- [03-04]: FLAGGED_FOR_REVIEW adds conflict_flagged tag — avoids schema change for rare multi-hop conflict edge case; queryable via JSONB tags field
- [03-06]: Celery Beat threshold check lives inside task body — Beat only supports time-based scheduling; condition gates must be task-internal (Pitfall 6)
- [03-06]: Provenance links stored as JSONB tags (provenance_links on canonical, source_item_ids on summaries) — erasure propagation without new DB columns
- [03-06]: PIIPipeline imported lazily inside run_distillation() body — prevents loading spacy/GLiNER (~400MB) at Celery worker startup
- [03-06]: quality_score = 0.6 for distilled summaries — above neutral 0.5 to reward curated content
- [Phase 03-05]: PostgreSQL native to_tsvector/ts_rank chosen over pg_search/pg_textsearch for hybrid search — avoids OS-level extension installation; RRF pattern identical when pg_search added later
- [Phase 03-05]: Quality boost formula: rrf_score * (0.7 + 0.3 * quality_score) computed in SQL — zero Python post-processing meets <200ms P95 target
- [Phase 03-05]: Fire-and-forget asyncio.create_task for retrieval signal recording — non-blocking count tracking preserves search response latency
- [Phase 03-05]: is_version_current derived from expired_at IS NULL in aggregator — reuses existing VERSION_FORK field set by conflict resolver, avoids complex sibling query
- [Phase 03-07]: openapi.json excluded from git via .gitignore — build artifact only, generated SDKs committed
- [Phase 03-07]: scripts/export_openapi.py imports FastAPI app directly — no running server needed for SDK generation, DB/Redis deps bypassed
- [Phase 03-07]: @hey-api/openapi-ts used for TypeScript SDK — actively maintained fork of abandoned openapi-typescript-codegen
- [Phase 04-dashboard-distribution]: HiveMindRetriever uses httpx.AsyncClient() for async implementation to avoid blocking event loop; HiveMindTool._run() returns formatted string for CrewAI chain compatibility; SKILL.md metadata uses single-line JSON per OpenClaw parser limitation
- [04-04]: npx/bin/hivemind.js appends /mcp to base URL before passing to mcp-remote — HiveMind Streamable HTTP endpoint lives at /mcp, users pass clean base URL
- [04-04]: docker-compose uses pgvector/pgvector:pg16 image (not postgres:16 + init script) — pgvector extension pre-installed, zero custom init scripts needed
- [04-04]: Dockerfile HEALTHCHECK uses --start-period=60s — allows GLiNER (~400MB) and sentence-transformers model load before first health check fires

### Pending Todos

None yet.

### Blockers/Concerns

- [Phase 1]: MCP protocol abstraction layer design needs research — spec evolved rapidly in 2025; v2 breaking changes expected
- [Phase 1]: French-specific PII recognizers (SIRET, SIREN, NIR) have zero native Presidio support — needs research spike
- [Phase 4]: Cold start risk — commons must demonstrate value in first agent session; pre-seeding strategy needed

## Session Continuity

Last session: 2026-02-19
Stopped at: Completed 04-05-PLAN.md — LangChain HiveMindRetriever, CrewAI HiveMindTool, and OpenClaw SKILL.md framework wrappers
Resume file: .planning/phases/04-dashboard-distribution/04-06-PLAN.md
