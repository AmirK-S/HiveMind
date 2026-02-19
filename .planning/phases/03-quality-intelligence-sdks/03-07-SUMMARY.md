---
phase: 03-quality-intelligence-sdks
plan: 07
subsystem: api
tags: [openapi, sdk, python, typescript, openapi-python-client, hey-api, makefile]

# Dependency graph
requires:
  - phase: 03-02
    provides: REST API with search, fetch, and outcome reporting endpoints
  - phase: 03-03
    provides: Outcome reporting endpoint for quality signals

provides:
  - Python SDK (hive-mind-client) with AuthenticatedClient and typed methods for search_knowledge, get_knowledge_item, report_outcome
  - TypeScript SDK with typed fetch-based functions (searchKnowledge, getKnowledgeItem, reportOutcome)
  - scripts/export_openapi.py for spec export without running server
  - Makefile with generate-sdks, generate-openapi, generate-python-sdk, generate-ts-sdk, check-sdk-drift targets

affects: [phase-04, sdk-consumers, ci-pipelines]

# Tech tracking
tech-stack:
  added: [openapi-python-client==0.28.2, "@hey-api/openapi-ts>=0.92.4"]
  patterns: [generated-sdks, spec-first-api, sdk-drift-detection, makefile-generation-targets]

key-files:
  created:
    - scripts/export_openapi.py
    - sdks/python/hive_mind_client/api/rest_api/search_knowledge.py
    - sdks/python/hive_mind_client/api/rest_api/get_knowledge_item.py
    - sdks/python/hive_mind_client/api/rest_api/report_outcome.py
    - sdks/python/hive_mind_client/client.py
    - sdks/python/README.md
    - sdks/typescript/src/client/sdk.gen.ts
    - sdks/typescript/src/client/types.gen.ts
    - sdks/typescript/README.md
    - Makefile
    - .gitignore
  modified:
    - pyproject.toml

key-decisions:
  - "openapi-python-client 0.28.2 used (latest stable) — installs to .venv alongside project deps via pip install; uv skipped due to missing README.md build artifact"
  - "@hey-api/openapi-ts 0.92.4 used via npx (latest) — not openapi-typescript-codegen which is abandoned"
  - "scripts/export_openapi.py imports FastAPI app directly — no running server needed for SDK generation (avoids DB/Redis dependency)"
  - "openapi.json excluded from version control via .gitignore — it is a build artifact, only generated SDKs are committed"
  - "Makefile uses .venv/bin/python and .venv/bin/openapi-python-client — explicit venv paths avoid PATH issues in CI"
  - "check-sdk-drift Makefile target uses git diff --exit-code to fail CI when SDK commits are stale"

patterns-established:
  - "Spec-first SDK: export spec statically from FastAPI app, generate SDKs, never hand-write client code"
  - "SDK drift detection: check-sdk-drift CI target regenerates and diffs to catch stale committed SDKs"
  - "Operation ID pattern: explicit operation_id on each FastAPI endpoint ensures clean SDK method names"

requirements-completed: [SDK-02, SDK-03]

# Metrics
duration: 8min
completed: 2026-02-19
---

# Phase 03 Plan 07: SDK Generation Summary

**Python and TypeScript SDKs auto-generated from OpenAPI spec via openapi-python-client and @hey-api/openapi-ts, with Makefile targets for one-command regeneration and CI drift detection**

## Performance

- **Duration:** 8 min
- **Started:** 2026-02-19T12:38:36Z
- **Completed:** 2026-02-19T12:46:42Z
- **Tasks:** 2
- **Files modified:** 30+

## Accomplishments
- Python SDK (hive-mind-client) generated with AuthenticatedClient and typed methods: search_knowledge, get_knowledge_item, report_outcome
- TypeScript SDK generated with typed fetch functions: searchKnowledge, getKnowledgeItem, reportOutcome — all using X-API-Key header auth
- scripts/export_openapi.py exports spec from FastAPI app without a running server (no DB/Redis required)
- Makefile provides generate-sdks, check-sdk-drift for one-command SDK regeneration and CI enforcement

## Task Commits

Each task was committed atomically:

1. **Task 1: OpenAPI spec polish and Python SDK generation** - `ce0f7d4` (feat)
2. **Task 2: TypeScript SDK generation and Makefile target** - `dcc7806` (feat)

## Files Created/Modified
- `scripts/export_openapi.py` - Exports OpenAPI spec from FastAPI app without running server
- `sdks/python/hive_mind_client/` - Generated Python SDK package with typed client and API methods
- `sdks/python/README.md` - Python SDK usage docs with search, fetch, and outcome examples
- `sdks/typescript/src/client/sdk.gen.ts` - Generated TypeScript SDK with searchKnowledge, getKnowledgeItem, reportOutcome
- `sdks/typescript/src/client/types.gen.ts` - Generated TypeScript type definitions
- `sdks/typescript/README.md` - TypeScript SDK usage docs
- `sdks/typescript/package.json` - TypeScript SDK package definition
- `Makefile` - SDK generation and drift check targets
- `.gitignore` - Excludes openapi.json build artifact and __pycache__
- `pyproject.toml` - Added openapi-python-client to dev dependencies

## Decisions Made
- `openapi-python-client` installed to `.venv` via pip (uv skipped due to missing README.md hatchling build issue)
- `@hey-api/openapi-ts` used via `npx` — actively maintained fork of abandoned openapi-typescript-codegen (research anti-pattern)
- `scripts/export_openapi.py` imports the FastAPI app directly — no running server required, safe for CI
- `openapi.json` excluded from version control — build artifact only
- Makefile uses explicit `.venv/bin/` paths to avoid PATH ambiguity in CI environments

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Created .gitignore to exclude openapi.json build artifact**
- **Found during:** Task 1 (Python SDK generation)
- **Issue:** No .gitignore existed; openapi.json (build artifact) would have been accidentally committed
- **Fix:** Created .gitignore with openapi.json exclusion per plan specification ("Do NOT include the openapi.json in version control")
- **Files modified:** .gitignore
- **Verification:** git status shows openapi.json not tracked
- **Committed in:** ce0f7d4 (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (1 blocking)
**Impact on plan:** Necessary to prevent build artifact from entering version control. No scope creep.

## Issues Encountered
- `uv run python scripts/export_openapi.py` failed because hatchling requires README.md to build the wheel. Switched to `.venv/bin/python` directly — this is the project's established pattern (all previous plans use `.venv/`).
- `openapi-python-client` not pre-installed — installed via `pip install` to `.venv`. Makefile uses `.venv/bin/openapi-python-client` for CI reproducibility.

## User Setup Required
None - no external service configuration required. SDK generation works fully offline from the FastAPI app import.

## Next Phase Readiness
- Both SDKs ready for Phase 4 agent integration consumers
- `make generate-sdks` can be run after any REST API change to regenerate
- `make check-sdk-drift` ready for CI pipeline integration
- Python SDK installable via `pip install -e sdks/python`
- TypeScript SDK consumable from `sdks/typescript/src/client`

---
*Phase: 03-quality-intelligence-sdks*
*Completed: 2026-02-19*

## Self-Check: PASSED

All files verified present. All commits verified in git log.

| Check | Status |
|---|---|
| scripts/export_openapi.py | FOUND |
| Python SDK search_knowledge.py | FOUND |
| Python SDK get_knowledge_item.py | FOUND |
| Python SDK report_outcome.py | FOUND |
| TypeScript sdk.gen.ts | FOUND |
| Makefile | FOUND |
| 03-07-SUMMARY.md | FOUND |
| Commit ce0f7d4 | FOUND |
| Commit dcc7806 | FOUND |
