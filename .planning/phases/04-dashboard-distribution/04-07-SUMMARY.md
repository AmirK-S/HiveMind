---
phase: 04-dashboard-distribution
plan: 07
subsystem: distribution
tags: [pypi, mcp, glama, langchain, crewai, npm, distribution]

# Dependency graph
requires:
  - phase: 04-dashboard-distribution
    provides: wrappers for langchain and crewai, npx package config, glama.json
provides:
  - Corrected distribution configs with real GitHub username (AmirK-S) and repo URL
  - glama.json with real maintainer for Glama.ai auto-indexing
  - npx/package.json with real repo URL for npm registry
  - wrappers/langchain/pyproject.toml with real homepage URL
  - wrappers/crewai/pyproject.toml with real homepage URL
  - README.md with real clone URL
affects: [publishing workflow, mcp-directory-submissions, pypi-publishing]

# Tech tracking
tech-stack:
  added: []
  patterns: [real GitHub username AmirK-S used across all distribution manifests]

key-files:
  created: []
  modified:
    - glama.json
    - npx/package.json
    - wrappers/langchain/pyproject.toml
    - wrappers/crewai/pyproject.toml
    - README.md

key-decisions:
  - "AmirK-S/HiveMind is the canonical GitHub identity — all distribution manifests updated to reflect it"

patterns-established:
  - "Distribution config files reference real GitHub identity not placeholder values"

requirements-completed: [DIST-04, DIST-06, DIST-07, DIST-08]

# Metrics
duration: 5min
completed: 2026-02-19
---

# Phase 4 Plan 7: Distribution Config Fixes Summary

**Replaced all your-org/your-github-username placeholders with AmirK-S/HiveMind across glama.json, npx/package.json, both pyproject.toml wrappers, and README.md**

## Performance

- **Duration:** ~5 min
- **Started:** 2026-02-19T14:31:06Z
- **Completed:** 2026-02-19T14:36:00Z
- **Tasks:** 1 of 2 (Task 2 is checkpoint:human-action — awaiting user)
- **Files modified:** 5

## Accomplishments
- glama.json maintainer updated to AmirK-S for Glama.ai auto-indexing on push
- npx/package.json repository URL updated to https://github.com/AmirK-S/HiveMind
- wrappers/langchain/pyproject.toml homepage updated to real repo URL
- wrappers/crewai/pyproject.toml homepage updated to real repo URL
- README.md clone URL updated to https://github.com/AmirK-S/HiveMind.git

## Task Commits

Each task was committed atomically:

1. **Task 1: Fix all placeholder values in distribution configs** - `e226393` (chore)

**Plan metadata:** (pending — final commit after Task 2 human action completes)

## Files Created/Modified
- `glama.json` - Updated maintainers from your-github-username to AmirK-S
- `npx/package.json` - Updated repository URL to https://github.com/AmirK-S/HiveMind
- `wrappers/langchain/pyproject.toml` - Updated Homepage to https://github.com/AmirK-S/HiveMind
- `wrappers/crewai/pyproject.toml` - Updated Homepage to https://github.com/AmirK-S/HiveMind
- `README.md` - Updated git clone URL to https://github.com/AmirK-S/HiveMind.git

## Decisions Made
- AmirK-S is the confirmed GitHub username (from git config email `37595327+AmirK-S@users.noreply.github.com`)
- HiveMind is the repo name (case-sensitive, matching the working directory)

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None

## User Setup Required

**Task 2 requires manual steps.** The following actions must be performed by the user:

### PyPI Publishing

```bash
# Publish hivemind-langchain
cd wrappers/langchain
pip install build twine
python -m build
twine upload dist/*

# Publish hivemind-crewai
cd wrappers/crewai
pip install build twine
python -m build
twine upload dist/*
```

### MCP Directory Submissions (at least 4 of 7)

1. **Glama.ai**: Push repo to GitHub as `AmirK-S/HiveMind`, then claim at https://glama.ai/mcp/servers (auto-indexed via glama.json)
2. **PulseMCP**: Submit at https://pulsemcp.com/submit — name: "HiveMind", description: "Shared knowledge commons for AI agents via MCP", GitHub URL
3. **punkpeye/awesome-mcp-servers**: Open PR at https://github.com/punkpeye/awesome-mcp-servers following CONTRIBUTING.md
4. **Official MCP Registry**: Open PR at https://github.com/modelcontextprotocol/registry following CONTRIBUTING.md
5. **Smithery**: Run `npx smithery mcp publish "https://your-hivemind-instance.com/mcp"` (requires public HTTPS endpoint)
6. **mcp.so**: Submit via https://mcp.so or their GitHub
7. **AwesomeClaude.ai**: Submit via https://awesomeclaude.ai form

After completing at least 4 submissions, update the README MCP Directory Listings table status from "Pending submission" to the actual status (e.g., "Listed", "PR submitted", "Under review").

### Verification

- `pip install hivemind-langchain` succeeds from a clean environment
- `pip install hivemind-crewai` succeeds from a clean environment
- At least 4 MCP directory submission confirmations or URLs available

## Next Phase Readiness
- Distribution configs are clean and ready for publishing
- Task 2 (PyPI publishing + MCP directory submissions) requires human action
- After Task 2, run plan 08 to complete Phase 4

---
*Phase: 04-dashboard-distribution*
*Completed: 2026-02-19*
