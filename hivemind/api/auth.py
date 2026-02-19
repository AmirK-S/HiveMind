"""API key authentication dependency for HiveMind REST API.

The ``require_api_key`` FastAPI dependency:
1. Reads the ``X-API-Key`` header from the incoming request.
2. Hashes the presented key with SHA-256 (same as create_api_key — raw key never stored).
3. Looks up the hash in the ``api_keys`` table and checks ``is_active``.
4. Checks if the billing period has expired; resets ``request_count`` atomically if so.
5. Increments ``request_count`` and updates ``last_used_at`` (usage metering, INFRA-04).
6. Returns the ``ApiKey`` ORM record for downstream use (org_id, tier, etc.).

Merging metering into the auth dependency (rather than a separate middleware class)
keeps the logic in one place, runs inside the same DB session, and is trivially testable
by substituting the dependency in test clients.

Requirements: INFRA-04, SDK-01.
Anti-pattern: Raw key is NEVER stored — only SHA-256 hash is persisted (SEC-03).
"""

from __future__ import annotations

import datetime
import hashlib

from fastapi import Depends, HTTPException, Security
from fastapi.security import APIKeyHeader
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from hivemind.db.models import ApiKey
from hivemind.db.session import AsyncSessionFactory

# ---------------------------------------------------------------------------
# Header definition — FastAPI will return 403 automatically if header is absent
# when auto_error=True. We set auto_error=False so we can return a custom 401.
# ---------------------------------------------------------------------------

API_KEY_HEADER = APIKeyHeader(name="X-API-Key", auto_error=False)


# ---------------------------------------------------------------------------
# Session dependency
# ---------------------------------------------------------------------------


async def get_async_session() -> AsyncSession:
    """FastAPI dependency that yields a fresh AsyncSession for each request."""
    async with AsyncSessionFactory() as session:
        yield session


# ---------------------------------------------------------------------------
# Authentication + metering dependency
# ---------------------------------------------------------------------------


async def require_api_key(
    api_key: str | None = Security(API_KEY_HEADER),
    session: AsyncSession = Depends(get_async_session),
) -> ApiKey:
    """FastAPI dependency that validates an API key and increments usage metering.

    Validates the ``X-API-Key`` header against the ``api_keys`` table using a
    SHA-256 hash comparison (the raw key is never stored).  On success, atomically
    increments ``request_count`` and sets ``last_used_at`` in the same transaction
    as validation to ensure accurate billing-period quota tracking (INFRA-04).

    Args:
        api_key: Raw API key from the ``X-API-Key`` header (injected by FastAPI).
        session: Async DB session (injected by FastAPI dependency).

    Returns:
        The authenticated ``ApiKey`` ORM record.  Callers can read ``record.org_id``,
        ``record.tier``, etc. for downstream authorization.

    Raises:
        HTTPException(401): If the header is absent, the key is not found, or the
                            key is inactive/revoked.

    Requirements: INFRA-04.
    """
    if not api_key:
        raise HTTPException(status_code=401, detail="Invalid or inactive API key")

    # Hash the presented key — only the hash is stored (SEC-03)
    key_hash = hashlib.sha256(api_key.encode()).hexdigest()

    # Look up the key record by hash
    result = await session.execute(
        select(ApiKey).where(ApiKey.key_hash == key_hash)
    )
    record = result.scalar_one_or_none()

    if record is None or not record.is_active:
        raise HTTPException(status_code=401, detail="Invalid or inactive API key")

    # Billing period reset: if the period has expired, reset request_count to 0.
    now = datetime.datetime.now(datetime.timezone.utc)

    # billing_period_start may be naive (stored as UTC without tzinfo) — normalise.
    billing_start = record.billing_period_start
    if billing_start.tzinfo is None:
        billing_start = billing_start.replace(tzinfo=datetime.timezone.utc)

    billing_age_days = (now - billing_start).days
    if billing_age_days >= record.billing_period_reset_days:
        # Reset counter and start a fresh billing period
        await session.execute(
            update(ApiKey)
            .where(ApiKey.id == record.id)
            .values(request_count=1, billing_period_start=now, last_used_at=now)
        )
    else:
        # Normal request — increment counter and update last_used_at atomically
        await session.execute(
            update(ApiKey)
            .where(ApiKey.id == record.id)
            .values(
                request_count=ApiKey.request_count + 1,
                last_used_at=now,
            )
        )

    await session.commit()

    # Refresh the record so callers see updated counts
    await session.refresh(record)
    return record
