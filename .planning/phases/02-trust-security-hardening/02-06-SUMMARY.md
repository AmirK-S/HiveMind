---
phase: 02-trust-security-hardening
plan: "06"
subsystem: security
tags: [mcp, fastmcp, casbin, rbac, api-key, rate-limiting, celery, webhook, injection-scanner, jwt]

# Dependency graph
requires:
  - phase: 02-trust-security-hardening
    plan: 02
    provides: ApiKey, WebhookEndpoint ORM models; redis_url + burst settings in config
  - phase: 02-trust-security-hardening
    plan: 03
    provides: Casbin RBAC enforcer (init_enforcer, enforce, add_policy), rate_limit.init_rate_limiter(), api_key.validate_api_key/increment_request_count
  - phase: 02-trust-security-hardening
    plan: 04
    provides: celery_app + configure_celery(), dispatch_webhooks() fan-out helper
  - phase: 01-agent-connection-loop
    provides: JWT auth pattern (decode_token), MCP tool registration (Tool.from_function), get_http_headers()

provides:
  - "Extended server lifespan initializing InjectionScanner, rate limiter, RBAC enforcer, and Celery alongside Phase 1 PII/embedder warmup"
  - "publish_knowledge MCP tool for reversible publication to the public commons with org ownership check (ACL-02)"
  - "manage_roles MCP tool with admin gate enabling RBAC management at namespace/category/item levels (ACL-03, ACL-04)"
  - "Webhook dispatch wired into approve_contribution() in CLI — best-effort, never blocks approval (INFRA-03)"
  - "decode_token_async() async entry point supporting both JWT and hm_-prefixed API keys (INFRA-04)"
  - "AuthContext.tier field populated when authenticated via API key"
  - "Six total MCP tools registered: add_knowledge, search_knowledge, list_knowledge, delete_knowledge, publish_knowledge, manage_roles"

affects:
  - phase-3-graph-intelligence (server lifespan pattern established for future Phase 3 init)
  - external-consumers (webhooks now fire on knowledge approval)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Dual-auth entry point: decode_token_async() checks hm_ prefix then falls through to JWT — no breaking change for JWT callers"
    - "Admin gate pattern in MCP tools: enforce(agent_id, org_id, namespace_obj, '*') before any privileged action (ACL-04)"
    - "Best-effort webhook dispatch: try/except wraps dispatch_webhooks() in approval flow — delivery failure never blocks approval"
    - "Phase 2 lifespan ordering: PII -> embedder -> injection scanner -> rate limiter -> RBAC enforcer -> Celery -> deployment config"

key-files:
  created:
    - hivemind/server/tools/publish_knowledge.py
    - hivemind/server/tools/admin_tools.py
  modified:
    - hivemind/server/main.py
    - hivemind/server/auth.py
    - hivemind/cli/client.py

key-decisions:
  - "decode_token_async() added as parallel async entry point — decode_token() kept unchanged for JWT-only backward compatibility; no need to modify existing tool callers"
  - "AuthContext gains optional tier field (default None) — JWT-authenticated callers get tier=None, API-key callers get tier from DB record"
  - "manage_roles admin check uses enforce(agent_id, org_id, namespace:org_id, *) — consistent with existing Casbin domain-aware model convention"
  - "publish_knowledge returns 404 for cross-org items regardless of existence — prevents org discovery via error message difference (ACL-01)"
  - "Webhook dispatch placed after session.commit() and before session.refresh() in approval flow — item is committed before fanout"

patterns-established:
  - "New MCP tools use _extract_auth() local helper calling decode_token() — can be migrated to decode_token_async() in a follow-up to support API key auth in tool handlers"
  - "Admin gate: enforce() with wildcard action '*' on namespace obj is the canonical admin check pattern"

requirements-completed: [ACL-02, ACL-03, ACL-04, SEC-03, INFRA-03, INFRA-04]

# Metrics
duration: 3min
completed: 2026-02-19
---

# Phase 02 Plan 06: MCP Tool Wiring and Auth Integration Summary

**Six MCP tools registered (including publish_knowledge + manage_roles), server lifespan extended with injection scanner/rate limiter/RBAC/Celery init, webhook dispatch wired into approval flow, and dual JWT+API-key auth via decode_token_async()**

## Performance

