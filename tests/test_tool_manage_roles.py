"""manage_roles: RBAC administration, reserved for the organisation admins."""

from __future__ import annotations

import pytest

from tests.conftest import AGENT_1, AGENT_2, AUTH_ERROR, ORG_A, call_tool, requires_database, tool_error, tool_ok

pytestmark = requires_database

ADMIN_ERROR = (
    "Only organization admins can manage roles. Your agent does not have admin privileges in this org."
)


@pytest.fixture
def admin_policies(sql):
    """agent-1 is an admin of org-a: one policy and one role binding in casbin_rule."""
    import hivemind.security.rbac as rbac

    sql(
        "INSERT INTO casbin_rule (ptype, v0, v1, v2, v3) VALUES "
        "('p', 'admin', %s, %s, '*'), ('g', %s, 'admin', %s, NULL)",
        (ORG_A, f"namespace:{ORG_A}", AGENT_1, ORG_A),
    )
    rbac._enforcer = None


async def test_admin_reads_and_assigns_roles(tool_client, token, admin_policies, sql):  # noqa: ARG001
    payload = tool_ok(
        await call_tool(tool_client, "manage_roles", {"action": "get_roles", "agent_id": AGENT_2}, token)
    )
    assert payload["domain"] == ORG_A
    assert payload["roles"] == []

    tool_ok(
        await call_tool(
            tool_client,
            "manage_roles",
            {"action": "assign_role", "agent_id": AGENT_2, "role": "contributor"},
            token,
        )
    )
    payload = tool_ok(
        await call_tool(tool_client, "manage_roles", {"action": "get_roles", "agent_id": AGENT_2}, token)
    )
    assert payload["roles"] == ["contributor"]
    rows = sql("SELECT v0, v1, v2 FROM casbin_rule WHERE ptype = 'g' AND v0 = %s", (AGENT_2,))
    assert rows == [(AGENT_2, "contributor", ORG_A)]


async def test_missing_token_is_refused(tool_client):
    result = await call_tool(tool_client, "manage_roles", {"action": "get_roles", "agent_id": AGENT_2})
    assert AUTH_ERROR in tool_error(result)


async def test_admin_of_one_organisation_is_nobody_in_another(tool_client, other_org_token, admin_policies):  # noqa: ARG001
    result = await call_tool(
        tool_client, "manage_roles", {"action": "get_roles", "agent_id": AGENT_2}, other_org_token
    )
    assert ADMIN_ERROR in tool_error(result)


async def test_without_any_policy_nobody_is_admin(tool_client, token):
    result = await call_tool(tool_client, "manage_roles", {"action": "get_roles", "agent_id": AGENT_2}, token)
    assert ADMIN_ERROR in tool_error(result)


async def test_unknown_action_is_refused_for_an_admin(tool_client, token, admin_policies):  # noqa: ARG001
    result = await call_tool(tool_client, "manage_roles", {"action": "nope", "agent_id": AGENT_2}, token)
    assert "Unknown action 'nope'. Valid actions: assign_role, get_roles, add_permission, remove_permission." in tool_error(result)
