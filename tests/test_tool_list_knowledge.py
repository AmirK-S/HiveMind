"""list_knowledge: what the calling agent contributed, and nothing else."""

from __future__ import annotations

from tests.conftest import AUTH_ERROR, SAMPLE_CONTENT, call_tool, requires_database, tool_error, tool_ok

pytestmark = requires_database


async def _contribute(client, token):
    payload = tool_ok(
        await call_tool(client, "add_knowledge", {"content": SAMPLE_CONTENT, "category": "general"}, token)
    )
    return payload["contribution_id"]


async def test_lists_the_callers_pending_contribution(tool_client, token):
    handle = await _contribute(tool_client, token)
    payload = tool_ok(await call_tool(tool_client, "list_knowledge", {}, token))
    assert payload["total_count"] == 1
    assert payload["contributions"][0]["id"] == handle
    assert payload["contributions"][0]["status"] == "pending"


async def test_missing_token_is_refused(tool_client):
    assert AUTH_ERROR in tool_error(await call_tool(tool_client, "list_knowledge", {}))


async def test_another_organisation_sees_nothing(tool_client, token, other_org_token):
    await _contribute(tool_client, token)
    payload = tool_ok(await call_tool(tool_client, "list_knowledge", {}, other_org_token))
    assert payload["total_count"] == 0
    assert payload["contributions"] == []


async def test_another_agent_of_the_same_organisation_sees_nothing(tool_client, token, other_agent_token):
    await _contribute(tool_client, token)
    payload = tool_ok(await call_tool(tool_client, "list_knowledge", {}, other_agent_token))
    assert payload["total_count"] == 0


async def test_unknown_status_filter_is_refused(tool_client, token):
    result = await call_tool(tool_client, "list_knowledge", {"status": "approuve"}, token)
    assert "Invalid status 'approuve'. Valid values: all, approved, pending" in tool_error(result)