- **Duration:** ~3 min
- **Started:** 2026-02-19T03:38:01Z
- **Completed:** 2026-02-19T03:41:00Z
- **Tasks:** 3 of 3
- **Files modified:** 3 modified, 2 created

## Accomplishments

- Server lifespan now initializes all Phase 2 security components at startup: InjectionScanner (SEC-01), rate limiter (SEC-03/INFRA-04), RBAC enforcer (ACL-03), and Celery broker (INFRA-03) — no cold-start penalty on first agent request
- publish_knowledge MCP tool provides reversible publication to the public commons with org ownership isolation (ACL-02) — returns 404 for cross-org items to prevent org discovery
- manage_roles MCP tool enables org admins to manage RBAC policies at namespace/category/item levels (ACL-03/ACL-04) with an enforce() admin gate before any action
- approve_contribution() in CLI now dispatches webhook notifications after successful approval — best-effort, never blocks (INFRA-03)
- decode_token_async() provides a clean async entry point detecting hm_-prefixed API keys and routing through validate_api_key() with tier info (INFRA-04)

## Task Commits

Each task was committed atomically:

1. **Task 1: Extend server lifespan and create publish_knowledge tool** - `bde0202` (feat)
2. **Task 2: Create admin tools and wire webhook dispatch into approval flow** - `862b77a` (feat)
3. **Task 3: Wire API key authentication into auth.py alongside JWT** - `d7f265f` (feat)

**Plan metadata:** (docs commit follows)

## Files Created/Modified

- `hivemind/server/main.py` — Extended lifespan with Phase 2 init (steps 2.5-2.8); added imports for InjectionScanner, init_enforcer, init_rate_limiter, configure_celery; registered publish_knowledge and manage_roles tools
- `hivemind/server/tools/publish_knowledge.py` — publish_knowledge MCP tool: toggle is_public on org-owned KnowledgeItem, reversible, 404 on cross-org (ACL-02)
- `hivemind/server/tools/admin_tools.py` — manage_roles MCP tool: admin gate + assign_role, get_roles, add_permission, remove_permission actions (ACL-03, ACL-04)
- `hivemind/cli/client.py` — Added dispatch_webhooks import + best-effort webhook dispatch in approve_contribution() after session.commit() (INFRA-03)
- `hivemind/server/auth.py` — Added optional tier field to AuthContext; added decode_token_async() detecting hm_ prefix, routing to validate_api_key(), incrementing request count (INFRA-04)

## Decisions Made

- `decode_token_async()` added as a parallel async entry point alongside `decode_token()` (JWT-only). This avoids modifying all existing tool callers while providing the recommended entry point for new tools that need dual JWT+API-key support.
- `AuthContext.tier` defaults to `None` — JWT-authenticated contexts remain backward compatible; tier is only populated by API key auth.
- Admin check uses `enforce(agent_id, org_id, f"namespace:{org_id}", "*")` — matches the domain-aware Casbin model established in Plan 03.
- `publish_knowledge` returns a generic 404 for any item not found or not owned by the caller's org — prevents cross-org existence discovery via error message difference.
- Webhook dispatch placed after `session.commit()` but before `session.refresh()` — item UUID is stable post-commit and available for the dispatch payload.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required. All modules import cleanly. Redis, PostgreSQL, and Celery workers are required at server runtime (existing infra requirement from prior plans).

## Next Phase Readiness

- All Phase 2 requirements fulfilled: RBAC (ACL-02/03/04), rate limiting (SEC-03), webhook delivery (INFRA-03), API key auth infrastructure (INFRA-04)
- Phase 2 feature set is complete — ready for Phase 3 (Graph Intelligence)
- Tool handlers using decode_token() can be migrated to decode_token_async() as a follow-up to support API key auth in all existing tools (not in scope for Phase 2)

## Self-Check: PASSED

All files verified present:
- hivemind/server/main.py: FOUND
- hivemind/server/tools/publish_knowledge.py: FOUND
- hivemind/server/tools/admin_tools.py: FOUND
- hivemind/cli/client.py: FOUND
- hivemind/server/auth.py: FOUND

Commits verified:
- bde0202: feat(02-06): extend lifespan with Phase 2 init and add publish_knowledge tool
- 862b77a: feat(02-06): add manage_roles tool and wire webhook dispatch in approval flow
- d7f265f: feat(02-06): wire API key auth into auth.py with decode_token_async

---
*Phase: 02-trust-security-hardening*
*Completed: 2026-02-19*
