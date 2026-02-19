# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-02-18)

**Core value:** Agents stop learning alone — when one agent solves a problem, every connected agent benefits
**Current focus:** Phase 2 in progress — 02-02 complete, 02-03 up next

## Current Position

Phase: 2 of 4 (Trust & Security Hardening) — IN PROGRESS
Plan: 2 of 6 in current phase (2 done)
Status: In progress
Last activity: 2026-02-19 — Completed 02-02: ApiKey, AutoApproveRule, WebhookEndpoint models + 3 Alembic migrations

Progress: [███████░░░] 44% (7 of 11 plans done; 7 of ~16 total plans)

## Performance Metrics

**Velocity:**
- Total plans completed: 7
- Average duration: ~4 min
- Total execution time: ~21 min

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 01-agent-connection-loop | 5 | ~17 min | ~3 min |
| 02-trust-security-hardening | 2 | ~4 min | ~2 min |

**Recent Trend:**
- Last 7 plans: 01-01 (~3 min), 01-02 (~3 min), 01-03 (~8 min), 01-04 (~3 min), 01-05 (~3 min), 02-01 (~2 min), 02-02 (~2 min)
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

### Pending Todos

None yet.

### Blockers/Concerns

- [Phase 1]: MCP protocol abstraction layer design needs research — spec evolved rapidly in 2025; v2 breaking changes expected
- [Phase 1]: French-specific PII recognizers (SIRET, SIREN, NIR) have zero native Presidio support — needs research spike
- [Phase 4]: Cold start risk — commons must demonstrate value in first agent session; pre-seeding strategy needed

## Session Continuity

Last session: 2026-02-19
Stopped at: Completed 02-02-PLAN.md — ApiKey, AutoApproveRule, WebhookEndpoint ORM models + Alembic migrations 003-005 + Settings extension
Resume file: .planning/phases/02-trust-security-hardening/02-03-PLAN.md
