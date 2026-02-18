---
phase: 01-agent-connection-loop
plan: "04"
subsystem: api
tags: [fastmcp, mcp, cli, typer, rich, questionary, soft-delete, pgvector, alembic, psycopg2, gamification]

requires:
  - phase: 01-03
    provides: "FastMCP server with JWT auth, add_knowledge and search_knowledge tools, stub list/delete tools"
  - phase: 01-01
    provides: "KnowledgeItem + PendingContribution ORM models, get_session() context manager"
  - phase: 01-02
    provides: "get_embedder() singleton for embedding generation at approval time"

provides:
  - "list_knowledge MCP tool: paginated agent-scoped contributions (pending + approved), filtered by source_agent_id from JWT"
  - "delete_knowledge MCP tool: soft-delete via deleted_at timestamp, scoped by org_id + source_agent_id, 404 for non-owned items"
  - "KnowledgeItem.deleted_at column + Alembic migration 002 (soft-delete infrastructure)"
  - "search_knowledge updated to exclude soft-deleted items (WHERE deleted_at IS NULL)"
  - "hivemind CLI app (Typer) with review command"
  - "CLI sync DB client: fetch_pending (FOR UPDATE SKIP LOCKED), approve_contribution (embedding gen), reject_contribution, flag_contribution, get_org_stats"
  - "hivemind review command: Rich Panel display, questionary prompts, category override, flag/reject/skip, gamification messages, session summary"

affects:
  - "Phase 2+ integration testing (all 4 MCP tools now functional)"
  - "Production deployment (requires psycopg2-binary for CLI)"

tech-stack:
  added:
    - "questionary 2.1.1 — interactive CLI prompts (select, confirm) for review workflow"
    - "psycopg2-binary — sync PostgreSQL driver for CLI (avoids asyncio event loop issues in Typer)"
    - "typer — CLI framework (was in pyproject.toml but not installed in venv; now verified installed)"
    - "rich — already installed; used for Panel + Console display in review"
  patterns:
    - "Sync CLI client pattern: derive sync URL by stripping +asyncpg from settings.database_url → psycopg2 driver"
    - "FOR UPDATE SKIP LOCKED in fetch_pending() — safe concurrent CLI session access to pending queue"
    - "Soft-delete pattern: deleted_at nullable DateTime column, all read queries filter WHERE deleted_at IS NULL"
    - "404-not-403 pattern: delete_knowledge returns 'not found' for items in other orgs — never reveals existence (research pitfall 6)"
    - "Embedding at approval time: generate embedding in approve_contribution() not at contribution time — content only enters commons after human review"

key-files:
  created:
    - "hivemind/server/tools/list_knowledge.py"
    - "hivemind/server/tools/delete_knowledge.py"
    - "alembic/versions/002_add_deleted_at.py"
    - "hivemind/cli/__init__.py"
    - "hivemind/cli/review.py"
    - "hivemind/cli/client.py"
  modified:
    - "hivemind/server/tools/search_knowledge.py"
    - "hivemind/server/main.py"
    - "hivemind/db/models.py"
    - "pyproject.toml"

key-decisions:
  - "psycopg2-binary added as explicit dependency for sync CLI DB access — asyncpg is async-only and cannot be used in synchronous Typer commands"
  - "Engine creation in client.py is module-level (not lazy) — clear initialization boundary; psycopg2 availability is now guaranteed by explicit dependency"
  - "list_knowledge merges pending+approved in Python (not SQL UNION) for simplicity — acceptable for Phase 1 scale, can optimize to SQL UNION in Phase 2 if needed"
  - "Embedding generated at approve_contribution() time (not at add_knowledge() time) — ensures only human-reviewed content receives embeddings and enters the searchable commons"
  - "Partial index ix_knowledge_items_deleted_at_null added in migration 002 — scoped to org_id WHERE deleted_at IS NULL, matches the most common search filter pattern"

patterns-established:
  - "Sync CLI client pattern: strip +asyncpg from database_url for psycopg2 sync engine — avoids asyncio event loop errors in Typer commands"
  - "Soft-delete everywhere pattern: any read query on knowledge_items must include .where(KnowledgeItem.deleted_at.is_(None))"
  - "404-not-403 for cross-org resource access: never reveal item existence in another org's namespace"
  - "FOR UPDATE SKIP LOCKED in CLI queue fetcher: prevents duplicate processing when multiple operators run review simultaneously"

requirements-completed:
  - MCP-04
  - MCP-05
  - TRUST-02
  - TRUST-03

duration: 9min
completed: 2026-02-18
---

# Phase 01 Plan 04: list_knowledge + delete_knowledge MCP tools + CLI approval workflow Summary

**Two new MCP tools (list_knowledge, delete_knowledge) completing the 4-tool surface, plus hivemind review CLI command with Rich/questionary approval workflow, soft-delete infrastructure, and embedding-at-approval pattern closing the full contribute/approve/retrieve loop**

## Performance

- **Duration:** 9 min
- **Started:** 2026-02-18T21:25:22Z
- **Completed:** 2026-02-18T21:34:00Z
- **Tasks:** 2
- **Files modified:** 10 (6 created, 4 modified)

## Accomplishments

