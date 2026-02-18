# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-02-18)

**Core value:** Agents stop learning alone — when one agent solves a problem, every connected agent benefits
**Current focus:** Phase 1 - Agent Connection Loop

## Current Position

Phase: 1 of 4 (Agent Connection Loop)
Plan: 3 of 4 in current phase
Status: In progress
Last activity: 2026-02-18 — Completed 01-03: MCP server + auth + add_knowledge + search_knowledge tools

Progress: [███░░░░░░░] 19% (3 of 4 plans in phase 1; 3 of ~16 total plans)

## Performance Metrics

**Velocity:**
- Total plans completed: 3
- Average duration: ~5 min
- Total execution time: ~14 min

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 01-agent-connection-loop | 3 | ~14 min | ~5 min |

**Recent Trend:**
- Last 5 plans: 01-01 (~3 min), 01-02 (~3 min), 01-03 (~8 min)
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

### Pending Todos

None yet.

### Blockers/Concerns

- [Phase 1]: MCP protocol abstraction layer design needs research — spec evolved rapidly in 2025; v2 breaking changes expected
- [Phase 1]: French-specific PII recognizers (SIRET, SIREN, NIR) have zero native Presidio support — needs research spike
- [Phase 4]: Cold start risk — commons must demonstrate value in first agent session; pre-seeding strategy needed

## Session Continuity

Last session: 2026-02-18
Stopped at: Completed 01-03-PLAN.md — MCP server + auth + add_knowledge + search_knowledge tools
Resume file: .planning/phases/01-agent-connection-loop/01-04-PLAN.md
