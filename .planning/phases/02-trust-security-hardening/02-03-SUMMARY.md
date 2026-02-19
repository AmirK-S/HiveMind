---
phase: 02-trust-security-hardening
plan: 03
subsystem: security
tags: [casbin, rbac, pycasbin, fastapi-limiter, redis, api-key, rate-limiting, postgresql]

# Dependency graph
requires:
  - phase: 01-agent-connection-loop
    provides: JWT auth pattern (org_id, agent_id), db/models.py with ApiKey ORM, hivemind.config settings
  - phase: 02-trust-security-hardening
    provides: 02-02 Alembic migrations (api_keys table schema, casbin_rule table via adapter)

provides:
  - Casbin AsyncEnforcer singleton with PostgreSQL policy storage (ACL-03, ACL-04)
  - Domain-aware RBAC model (namespace/category/item three-level enforcement)
  - Policy CRUD helpers (add_policy, remove_policy, add_role_for_user)
  - Default policy seeder for org onboarding (seed_default_policies)
  - Tier-based rate limit constants (TIER_LIMITS: free/pro/enterprise)
  - Redis connection init and accessor (init_rate_limiter, get_redis_connection)
  - Anti-sybil burst detection via Redis ZSET (check_burst)
  - API key generation (hm_-prefixed, SHA-256 hash only stored)
  - API key CRUD: create_api_key (returns raw key once), validate_api_key, increment_request_count

affects:
  - 02-06 (MCP tool wiring — rate limiter and RBAC enforcement added to add_knowledge/search_knowledge)
  - server/main.py lifespan (init_rate_limiter and init_enforcer startup calls)

# Tech tracking
tech-stack:
  added:
    - pycasbin 2.8.0 (RBAC enforcement engine with AsyncEnforcer)
    - casbin-async-sqlalchemy-adapter 1.17.0 (PostgreSQL policy storage, auto-creates casbin_rule table)
    - fastapi-limiter 0.2.0 (endpoint rate limiting; uses pyrate-limiter 4.0.2 Limiter objects)
    - pyrate-limiter 4.0.2 (sliding window rate algorithm, pulled by fastapi-limiter)
  patterns:
    - Lazy singleton for AsyncEnforcer (same pattern as PIIPipeline/EmbeddingProvider)
    - Lazy config import in security modules (avoids circular dependency with hivemind.config)
    - SHA-256 hash-only API key storage (raw key shown once, never persisted)
    - Redis ZSET sliding window for burst/sybil detection (score = unix timestamp, member = contribution_id)
    - Namespaced rate limit keys: "{operation}:{org_id}:{agent_id}" (prevents cross-org collisions)

key-files:
  created:
    - hivemind/security/__init__.py
    - hivemind/security/rbac.py
    - hivemind/security/rbac_model.conf
    - hivemind/security/rate_limit.py
    - hivemind/security/api_key.py
  modified:
    - pyproject.toml (added pycasbin, casbin-async-sqlalchemy-adapter, fastapi-limiter dependencies)

key-decisions:
  - "fastapi-limiter 0.2.0 API differs from 0.1.x — no FastAPILimiter.init(redis); uses pyrate-limiter Limiter objects for endpoints; init_rate_limiter() stores Redis connection for anti-sybil ZSET operations only; endpoint-level RateLimiter deps wired in Plan 06"
  - "casbin-async-sqlalchemy-adapter strips +asyncpg from database_url — adapter creates its own sync SQLAlchemy engine and needs the plain postgresql:// URL form"
  - "seed_default_policies() uses default-permissive approach per research Open Question 1 — existing orgs get admin (full) and contributor (read+write) roles on namespace object to prevent lockout"
  - "Burst detection returns True as a flag (review signal), not a hard block — coordinated campaigns flagged but not rejected outright"

patterns-established:
  - "RBAC obj prefix convention: namespace:<org_id>, category:<cat>, item:<uuid> — three enforcement levels via obj string prefix"
  - "Security modules use lazy hivemind.config imports to avoid circular dependency"
  - "API keys use hm_ prefix for identifiability; only key[:8] stored as display prefix"

requirements-completed: [ACL-03, ACL-04, SEC-03, INFRA-04]

# Metrics
duration: 4min
completed: 2026-02-19
---

# Phase 02 Plan 03: Security Infrastructure Summary

**Casbin domain-aware RBAC enforcer + Redis anti-sybil burst detector + hm_-prefixed API key CRUD — all as standalone testable modules before Plan 06 wiring**

## Performance

- **Duration:** ~4 min
- **Started:** 2026-02-19T03:29:52Z
- **Completed:** 2026-02-19T03:33:46Z
- **Tasks:** 2 of 2
- **Files modified:** 6