- `list_knowledge` MCP tool: agents can see their own pending + approved contributions with status, category, and cursor pagination. Filtered by both org_id and source_agent_id from JWT — per-agent isolation, not just per-org.
- `delete_knowledge` MCP tool: soft-deletes approved items via `deleted_at` timestamp (not physical removal). Scoped by org_id + source_agent_id. Returns 404 (not 403) for items in other orgs, per research pitfall 6 (don't reveal cross-org item existence). Migration 002 adds the `deleted_at` column with a partial index on active items.
- `hivemind review` CLI command: operators walk through pending contributions in Rich Panels showing clean PII-stripped content. questionary drives approve/reject/flag/skip prompts. Category override available on approval. Gamification message after each approval shows total contributions and agent reach. Session summary at end. Sync DB client uses FOR UPDATE SKIP LOCKED to handle concurrent sessions safely.

## Task Commits

Each task was committed atomically:

1. **Task 1: list_knowledge and delete_knowledge MCP tools** - `ef3a1b4` (feat)
2. **Task 2: CLI approval workflow with Typer + Rich + questionary** - `2c87d8d` (feat)

**Plan metadata:** (see final docs commit)

## Files Created/Modified

- `hivemind/server/tools/list_knowledge.py` - list_knowledge MCP tool: paginated agent contributions (pending + approved), source_agent_id auth filter, cursor pagination
- `hivemind/server/tools/delete_knowledge.py` - delete_knowledge MCP tool: soft-delete with org_id + source_agent_id ownership check, 404 for non-owned items
- `alembic/versions/002_add_deleted_at.py` - Migration: deleted_at nullable DateTime column + partial index WHERE deleted_at IS NULL on org_id
- `hivemind/cli/__init__.py` - Typer app with review command registered, entry point for hivemind CLI
- `hivemind/cli/review.py` - review command: Rich Panel display, questionary action prompts, approve/category-override/flag/reject/skip flow, gamification messages, session summary
- `hivemind/cli/client.py` - Sync DB client: fetch_pending (FOR UPDATE SKIP LOCKED), approve_contribution (embedding gen + promotion), reject_contribution, flag_contribution, get_org_stats
- `hivemind/server/tools/search_knowledge.py` (modified) - Added `WHERE deleted_at IS NULL` filter to both search mode and fetch mode
- `hivemind/server/main.py` (modified) - Replaced list_knowledge and delete_knowledge stubs with real module imports
- `hivemind/db/models.py` (modified) - Added deleted_at nullable DateTime column to KnowledgeItem model
- `pyproject.toml` (modified) - Added psycopg2-binary as explicit dependency for sync CLI DB access

## Decisions Made

- psycopg2-binary added as an explicit dependency — asyncpg is async-only and causes "asyncio event loop is not running" errors when called from synchronous Typer commands. Using psycopg2 for CLI is the clean separation: async engine for the MCP server, sync engine for CLI.
- The sync URL is derived from `settings.database_url` by stripping `+asyncpg` — no separate config field needed. This reuses the same host/port/credentials while switching drivers.
- list_knowledge merges pending and approved results in Python (two separate queries, concatenate, then paginate) rather than a SQL UNION. For Phase 1 scale this is simpler and more maintainable. SQL UNION optimization deferred to Phase 2 if query times become an issue.
- Embedding generation happens at `approve_contribution()` time, not at `add_knowledge()` time. This means only human-reviewed content enters the searchable commons with embeddings — consistent with the trust model (PII-stripped + human-approved = safe to embed and surface to other agents).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] psycopg2 not installed in project venv**
- **Found during:** Task 2 (CLI client import verification)
- **Issue:** `client.py` creates a sync SQLAlchemy engine at module level using `postgresql://` URL (psycopg2 driver). On import, Python immediately tries to import psycopg2. It was not installed — only asyncpg was in the venv.
- **Fix:** Installed `psycopg2-binary` via pip and added it to `pyproject.toml` as an explicit dependency so it is installed automatically in future environments.
- **Files modified:** `pyproject.toml`
- **Verification:** `from hivemind.cli import app` imports successfully without error.
- **Committed in:** `2c87d8d` (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (Rule 3 - blocking)
**Impact on plan:** psycopg2-binary is a required dependency for any sync DB access from the CLI. Adding it to pyproject.toml is the correct fix — no scope creep, no architectural change.

## Issues Encountered

- hatchling editable install (`pip install -e .`) fails due to `AttributeError: module 'hatchling.build' has no attribute 'prepare_metadata_for_build_editable'` — this is a pre-existing environment issue (hatchling version incompatibility with Python 3.14). It does not block CLI functionality since all imports work via PYTHONPATH. Deferred to Phase 2 (infrastructure/packaging).

## User Setup Required

None - no external service configuration required for this plan. CLI requires a running PostgreSQL database (same requirement as the MCP server). Set `HIVEMIND_ORG_ID` in the environment or pass `--org-id` to the review command.

## Next Phase Readiness

- All 4 MCP tools registered and functional: `add_knowledge`, `search_knowledge`, `list_knowledge`, `delete_knowledge`
- Full Phase 1 loop closeable: agent contributes via add_knowledge → operator reviews via `hivemind review` → approved knowledge is embedded and searchable via search_knowledge
- `hivemind review --help` shows command with `--org-id` option and all actions documented
- Soft-delete infrastructure in place: `deleted_at` column, migration 002, and all read paths updated
- Phase 1 complete — ready for Phase 2 planning (agent-to-agent knowledge sharing, advanced trust features, or production hardening)

---
*Phase: 01-agent-connection-loop*
*Completed: 2026-02-18*
