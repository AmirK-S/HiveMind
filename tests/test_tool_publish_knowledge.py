"""publish_knowledge : rendre un item visible aux autres organisations, et revenir en arriere."""

from __future__ import annotations

import uuid

from tests.conftest import AUTH_ERROR, call_tool, requires_database, tool_error, tool_ok

pytestmark = requires_database


async def test_publish_makes_the_item_visible_to_another_organisation_and_is_reversible(
    tool_client, token, other_org_token, approved_item, sql
):
    payload = tool_ok(
        await call_tool(tool_client, "publish_knowledge", {"id": approved_item, "is_public": True}, token)
    )
    assert payload["is_public"] is True
    assert sql("SELECT is_public FROM knowledge_items WHERE id = %s", (approved_item,)) == [(True,)]

    seen = tool_ok(await call_tool(tool_client, "search_knowledge", {"id": approved_item}, other_org_token))
    assert seen["id"] == approved_item

    payload = tool_ok(
        await call_tool(tool_client, "publish_knowledge", {"id": approved_item, "is_public": False}, token)
    )
    assert payload["is_public"] is False
    result = await call_tool(tool_client, "search_knowledge", {"id": approved_item}, other_org_token)
    assert "not found" in tool_error(result)


async def test_missing_token_is_refused(tool_client, approved_item):
    result = await call_tool(tool_client, "publish_knowledge", {"id": approved_item, "is_public": True})
    assert AUTH_ERROR in tool_error(result)


async def test_another_organisation_cannot_publish(tool_client, other_org_token, approved_item, sql):
    result = await call_tool(
        tool_client, "publish_knowledge", {"id": approved_item, "is_public": True}, other_org_token
    )
    assert f"Knowledge item '{approved_item}' not found or you do not have access to it." in tool_error(result)
    assert sql("SELECT is_public FROM knowledge_items WHERE id = %s", (approved_item,)) == [(False,)]


async def test_unknown_handle_is_refused(tool_client, token):
    unknown = str(uuid.uuid4())
    result = await call_tool(tool_client, "publish_knowledge", {"id": unknown, "is_public": True}, token)
    assert f"Knowledge item '{unknown}' not found or you do not have access to it." in tool_error(result)
