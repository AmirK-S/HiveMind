---
phase: 04-dashboard-distribution
plan: "03"
subsystem: ui
tags: [nextjs, react, tanstack-query, recharts, contributions, analytics, provenance, reciprocity]

# Dependency graph
requires:
  - phase: 04-dashboard-distribution
    provides: "GET /api/v1/contributions, POST /approve, POST /reject, GET /api/v1/stats/commons, GET /api/v1/stats/org, GET /api/v1/knowledge/:id"
  - phase: 04-dashboard-distribution
    provides: Next.js dashboard scaffold with TanStack Query, recharts, apiFetch helper, Sidebar with Contributions+Analytics links
affects:
  - 04-04-distribution

provides:
  - Contributions review list at /contributions with approve/reject workflow via TanStack Query mutations
  - Knowledge item detail at /contributions/[id] with full provenance (agent, org, hash, quality, retrieval stats)
  - Analytics page at /analytics with commons health section and org reciprocity ledger
  - GrowthChart (Recharts AreaChart) and StatsCard reusable components
  - Next.js proxy routes: /api/contributions, /api/contributions/[id]/approve, /api/contributions/[id]/reject, /api/knowledge/[id], /api/stats/commons, /api/stats/org

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "TanStack Query useMutation with optimistic updates: cancelQueries + setQueryData on onMutate, rollback in onError, invalidateQueries on onSettled"
    - "Recharts AreaChart with SVG linearGradient fill for growth visualization inside ResponsiveContainer"
    - "Recharts BarChart layout=vertical for horizontal category breakdown"
    - "Two-column responsive layout: flex-col on mobile, flex-row lg:flex-row on desktop for detail pages"

key-files:
  created:
    - dashboard/src/app/contributions/page.tsx
    - dashboard/src/app/contributions/[id]/page.tsx
    - dashboard/src/app/analytics/page.tsx
    - dashboard/src/components/contributions/ReviewCard.tsx
    - dashboard/src/components/charts/GrowthChart.tsx
    - dashboard/src/components/charts/StatsCard.tsx
    - dashboard/src/app/api/contributions/route.ts
    - dashboard/src/app/api/contributions/[id]/approve/route.ts
    - dashboard/src/app/api/contributions/[id]/reject/route.ts
    - dashboard/src/app/api/knowledge/[id]/route.ts
    - dashboard/src/app/api/stats/commons/route.ts
    - dashboard/src/app/api/stats/org/route.ts
  modified: []

key-decisions:
  - "Optimistic update pattern: cancelQueries + setQueryData on onMutate, context-based rollback on onError — prevents flickering while giving instant UI feedback"
  - "Two-section analytics page: CommonsStatsResponse fields drive health section, OrgStatsResponse fields drive reciprocity ledger — API shapes read from stats.py before implementing"
  - "Synthetic growth chart: 7-day time series built from growth_rate_7d and growth_rate_24h totals — /stats/commons has no time-series data, this provides visual without extra API"
  - "Gamification trigger: retrievals_by_others > contributions_total shows demand message — uses existing OrgStatsResponse fields, no new data needed"
  - "isPending detection: item has no quality_score — approved items always have quality_score set at approval; pending contributions do not"

requirements-completed: [DASH-03, DASH-04, DASH-05, DASH-06]

# Metrics
duration: 5min
completed: 2026-02-19
---

# Phase 4 Plan 03: Analytics UI and Contribution Review Summary

**Three feature pages (contributions review, item detail with provenance, analytics with reciprocity) backed by six Next.js proxy route handlers — delivering the management and observation layer for the knowledge commons**

## Performance

- **Duration:** ~5 min
- **Started:** 2026-02-19T13:54:48Z
- **Completed:** 2026-02-19T13:59:00Z
- **Tasks:** 3
- **Files created:** 12

## Accomplishments

- Contributions review list at `/contributions` with ReviewCard components, TanStack Query polling every 15s, optimistic approve/reject mutations (card immediately removed, rollback on error), skeleton loading, and empty state
- Knowledge item detail at `/contributions/[id]` with two-column responsive layout — full content left, provenance sidebar right — rendering all provenance fields: source_agent_id, org_id, contributed_at, full SHA-256 content_hash (copyable), quality score bar (red/yellow/green gradient), retrieval_count, helpful/not_helpful counts with ratio, is_public badge, valid_at/expired_at temporal info
- Analytics page at `/analytics` with two sections: Commons Health (6 StatsCards + GrowthChart + BarChart category breakdown) and Org Reciprocity Ledger (5 StatsCards + top-5 items table + gamification message), both polling every 30s
- Recharts GrowthChart (AreaChart with gradient fill) and StatsCard reusable components
- Six proxy route handlers forwarding to FastAPI with X-API-Key passthrough

