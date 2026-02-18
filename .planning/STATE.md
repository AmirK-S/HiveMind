# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-02-18)

**Core value:** Agents stop learning alone — when one agent solves a problem, every connected agent benefits
**Current focus:** Phase 1 complete — Phase 2 planning next

## Current Position

Phase: 1 of 4 (Agent Connection Loop) — COMPLETE
Plan: 5 of 5 in current phase (all plans done)
Status: Phase complete
Last activity: 2026-02-18 — Completed 01-05: TRUST-02 similar knowledge lookup + QI pre-screening badge

Progress: [██████░░░░] 38% (5 of 5 plans in phase 1; 5 of ~16 total plans)

## Performance Metrics

**Velocity:**
- Total plans completed: 5
- Average duration: ~5 min
- Total execution time: ~17 min

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 01-agent-connection-loop | 5 | ~17 min | ~3 min |

**Recent Trend:**
- Last 5 plans: 01-01 (~3 min), 01-02 (~3 min), 01-03 (~8 min), 01-04 (~3 min), 01-05 (~3 min)
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

### Pending Todos

None yet.

### Blockers/Concerns

- [Phase 1]: MCP protocol abstraction layer design needs research — spec evolved rapidly in 2025; v2 breaking changes expected
- [Phase 1]: French-specific PII recognizers (SIRET, SIREN, NIR) have zero native Presidio support — needs research spike
- [Phase 4]: Cold start risk — commons must demonstrate value in first agent session; pre-seeding strategy needed

## Session Continuity

Last session: 2026-02-18
Stopped at: Completed 01-05-PLAN.md — TRUST-02 similar knowledge + QI pre-screening badge in review panel
Resume file: .planning/phases/02-*/02-01-PLAN.md (Phase 2 not yet planned)
