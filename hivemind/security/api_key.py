"""API key creation, validation, and usage tracking for HiveMind.

API keys use a ``hm_`` prefix followed by a URL-safe random token.  Only the
SHA-256 hash of the raw key is stored in the database — the raw key is shown
exactly ONCE to the caller at creation time and cannot be recovered afterward
(research anti-pattern: never store raw API keys).

Key lifecycle:
1. ``create_api_key()`` — generates key, inserts ApiKey row, returns raw key once.
2. ``validate_api_key()`` — hashes the presented key, looks up by hash, checks
   active/billing-period state, returns context dict or None.
3. ``increment_request_count()`` — updates usage counter and last_used_at for
   billing analytics.

Requirements: INFRA-04 (API key auth with tier, request counter, billing reset).
Anti-pattern: SEC-03 note — raw key is NEVER stored (Pitfall: never store raw keys).
"""

from __future__ import annotations

import datetime
import hashlib
import secrets
import uuid


# ---------------------------------------------------------------------------
# Low-level key generation
# ---------------------------------------------------------------------------


def generate_api_key() -> tuple[str, str, str]:
    """Generate a new HiveMind API key and return its components.

    The raw key uses a ``hm_`` prefix for easy identification in logs/config.
    Only the first 8 characters (``key_prefix``) and the SHA-256 hash
    (``key_hash``) are safe to persist — the raw key must not be stored.

    Returns:
        A ``(raw_key, key_prefix, key_hash)`` triple where:
        - ``raw_key``    — full key shown once to the user (e.g. ``"hm_abc..."``).
        - ``key_prefix`` — first 8 characters for safe display (``"hm_12345"``).
        - ``key_hash``   — SHA-256 hex digest used for database lookup.

    Requirements: INFRA-04.
    """
    key = "hm_" + secrets.token_urlsafe(32)
    key_prefix = key[:8]
    key_hash = hashlib.sha256(key.encode()).hexdigest()
    return key, key_prefix, key_hash


# ---------------------------------------------------------------------------
# CRUD operations
# ---------------------------------------------------------------------------


async def create_api_key(
    org_id: str,
    agent_id: str,
    tier: str = "free",
) -> tuple[str, str]:
    """Create a new API key for the given agent and return the raw key once.

    Inserts an ApiKey row into the database with the hashed key.  The raw
    key is returned to the caller and is NEVER stored — it cannot be recovered
    from the database after this function returns.

    Args:
        org_id:   Organisation the key belongs to (namespace isolation, ACL-01).
        agent_id: Agent the key authenticates.
        tier:     Billing tier controlling rate limits (``"free"`` | ``"pro"``
                  | ``"enterprise"``).  Defaults to ``"free"``.

    Returns:
        ``(raw_key, api_key_id)`` — the raw key shown once and the UUID of the
        newly created ApiKey row (for audit logging).

    Requirements: INFRA-04.
    """
    # Lazy imports to avoid circular dependencies at module load.
    from hivemind.db.models import ApiKey
    from hivemind.db.session import get_session

    raw_key, key_prefix, key_hash = generate_api_key()

    async with get_session() as session:
        api_key = ApiKey(
            id=uuid.uuid4(),
            key_prefix=key_prefix,
            key_hash=key_hash,
            org_id=org_id,
            agent_id=agent_id,
            tier=tier,
            request_count=0,
            billing_period_start=datetime.datetime.utcnow(),
            billing_period_reset_days=30,
            is_active=True,
        )
        session.add(api_key)
        await session.commit()
        await session.refresh(api_key)

        api_key_id = str(api_key.id)

    return raw_key, api_key_id


async def validate_api_key(raw_key: str) -> dict | None:
    """Validate a raw API key and return context if it is active.

    Hashes the presented key and looks up the record by ``key_hash``.  If the
    key is found and active, checks whether the billing period has expired and
    resets the request counter if so.

    Args:
        raw_key: The raw API key string as presented by the caller.

    Returns:
        A context dict with keys ``org_id``, ``agent_id``, ``tier``,
        ``request_count``, and ``api_key_id`` if valid and active.
        ``None`` if the key is not found, is inactive, or has been revoked.

    Requirements: INFRA-04.
    """
    from sqlalchemy import select, update

    from hivemind.db.models import ApiKey
    from hivemind.db.session import get_session

    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()

    async with get_session() as session:
        result = await session.execute(
            select(ApiKey).where(ApiKey.key_hash == key_hash)
        )
        api_key = result.scalar_one_or_none()

        if api_key is None or not api_key.is_active:
            return None

        # Billing period reset: if the billing period has expired, reset the counter.
        now = datetime.datetime.utcnow()
        billing_age_days = (now - api_key.billing_period_start).days
        if billing_age_days >= api_key.billing_period_reset_days:
            await session.execute(
                update(ApiKey)
                .where(ApiKey.id == api_key.id)
                .values(request_count=0, billing_period_start=now)
            )
            await session.commit()
            # Reflect reset in the returned context.
            request_count = 0
        else:
            request_count = api_key.request_count

        return {
            "org_id": api_key.org_id,
            "agent_id": api_key.agent_id,
            "tier": api_key.tier,
            "request_count": request_count,
            "api_key_id": str(api_key.id),
        }


async def increment_request_count(api_key_id: str) -> None:
    """Increment the request counter and update last_used_at for a key.

    Should be called after each successful authenticated request to maintain
    accurate usage metrics for billing and rate-limit enforcement.

    Args:
        api_key_id: UUID string of the ApiKey row to update.

    Requirements: INFRA-04.
    """
    import uuid as _uuid

    from sqlalchemy import update

    from hivemind.db.models import ApiKey
    from hivemind.db.session import get_session

    key_uuid = _uuid.UUID(api_key_id)
    now = datetime.datetime.utcnow()

    async with get_session() as session:
        await session.execute(
            update(ApiKey)
            .where(ApiKey.id == key_uuid)
            .values(
                request_count=ApiKey.request_count + 1,
                last_used_at=now,
            )
        )
        await session.commit()
