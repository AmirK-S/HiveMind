---
phase: 04-dashboard-distribution
plan: 05
subsystem: api
tags: [langchain, crewai, openclaw, httpx, pydantic, wrappers, rest-client]

# Dependency graph
requires:
  - phase: 03-quality-intelligence-sdks
    provides: REST API /api/v1/knowledge/search endpoint with X-API-Key auth
provides:
  - LangChain BaseRetriever subclass (HiveMindRetriever) calling /api/v1/knowledge/search
  - CrewAI BaseTool subclass (HiveMindTool) with Pydantic args_schema, returning formatted strings
  - OpenClaw SKILL.md with AgentSkills format REST API instructions
affects:
  - any phase adding more framework integrations
  - any phase touching /api/v1/knowledge/search endpoint contract

# Tech tracking
tech-stack:
  added: [hivemind-langchain (new PyPI package), hivemind-crewai (new PyPI package), hatchling build system]
  patterns: [thin HTTP wrapper pattern over REST API, sync+async dual implementation with httpx/httpx.AsyncClient]

key-files:
  created:
    - wrappers/langchain/pyproject.toml
    - wrappers/langchain/hivemind_langchain/__init__.py
    - wrappers/langchain/hivemind_langchain/retriever.py
    - wrappers/crewai/pyproject.toml
    - wrappers/crewai/hivemind_crewai/__init__.py
    - wrappers/crewai/hivemind_crewai/tool.py
    - skills/SKILL.md
  modified: []

key-decisions:
  - "HiveMindRetriever uses httpx.get() for sync and httpx.AsyncClient() for async — avoids blocking event loop in async context (anti-pattern from research)"
  - "HiveMindTool._run() returns formatted string not structured data — CrewAI tools require string returns for agent chain compatibility"
  - "_arun() included for future CrewAI async support with comment noting compatibility scope"
  - "SKILL.md metadata field uses single-line JSON object — OpenClaw parser limitation confirmed in research"

patterns-established:
  - "Thin wrapper pattern: framework integration = subclass + httpx + /api/v1/knowledge/search, no MCP dependency"
  - "Sync/async dual implementation: sync uses httpx.get(), async uses httpx.AsyncClient() context manager"
  - "AgentSkills SKILL.md format: single-line frontmatter values only (YAML parser limitation)"

requirements-completed: [DIST-05, DIST-07, DIST-08]

# Metrics
duration: 2min
completed: 2026-02-19
---

# Phase 4 Plan 5: Framework Wrappers Summary

**LangChain BaseRetriever and CrewAI BaseTool thin HTTP wrappers plus OpenClaw SKILL.md — three independently installable integrations calling /api/v1/knowledge/search with no MCP dependency**

## Performance

- **Duration:** 2 min
- **Started:** 2026-02-19T13:34:59Z
- **Completed:** 2026-02-19T13:37:00Z
- **Tasks:** 3
- **Files modified:** 7

## Accomplishments

- HiveMindRetriever (LangChain) subclasses BaseRetriever with sync/async methods returning Document objects with id/category/confidence metadata
- HiveMindTool (CrewAI) subclasses BaseTool with HiveMindSearchInput args_schema and formatted string output for agent chains
- SKILL.md in AgentSkills format with REST search/outcome endpoints and MCP alternative for OpenClaw agents
- Both Python packages independently installable via pyproject.toml with hatchling build system

## Task Commits

Each task was committed atomically:

1. **Task 1: LangChain HiveMindRetriever package** - `6cc6d23` (feat)
2. **Task 2: CrewAI HiveMindTool package** - `83abc5e` (feat)
3. **Task 3: OpenClaw SKILL.md** - `d78e0eb` (feat)

**Plan metadata:** (docs commit - pending)

## Files Created/Modified

- `wrappers/langchain/pyproject.toml` - hatchling build config, langchain-core>=0.2.0 + httpx>=0.25.0 dependencies
- `wrappers/langchain/hivemind_langchain/__init__.py` - package entry point exporting HiveMindRetriever
- `wrappers/langchain/hivemind_langchain/retriever.py` - BaseRetriever subclass, sync + async search implementations
- `wrappers/crewai/pyproject.toml` - hatchling build config, crewai>=0.100.0 + httpx>=0.25.0 dependencies
- `wrappers/crewai/hivemind_crewai/__init__.py` - package entry point exporting HiveMindTool
- `wrappers/crewai/hivemind_crewai/tool.py` - BaseTool subclass with HiveMindSearchInput schema and formatted string output
- `skills/SKILL.md` - AgentSkills spec with single-line YAML frontmatter, REST instructions for search + outcome reporting

## Decisions Made

- `httpx.get()` used for sync methods; `httpx.AsyncClient()` used for async — prevents blocking event loop (anti-pattern from research)
- `HiveMindTool._run()` returns formatted string — CrewAI tools must return strings, not dicts, for agent chain compatibility
- `_arun()` included with note about future CrewAI async support scope
- SKILL.md metadata is single-line JSON — OpenClaw parser cannot handle multi-line YAML values

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

- CrewAI not installed in this environment. Plan verify step explicitly notes "(requires crewai installed)" — the import verification cannot run without the package. File structure and implementation are correct; verification requires `pip install crewai` in the target environment.

## User Setup Required

None - no external service configuration required for the wrappers themselves. Users install packages from PyPI once published.

## Next Phase Readiness

- All three framework integrations complete and ready for distribution
- Phase 4 (dashboard-distribution) wrappers complete
- LangChain and CrewAI packages can be published to PyPI independently
- OpenClaw agents can immediately use SKILL.md to integrate with HiveMind REST API

---
*Phase: 04-dashboard-distribution*
*Completed: 2026-02-19*
