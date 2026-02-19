---
phase: 04-dashboard-distribution
plan: 06
subsystem: api
tags: [smithery, glama, mcp-discovery, vhs, demo, distribution, well-known]

# Dependency graph
requires:
  - phase: 04-dashboard-distribution plan 04
    provides: FastAPI app entry point (hivemind/server/main.py), README.md base structure
  - phase: 01-agent-connection-loop
    provides: 7 MCP tools (add_knowledge, search_knowledge, list_knowledge, delete_knowledge, publish_knowledge, manage_roles, report_outcome)
provides:
  - Smithery server-card.json endpoint at /.well-known/mcp/server-card.json listing all 7 MCP tools
  - glama.json in repo root for Glama.ai automatic directory indexing
  - scripts/demo.tape: VHS tape for reproducible 30-second demo GIF showing contribute-search-feedback loop
  - README demo section with demo.gif reference and regeneration instructions
  - README MCP Directory Listings section with actionable submission instructions for 7 directories
affects: [deployment, publishing, distribution, 04-04-distribution]

# Tech tracking
tech-stack:
  added:
    - VHS tape format (scripts/demo.tape) for reproducible terminal demo GIFs
  patterns:
    - Well-known path registration: well_known_router mounted on top-level FastAPI app (not api_router) to serve /.well-known/ root paths
    - Smithery server-card.json: JSON endpoint describing server capabilities for MCP directory indexing

key-files:
  created:
    - hivemind/api/routes/well_known.py
    - glama.json
    - scripts/demo.tape
  modified:
    - hivemind/server/main.py
    - README.md

key-decisions:
  - "well_known_router registered on top-level FastAPI app (not api_router) — /.well-known/ is a root path outside /api/v1/ prefix scope"
  - "well_known_router registered BEFORE app.mount('/mcp') — FastAPI route registration order matters; routes registered after mount may be shadowed"
  - "VHS demo tape uses curl REST calls instead of real MCP client calls — REST/MCP parity from Phase 3 means this demonstrates identical workflow; VHS cannot spawn an interactive MCP client session"
  - "glama.json maintainers field uses placeholder 'your-github-username' — no git remote configured; operator must update before push"

patterns-established:
  - "Well-known path pattern: mount on top-level app before MCP ASGI mount to avoid route shadowing"

requirements-completed: [DIST-04, DIST-06, DIST-09]

# Metrics
duration: 5min
completed: 2026-02-19
---

# Phase 04 Plan 06: MCP Discovery & Demo Summary

**Smithery server-card.json at /.well-known/mcp/server-card.json, glama.json for Glama.ai auto-indexing, VHS demo tape for reproducible 30-second contribute-search-feedback demo, and README with actionable submission instructions for all 7 MCP directories**

## Performance

- **Duration:** 5 min
- **Started:** 2026-02-19T13:43:43Z
- **Completed:** 2026-02-19T13:49:00Z
- **Tasks:** 2 of 3 (Task 3 is a human-action checkpoint)
- **Files modified:** 5

## Accomplishments

- Smithery discovery endpoint: `GET /.well-known/mcp/server-card.json` served by FastAPI, listing all 7 MCP tools with authentication details
- Glama.ai automatic indexing: `glama.json` in repo root triggers automatic discovery when pushed to main
- VHS demo tape at `scripts/demo.tape` produces reproducible 30-second demo GIF showing contribute-search-feedback loop via REST API (equivalent to MCP tool calls)
- README updated with demo section (demo.gif reference + `vhs scripts/demo.tape` regeneration command) and MCP Directory Listings section with step-by-step submission instructions for all 7 directories

## Task Commits

Each task was committed atomically:

1. **Task 1: Smithery server-card.json endpoint + Glama.ai config** - `bac4ad5` (feat)
2. **Task 2: VHS demo tape + README demo section** - `9f1443a` (feat)
3. **Task 3: Submit to MCP discovery directories** - PENDING (human-action checkpoint)

**Plan metadata:** *(docs commit follows)*

## Files Created/Modified

- `hivemind/api/routes/well_known.py` - FastAPI router serving Smithery server-card.json at /.well-known/mcp/server-card.json
- `hivemind/server/main.py` - Added well_known_router import and registration on top-level app
- `glama.json` - Glama.ai server configuration for automatic directory indexing
- `scripts/demo.tape` - VHS tape file for reproducible demo GIF (Output scripts/demo.gif directive)
- `README.md` - Added Demo section with demo.gif reference and MCP Directory Listings section with 7 submission instructions

## Decisions Made

- `well_known_router` registered on top-level FastAPI `app` directly (not on `api_router`) — the `/.well-known/` path is a root path outside the `/api/v1/` prefix scope, so it must be on the top-level app
- Router registered BEFORE `app.mount("/mcp", _mcp_app)` — FastAPI route ordering matters; routes registered after an ASGI mount could be shadowed
- VHS demo uses curl REST calls instead of an actual MCP client — REST/MCP parity from Phase 3 ensures this demonstrates the identical workflow that agents execute via MCP; VHS cannot spawn interactive MCP client sessions

## Deviations from Plan

None - plan executed exactly as written for the two automated tasks.

## Issues Encountered

None.

## User Setup Required

**Before pushing to GitHub:** Update `glama.json` with your actual GitHub username:
```json
{
  "$schema": "https://glama.ai/mcp/schemas/server.json",
  "maintainers": ["your-actual-github-username"]
}
```

**After pushing to main:** Claim the Glama.ai listing at https://glama.ai/mcp/servers

**To generate the demo GIF:** Run `vhs scripts/demo.tape` with VHS, ffmpeg, and ttyd installed. See https://github.com/charmbracelet/vhs for installation.

**To submit to MCP directories:** See the MCP Directory Listings section in README.md for step-by-step instructions for all 7 directories.

## Next Phase Readiness

- All automated discovery artifacts are complete and committed
- Task 3 (directory submissions) is a human-action checkpoint — see checkpoint details in CHECKPOINT REACHED section
- Phase 04 is now complete on the automated side — only external submissions remain

## Self-Check: PASSED

| Check | Result |
|-------|--------|
| hivemind/api/routes/well_known.py | FOUND |
| glama.json | FOUND |
| scripts/demo.tape | FOUND |
| README.md demo.gif reference | FOUND |
| README.md MCP Directory Listings | FOUND |
| well_known_router in main.py | FOUND |
| Commit bac4ad5 (Task 1) | FOUND |
| Commit 9f1443a (Task 2) | FOUND |

---
*Phase: 04-dashboard-distribution*
*Completed: 2026-02-19*
