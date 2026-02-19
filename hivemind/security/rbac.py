"""Casbin RBAC enforcer with domain-aware policy enforcement.

Provides a lazy AsyncEnforcer singleton backed by PostgreSQL via
casbin-async-sqlalchemy-adapter.  Three enforcement levels are encoded
via ``obj`` prefixes:

- Namespace level:  ``obj = "namespace:<org_id>"``   — org-wide access
- Category level:   ``obj = "category:<category>"``  — knowledge-category access
- Item level:       ``obj = "item:<uuid>"``           — individual item access

Requirements: ACL-03 (three-level RBAC), ACL-04 (org admin role management).

Design decisions:
- Lazy singleton pattern mirrors PIIPipeline and EmbeddingProvider singletons.
- The database URL is imported lazily from hivemind.config to avoid circular
  dependency (config imports nothing from security).
- casbin-async-sqlalchemy-adapter creates the ``casbin_rule`` table
  automatically on first ``load_policy()`` call.
"""

from __future__ import annotations

import pathlib

import casbin
import casbin_async_sqlalchemy_adapter

# Module-level lazy singleton — initialised on first call to get_enforcer().
_enforcer: casbin.AsyncEnforcer | None = None

# Absolute path to the Casbin model config located alongside this module.
_MODEL_PATH = pathlib.Path(__file__).parent / "rbac_model.conf"


async def init_enforcer() -> casbin.AsyncEnforcer:
    """Initialise and return the Casbin AsyncEnforcer.

    Creates the adapter pointing at the project PostgreSQL database, loads
    all policies from the ``casbin_rule`` table (created automatically if
    absent), and stores the enforcer in the module-level singleton.

    The adapter receives the raw database URL; ``+asyncpg`` is stripped if
    present because casbin-async-sqlalchemy-adapter manages its own
    SQLAlchemy engine and prefers the sync driver name form.

    Requirements: ACL-03, ACL-04.
    """
    global _enforcer

    # Lazy import to avoid circular dependency.
    from hivemind.config import settings

    # casbin-async-sqlalchemy-adapter internally uses its own SQLAlchemy
    # engine.  Provide the plain postgresql URL (strip +asyncpg if present).
    db_url = settings.database_url.replace("+asyncpg", "")

    adapter = casbin_async_sqlalchemy_adapter.Adapter(db_url)
    enforcer = casbin.AsyncEnforcer(str(_MODEL_PATH), adapter)
    await enforcer.load_policy()

    _enforcer = enforcer
    return enforcer


async def get_enforcer() -> casbin.AsyncEnforcer:
    """Return the module-level AsyncEnforcer, initialising it on first call.

    Requirements: ACL-03, ACL-04.
    """
    global _enforcer
    if _enforcer is None:
        await init_enforcer()
    return _enforcer  # type: ignore[return-value]


async def enforce(subject: str, domain: str, obj: str, action: str) -> bool:
    """Check whether *subject* may perform *action* on *obj* within *domain*.

    Args:
        subject: The entity requesting access (e.g. agent_id or a role name).
        domain:  The tenant/namespace (org_id) that scopes the policy.
        obj:     The resource, prefixed by level — ``"namespace:<org_id>"``,
                 ``"category:<cat>"``, or ``"item:<uuid>"``.
        action:  The requested operation (e.g. ``"read"``, ``"write"``,
                 ``"*"``).

    Returns:
        ``True`` if allowed, ``False`` if denied.

    Requirements: ACL-03.
    """
    enforcer = await get_enforcer()
    return await enforcer.enforce(subject, domain, obj, action)


async def add_policy(subject: str, domain: str, obj: str, action: str) -> bool:
    """Add a policy rule ``(subject, domain, obj, action)`` to the store.

    Returns ``True`` if the rule was added, ``False`` if it already existed.

    Requirements: ACL-04.
    """
    enforcer = await get_enforcer()
    return await enforcer.add_policy(subject, domain, obj, action)


async def remove_policy(subject: str, domain: str, obj: str, action: str) -> bool:
    """Remove a policy rule from the store.

    Returns ``True`` if the rule was removed, ``False`` if it did not exist.

    Requirements: ACL-04.
    """
    enforcer = await get_enforcer()
    return await enforcer.remove_policy(subject, domain, obj, action)


async def add_role_for_user(user: str, role: str, domain: str) -> bool:
    """Assign *role* to *user* within *domain*.

    Wraps ``AsyncEnforcer.add_role_for_user_in_domain``.

    Requirements: ACL-04.
    """
    enforcer = await get_enforcer()
    return await enforcer.add_role_for_user_in_domain(user, role, domain)


async def get_roles_for_user(user: str, domain: str) -> list[str]:
    """Return all roles assigned to *user* within *domain*.

    Requirements: ACL-04.
    """
    enforcer = await get_enforcer()
    return await enforcer.get_roles_for_user_in_domain(user, domain)


async def seed_default_policies(org_id: str) -> None:
    """Seed baseline policies for a newly onboarded organisation.

    Per research Open Question 1 (default permissive approach): grants the
    ``admin`` role full access to the org namespace, and grants the
    ``contributor`` role read + write access to the org namespace.  These
    defaults ensure existing orgs are not locked out when RBAC is first
    enabled.

    Called once per org during initialisation; safe to call multiple times
    (Casbin ``add_policy`` is idempotent — returns False if rule exists).

    Args:
        org_id: The organisation identifier used as both the domain and the
                namespace object prefix.

    Requirements: ACL-03, ACL-04.
    """
    namespace_obj = f"namespace:{org_id}"

    # Admin: full access to the org namespace.
    await add_policy("admin", org_id, namespace_obj, "*")

    # Contributor: read and write access to the org namespace.
    await add_policy("contributor", org_id, namespace_obj, "read")
    await add_policy("contributor", org_id, namespace_obj, "write")
