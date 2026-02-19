# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-02-18)

**Core value:** Agents stop learning alone — when one agent solves a problem, every connected agent benefits
**Current focus:** Phase 3 in progress — 2 of 7 plans done; REST API layer complete

## Current Position

Phase: 3 of 4 (Quality Intelligence & SDKs)
Plan: 2 of 7 in current phase (2 done)
Status: In progress
Last activity: 2026-02-19 — Completed 03-02: REST API layer at /api/v1/ with X-API-Key auth, usage metering, knowledge search/fetch/outcomes endpoints

Progress: [█████████░] 73% (13 of ~18 total plans done)

## Performance Metrics

**Velocity:**
- Total plans completed: 13
- Average duration: ~3 min
- Total execution time: ~40 min

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 01-agent-connection-loop | 5 | ~17 min | ~3 min |
| 02-trust-security-hardening | 6 | ~17 min | ~3 min |
| 03-quality-intelligence-sdks | 2 (of 7) | ~6 min | ~3 min |

**Recent Trend:**
- Last 13 plans: 01-01 (~3 min), 01-02 (~3 min), 01-03 (~8 min), 01-04 (~3 min), 01-05 (~3 min), 02-01 (~2 min), 02-02 (~2 min), 02-03 (~4 min), 02-04 (~3 min), 02-05 (~3 min), 02-06 (~3 min), 03-01 (~3 min), 03-02 (~3 min)
- Trend: Stable

*Updated after each plan completion*

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

### Pending Todos

None yet.

### Blockers/Concerns

- [Phase 1]: MCP protocol abstraction layer design needs research — spec evolved rapidly in 2025; v2 breaking changes expected
- [Phase 1]: French-specific PII recognizers (SIRET, SIREN, NIR) have zero native Presidio support — needs research spike
- [Phase 4]: Cold start risk — commons must demonstrate value in first agent session; pre-seeding strategy needed

## Session Continuity

Last session: 2026-02-19
Stopped at: Completed 03-01-PLAN.md — Quality infrastructure: migration 006, QualitySignal model, compute_quality_score(), signal recording helpers, Phase 3 config
Resume file: .planning/phases/03-quality-intelligence-sdks/ (Phase 3 — plan 02 next)
