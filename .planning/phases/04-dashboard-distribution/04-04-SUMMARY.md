---
phase: 04-dashboard-distribution
plan: 04
subsystem: infra
tags: [npm, npx, docker, mcp, mcp-remote, dockerfile, docker-compose, readme, distribution]

# Dependency graph
requires:
  - phase: 01-agent-connection-loop
    provides: hivemind.server.main:app FastAPI entry point (uvicorn CMD target)
  - phase: 03-quality-intelligence-sdks
    provides: pyproject.toml + uv.lock dependency definitions used by Dockerfile uv sync
provides:
  - npx hivemind-mcp one-liner: stdio-to-HTTP MCP proxy package ready for npm publish
  - Dockerfile: multi-stage production image (python:3.12-slim + uv + uvicorn)
  - docker-compose.yml: full dev stack (hivemind + pgvector/pgvector:pg16 + redis:7-alpine)
  - README.md: MCP client configs for Claude Desktop, Cursor, VS Code, ChatGPT Desktop, Windsurf, Gemini CLI
affects: [04-05-dashboard, 04-06-publishing, deployment, onboarding]

# Tech tracking
tech-stack:
  added:
    - mcp-remote (npm package — stdio-to-HTTP proxy for MCP clients)
    - hivemind-mcp (new npm package wrapping mcp-remote)
    - pgvector/pgvector:pg16 (Docker image with pgvector extension pre-installed)
    - redis:7-alpine (Docker image for Celery + rate limiting)
  patterns:
    - Multi-stage Docker build: builder stage with uv sync, runtime stage copies .venv only
    - stdio-to-HTTP proxy pattern: MCP clients connect via npx wrapper that spawns mcp-remote
    - Environment variable config with CLI arg fallback (HIVEMIND_URL / HIVEMIND_API_KEY)
    - Signal forwarding (SIGINT/SIGTERM) from wrapper to child process for clean shutdown

key-files:
  created:
    - npx/package.json
    - npx/bin/hivemind.js
    - npx/README.md
    - Dockerfile
    - docker-compose.yml
    - .dockerignore
    - README.md
  modified: []

key-decisions:
  - "npx/bin/hivemind.js uses spawn('npx', ['-y', 'mcp-remote', url+'/mcp']) pattern — delegates proxy work to mcp-remote, keeps wrapper minimal"
  - "Dockerfile builder stage uses uv sync --frozen --no-dev — reproducible builds locked to uv.lock, dev deps excluded from image"
  - "docker-compose postgres service uses pgvector/pgvector:pg16 image (not postgres:16 + manual extension) — pgvector pre-installed, no init scripts needed"
  - "README uses 6 separate mcpServers snippets (one per client) with client-specific config file paths — copy-paste ready, zero extra config"
  - ".dockerignore excludes .env, .planning, .venv, deep_research, sdks, node_modules — secrets and dev artifacts never enter image"

patterns-established:
  - "npm wrapper pattern: thin Node.js script parses env/args then delegates to mcp-remote via spawn"
  - "Docker healthcheck via /health endpoint: curl -f http://localhost:8000/health polls every 30s"
  - "Compose service dependency ordering: hivemind depends_on postgres with condition: service_healthy"

requirements-completed: [DIST-01, DIST-02, DIST-03]

# Metrics
duration: 2min
completed: 2026-02-19
---

# Phase 04 Plan 04: Distribution Artifacts Summary

**npx hivemind-mcp stdio-to-HTTP proxy via mcp-remote, multi-stage Dockerfile with uv + python:3.12-slim, and README with copy-paste configs for 6 MCP clients (Claude Desktop, Cursor, VS Code, ChatGPT Desktop, Windsurf, Gemini CLI)**

## Performance

- **Duration:** 2 min
- **Started:** 2026-02-19T13:35:03Z
- **Completed:** 2026-02-19T13:37:29Z
- **Tasks:** 3
- **Files created:** 7

## Accomplishments

- npx package (`hivemind-mcp`) ready for `npm publish` with CLI entry point that proxies stdio to HiveMind HTTP via mcp-remote, supporting both CLI args and env vars
- Multi-stage Dockerfile producing minimal runtime image using uv for reproducible dependency installation, with full docker-compose dev stack (hivemind + pgvector + redis)
- README.md with sub-5-minute onboarding path via 6 MCP client config snippets (each with client-specific file paths and JSON snippets)

## Task Commits

Each task was committed atomically:

1. **Task 1: npx hivemind-mcp one-liner wrapper package** - `54e4dcd` (feat)
2. **Task 2: Multi-stage Dockerfile + docker-compose + .dockerignore** - `5b8a8cc` (feat)
3. **Task 3: MCP client configuration snippets in README** - `405e64e` (feat)

**Plan metadata:** *(docs commit follows)*

## Files Created/Modified

- `npx/package.json` - npm package definition with bin entry pointing to hivemind-mcp
- `npx/bin/hivemind.js` - CLI entry point: parses URL/API key from env or argv, spawns mcp-remote with SIGINT/SIGTERM forwarding
- `npx/README.md` - npm package README with quick start, env config, and MCP client snippet
- `Dockerfile` - 2-stage build (builder: uv sync --frozen --no-dev; runtime: copy .venv + hivemind/ + alembic/)
- `docker-compose.yml` - Full stack: hivemind + pgvector/pgvector:pg16 + redis:7-alpine, postgres healthcheck before hivemind starts
- `.dockerignore` - Excludes .env, .planning, .venv, node_modules, deep_research, sdks, build artifacts
- `README.md` - Project overview, quick start, 6 MCP client configs with file paths, Docker setup, tool table

## Decisions Made

- `npx/bin/hivemind.js` appends `/mcp` to the base URL before passing to mcp-remote — the HiveMind Streamable HTTP endpoint lives at `/mcp`, but users should pass only the base URL (cleaner UX)
- Dockerfile uses `pgvector/pgvector:pg16` in docker-compose rather than `postgres:16-alpine` — avoids the need for custom init scripts to enable the pgvector extension
- `--start-period=60s` added to Dockerfile HEALTHCHECK — allows time for GLiNER (~400MB) and sentence-transformers model loading before first health check

## Deviations from Plan

None — plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None — no external service configuration required. Users self-configure `HIVEMIND_URL` and `HIVEMIND_API_KEY` in their MCP client config files.

## Next Phase Readiness

- npx package ready for `npm publish hivemind-mcp` (verify name availability first: `npm info hivemind-mcp`)
- Docker image ready for `docker build -t hivemind .` and push to registry
- README provides complete onboarding for all 6 major MCP clients
- Phase 04 plans 05 and 06 can proceed (dashboard and publishing)

## Self-Check: PASSED

All created files verified on disk. All task commits verified in git log.

| Check | Result |
|-------|--------|
| npx/package.json | FOUND |
| npx/bin/hivemind.js | FOUND |
| npx/README.md | FOUND |
| Dockerfile | FOUND |
| docker-compose.yml | FOUND |
| .dockerignore | FOUND |
| README.md | FOUND |
| 04-04-SUMMARY.md | FOUND |
| Commit 54e4dcd (Task 1) | FOUND |
| Commit 5b8a8cc (Task 2) | FOUND |
| Commit 405e64e (Task 3) | FOUND |
| Commit 481df76 (metadata) | FOUND |

---
*Phase: 04-dashboard-distribution*
*Completed: 2026-02-19*