## Accomplishments
- Created `hivemind/security/` package with Casbin AsyncEnforcer singleton backed by PostgreSQL via casbin-async-sqlalchemy-adapter; domain-aware three-level RBAC (namespace/category/item via obj prefixes)
- Created rate_limit.py with TIER_LIMITS (free/pro/enterprise), Redis init, anti-sybil ZSET burst detection (SEC-03), and namespaced rate limit key helpers
- Created api_key.py with `generate_api_key()` (hm_-prefix, SHA-256 hash), `create_api_key()` (raw key returned once), `validate_api_key()` (hash lookup + billing period reset), and `increment_request_count()` — raw key never persisted

## Task Commits

Each task was committed atomically:

1. **Task 1: Create Casbin RBAC module with domain-aware model** - `4bae7a4` (feat)
2. **Task 2: Create rate limiting and API key management modules** - `a475492` (feat)

## Files Created/Modified
- `hivemind/security/__init__.py` - Package marker
- `hivemind/security/rbac.py` - Casbin AsyncEnforcer singleton; exports: get_enforcer, enforce, add_policy, remove_policy, add_role_for_user, get_roles_for_user, seed_default_policies
- `hivemind/security/rbac_model.conf` - Casbin domain-aware model: `r = sub, dom, obj, act`
- `hivemind/security/rate_limit.py` - TIER_LIMITS dict, init_rate_limiter(), get_redis_connection(), check_burst(), get_rate_limit_key()
- `hivemind/security/api_key.py` - generate_api_key(), create_api_key(), validate_api_key(), increment_request_count()
- `pyproject.toml` - Added pycasbin, casbin-async-sqlalchemy-adapter, fastapi-limiter

## Decisions Made
- **fastapi-limiter 0.2.0 API change:** Research documented the 0.1.x `FastAPILimiter.init(redis)` pattern. The installed 0.2.0 version uses `pyrate-limiter` `Limiter` objects for endpoint dependencies — there is no `FastAPILimiter` class. `init_rate_limiter()` was adapted to store the Redis connection for ZSET burst detection; endpoint-level `RateLimiter` dependency wiring is deferred to Plan 06.
- **casbin-async-sqlalchemy-adapter URL handling:** The adapter creates its own SQLAlchemy engine and needs a plain `postgresql://` URL (strips `+asyncpg` from `settings.database_url`). The adapter auto-creates the `casbin_rule` table on first `load_policy()` call.
- **Default permissive policy seeding:** `seed_default_policies()` grants `admin` (full `*` on namespace) and `contributor` (read+write on namespace) roles per research Open Question 1 — prevents lockout of existing orgs when RBAC is first enabled.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Adapted init_rate_limiter() for fastapi-limiter 0.2.0 API**
- **Found during:** Task 2 (rate_limit.py creation) — verification import failed with `ImportError: cannot import name 'FastAPILimiter' from 'fastapi_limiter'`
- **Issue:** Research documented the 0.1.x API (`FastAPILimiter.init(redis_conn)`). fastapi-limiter 0.2.0 removed the `FastAPILimiter` class entirely; uses `pyrate-limiter` `Limiter` objects for endpoint wiring instead.
- **Fix:** Removed `FastAPILimiter` import and init call. `init_rate_limiter()` now creates and stores the `aioredis.Redis` connection in `_redis_conn` for anti-sybil ZSET operations. Endpoint `RateLimiter` dependencies will use `pyrate-limiter` `Limiter` objects in Plan 06.
- **Files modified:** `hivemind/security/rate_limit.py`
- **Verification:** `python -c "from hivemind.security.rate_limit import TIER_LIMITS, init_rate_limiter, check_burst, get_redis_connection; assert get_redis_connection() is None; print(...)"`
- **Committed in:** `a475492` (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 - API version mismatch)
**Impact on plan:** Auto-fix preserved all required exports and behavior. Anti-sybil burst detection is unchanged. Endpoint-level rate limiting deferred to Plan 06 as planned. No scope creep.

## Issues Encountered
- fastapi-limiter 0.2.0 breaking API change vs research docs (0.1.x). Detected and fixed during Task 2 verification.

## User Setup Required
None — all modules are standalone Python files. No external service configuration required for these security primitives. Redis and PostgreSQL must be running when the full server starts (existing infra requirement).

## Next Phase Readiness
- `hivemind/security/` package is complete and testable independently of database/Redis
- Plan 06 (MCP tool wiring) can now import `enforce()`, `check_burst()`, `validate_api_key()`, `increment_request_count()` and wire them into `add_knowledge` and `search_knowledge`
- Casbin policy enforcement is ready for admin tools (Plan 06 ACL-04 wiring)
- `seed_default_policies()` available for server startup sequence

---
*Phase: 02-trust-security-hardening*
*Completed: 2026-02-19*
