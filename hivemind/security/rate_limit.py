"""Rate limiting setup and tier-based burst detection for HiveMind.

Uses Redis (via redis.asyncio) for anti-sybil burst detection and stores a
module-level connection for reuse by other modules.  fastapi-limiter 0.2.0
uses pyrate-limiter ``Limiter`` objects for endpoint-level rate limiting —
see Plan 06 for per-endpoint wiring.

Tier limits (per minute):
- free:       10 contributions, 30 searches
- pro:        60 contributions, 200 searches
- enterprise: 300 contributions, 1000 searches

Rate limit keys are namespaced by ``"{operation}:{org_id}:{agent_id}"`` to
avoid cross-org bucket collisions (research Pitfall 6).

Requirements: SEC-03 (anti-sybil burst detection), INFRA-04 (tier-based limits).
"""

from __future__ import annotations

import time

import redis.asyncio as aioredis

# Module-level Redis connection stored after init_rate_limiter() is called.
_redis_conn: aioredis.Redis | None = None

# ---------------------------------------------------------------------------
# Tier-based limits
# ---------------------------------------------------------------------------

TIER_LIMITS: dict[str, dict[str, int]] = {
    "free": {"contributions": 10, "searches": 30},
    "pro": {"contributions": 60, "searches": 200},
    "enterprise": {"contributions": 300, "searches": 1000},
}
"""Mapping from tier name to per-minute operation limits.

Values are *per minute* for the named operation type.  Keyed by operation so
different operations (contributions vs searches) can have independent limits.

Requirements: INFRA-04.
"""


# ---------------------------------------------------------------------------
# Initialisation
# ---------------------------------------------------------------------------


async def init_rate_limiter(redis_url: str) -> None:
    """Initialise the Redis connection used for rate limiting and burst detection.

    Must be called once during application startup (e.g. in the FastAPI or
    FastMCP lifespan function) before any rate-limited endpoint is served.

    Note: fastapi-limiter 0.2.0 uses pyrate-limiter ``Limiter`` objects for
    endpoint-level rate limiting.  Per-endpoint ``RateLimiter`` dependencies
    are wired in Plan 06 using these limits.  This function stores the Redis
    connection for anti-sybil ZSET operations via :func:`check_burst`.

    Args:
        redis_url: Redis connection string, e.g. ``"redis://localhost:6379/0"``.
                   Prefer ``settings.redis_url`` from hivemind.config.

    Requirements: SEC-03, INFRA-04.
    """
    global _redis_conn

    redis_connection = aioredis.from_url(
        redis_url, encoding="utf-8", decode_responses=True
    )
    _redis_conn = redis_connection


def get_redis_connection() -> aioredis.Redis | None:
    """Return the module-level Redis connection, or None before init.

    Other modules (e.g. ``add_knowledge``) use this to access Redis for
    burst-pattern detection without creating a second connection.

    Returns:
        The ``aioredis.Redis`` instance stored by :func:`init_rate_limiter`,
        or ``None`` if it has not been called yet.

    Requirements: SEC-03.
    """
    return _redis_conn


# ---------------------------------------------------------------------------
# Anti-sybil burst detection (SEC-03)
# ---------------------------------------------------------------------------


async def check_burst(org_id: str, contribution_id: str, redis_conn: aioredis.Redis) -> bool:
    """Detect coordinated contribution bursts for an organisation using a Redis ZSET.

    Implements SEC-03 anti-sybil detection.  Uses a sliding time window: each
    approved contribution is added to a sorted set keyed by org_id.  Entries
    older than ``settings.burst_window_seconds`` are pruned.  If the remaining
    count exceeds ``settings.burst_threshold``, the call returns ``True``
    signalling a burst (flag for manual review — do NOT outright block).

    Redis key format: ``"burst:{org_id}:contributions"``

    Args:
        org_id:          Organisation identifier.
        contribution_id: Unique ID for the contribution being recorded.
        redis_conn:      Active async Redis connection.

    Returns:
        ``True`` if a burst pattern is detected (count > threshold).
        ``False`` otherwise.

    Requirements: SEC-03.
    """
    # Lazy import to avoid circular dependency at module load.
    from hivemind.config import settings

    key = f"burst:{org_id}:contributions"
    now = time.time()
    window_start = now - settings.burst_window_seconds

    # Add the current contribution with its timestamp as score.
    await redis_conn.zadd(key, {contribution_id: now})

    # Remove entries outside the sliding window.
    await redis_conn.zremrangebyscore(key, "-inf", window_start)

    # Count contributions within the window.
    count = await redis_conn.zcard(key)

    return count > settings.burst_threshold


# ---------------------------------------------------------------------------
# Key helpers
# ---------------------------------------------------------------------------


def get_rate_limit_key(org_id: str, agent_id: str, operation: str) -> str:
    """Return a namespaced rate limit key for the given agent and operation.

    Format: ``"{operation}:{org_id}:{agent_id}"``

    Namespacing by org_id prevents key collisions across organisations when
    agent_id values are not globally unique (research Pitfall 6).

    Args:
        org_id:    Organisation identifier.
        agent_id:  Agent identifier.
        operation: Operation name, e.g. ``"contributions"`` or ``"searches"``.

    Returns:
        Namespaced rate limit key string.

    Requirements: INFRA-04.
    """
    return f"{operation}:{org_id}:{agent_id}"