## Task Commits

Each task was committed atomically:

1. **Task 1: Contributions review page with approve/reject workflow** - `a2899f2` (feat)
2. **Task 2: Knowledge item detail page with full provenance** - `dcf634a` (feat)
3. **Task 3: Analytics page with reciprocity ledger and commons health** - `85185bc` (feat)

## Files Created/Modified

- `dashboard/src/app/contributions/page.tsx` — Contributions list with 15s polling, skeleton loading, empty state
- `dashboard/src/app/contributions/[id]/page.tsx` — Item detail with full provenance, responsive two-column layout, approve/reject for pending items
- `dashboard/src/app/analytics/page.tsx` — Analytics page with commons health + org reciprocity, 30s polling, BarChart + GrowthChart
- `dashboard/src/components/contributions/ReviewCard.tsx` — Review card with useMutation optimistic updates, inline reject confirmation, hash copy
- `dashboard/src/components/charts/GrowthChart.tsx` — Recharts AreaChart with gradient fill, responsive container
- `dashboard/src/components/charts/StatsCard.tsx` — Reusable stat card with value, subtitle, trend indicator
- `dashboard/src/app/api/contributions/route.ts` — GET proxy to /api/v1/contributions
- `dashboard/src/app/api/contributions/[id]/approve/route.ts` — POST proxy to /api/v1/contributions/:id/approve
- `dashboard/src/app/api/contributions/[id]/reject/route.ts` — POST proxy to /api/v1/contributions/:id/reject
- `dashboard/src/app/api/knowledge/[id]/route.ts` — GET proxy to /api/v1/knowledge/:id
- `dashboard/src/app/api/stats/commons/route.ts` — GET proxy to /api/v1/stats/commons
- `dashboard/src/app/api/stats/org/route.ts` — GET proxy to /api/v1/stats/org

## Decisions Made

- Optimistic update pattern (cancelQueries + setQueryData on onMutate, context-based rollback on onError) — provides instant UI feedback while maintaining consistency with server state
- API response shapes read from FastAPI `stats.py` before implementing analytics page — ensured field names (e.g., `growth_rate_24h`, `retrievals_by_others`, `contributions_total`) are exact matches
- Synthetic 7-day growth chart built from `growth_rate_7d` and `growth_rate_24h` totals — API has no time-series endpoint; visual trend indicator more valuable than empty chart
- `isPending` detection via absence of `quality_score` — approved items always have quality_score set at approval time per 04-01 implementation
- Inline reject confirmation (small "Sure?" toggle) instead of modal — avoids dependency on modal library, consistent with Plan spec

## Deviations from Plan

None - plan executed exactly as written. All files created, all verification criteria passed (build succeeds, AreaChart/BarChart usage confirmed, all provenance fields rendered, TanStack Query mutations with optimistic updates).

---

**Total deviations:** 0
**Impact on plan:** None.

## Issues Encountered

None.

## User Setup Required

No additional setup beyond what Plan 04-02 requires. The same `.env.local` with `HIVEMIND_API_URL` and `HIVEMIND_API_KEY` is sufficient.

## Next Phase Readiness

- All dashboard pages are complete and functional
- Sidebar already includes Contributions and Analytics links (added in 04-02)
- `/contributions` and `/contributions/[id]` replace the CLI review flow for the dashboard
- `/analytics` provides the full network-effect visibility for DASH-03/05/06
- No blockers for Plan 04-04 (distribution)

---
*Phase: 04-dashboard-distribution*
*Completed: 2026-02-19*

## Self-Check: PASSED

- FOUND: dashboard/src/app/contributions/page.tsx
- FOUND: dashboard/src/app/contributions/[id]/page.tsx
- FOUND: dashboard/src/app/analytics/page.tsx
- FOUND: dashboard/src/components/contributions/ReviewCard.tsx
- FOUND: dashboard/src/components/charts/GrowthChart.tsx
- FOUND: dashboard/src/components/charts/StatsCard.tsx
- FOUND: dashboard/src/app/api/contributions/route.ts
- FOUND: dashboard/src/app/api/contributions/[id]/approve/route.ts
- FOUND: dashboard/src/app/api/contributions/[id]/reject/route.ts
- FOUND: dashboard/src/app/api/knowledge/[id]/route.ts
- FOUND: dashboard/src/app/api/stats/commons/route.ts
- FOUND: dashboard/src/app/api/stats/org/route.ts
- FOUND: .planning/phases/04-dashboard-distribution/04-03-SUMMARY.md
- FOUND: commit a2899f2 (Task 1: contributions review page)
- FOUND: commit dcf634a (Task 2: knowledge item detail)
- FOUND: commit 85185bc (Task 3: analytics page)
