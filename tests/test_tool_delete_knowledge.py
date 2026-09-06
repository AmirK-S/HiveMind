"""delete_knowledge: soft delete, by the agent who contributed, inside its own organisation."""

from __future__ import annotations

import uuid

from tests.conftest import AUTH_ERROR, call_tool, requires_database, tool_error, tool_ok

pytestmark = requires_database


async def test_owner_deletes_and_the_item_disappears_from_fetch(tool_client, token, approved_item, sql):
    payload = tool_ok(await call_tool(tool_client, "delete_knowledge", {"id": approved_item}, token))
    assert payload["status"] == "deleted"
    assert sql("SELECT deleted_at IS NOT NULL FROM knowledge_items WHERE id = %s", (approved_item,)) == [(True,)]

    result = await call_tool(tool_client, "search_knowledge", {"id": approved_item}, token)
    assert f"Knowledge item '{approved_item}' not found." in tool_error(result)


async def test_missing_token_is_refused(tool_client, approved_item):
    assert AUTH_ERROR in tool_error(await call_tool(tool_client, "delete_knowledge", {"id": approved_item}))


async def test_another_organisation_cannot_delete(tool_client, other_org_token, approved_item, sql):
    result = await call_tool(tool_client, "delete_knowledge", {"id": approved_item}, other_org_token)
    assert f"Knowledge item '{approved_item}' not found." in tool_error(result)
    assert sql("SELECT deleted_at FROM knowledge_items WHERE id = %s", (approved_item,)) == [(None,)]


async def test_another_agent_of_the_same_organisation_cannot_delete(
    tool_client, other_agent_token, approved_item, sql
):
    result = await call_tool(tool_client, "delete_knowledge", {"id": approved_item}, other_agent_token)
    assert "not found" in tool_error(result)
    assert sql("SELECT deleted_at FROM knowledge_items WHERE id = %s", (approved_item,)) == [(None,)]


async def test_unknown_handle_gets_the_same_answer_as_a_foreign_one(
    tool_client, token, other_org_token, approved_item
):
    unknown = str(uuid.uuid4())
    unknown_text = tool_error(await call_tool(tool_client, "delete_knowledge", {"id": unknown}, token))
    foreign_text = tool_error(
        await call_tool(tool_client, "delete_knowledge", {"id": approved_item}, other_org_token)
    )
    assert unknown_text.replace(unknown, "<id>") == foreign_text.replace(approved_item, "<id>")
