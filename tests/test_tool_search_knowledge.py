"""search_knowledge : retrouver un item par son handle, ou par recherche."""

from __future__ import annotations

import uuid

from tests.conftest import (
    AUTH_ERROR,
    ORG_A,
    SAMPLE_CONTENT,
    call_tool,
    requires_database,
    tool_error,
    tool_ok,
)

pytestmark = requires_database


async def test_fetch_by_handle_returns_the_item_with_integrity_check(tool_client, token, approved_item):
    payload = tool_ok(await call_tool(tool_client, "search_knowledge", {"id": approved_item}, token))
    assert payload["id"] == approved_item
    assert payload["content"] == SAMPLE_CONTENT
    assert payload["org_attribution"] == ORG_A
    assert payload["integrity_verified"] is True


async def test_search_by_exact_text_finds_the_item(tool_client, token, approved_item):
    payload = tool_ok(
        await call_tool(tool_client, "search_knowledge", {"query": SAMPLE_CONTENT}, token)
    )
    assert approved_item in {item["id"] for item in payload["results"]}


async def test_missing_token_is_refused(tool_client, approved_item):
    result = await call_tool(tool_client, "search_knowledge", {"id": approved_item})
    assert AUTH_ERROR in tool_error(result)


async def test_private_item_is_invisible_to_another_organisation_until_published(
    tool_client, other_org_token, approved_item, sql
):
    result = await call_tool(tool_client, "search_knowledge", {"id": approved_item}, other_org_token)
    assert f"Knowledge item '{approved_item}' not found." in tool_error(result)

    sql("UPDATE knowledge_items SET is_public = true WHERE id = %s", (approved_item,))
    payload = tool_ok(
        await call_tool(tool_client, "search_knowledge", {"id": approved_item}, other_org_token)
    )
    assert payload["id"] == approved_item


async def test_unknown_handle_is_indistinguishable_from_a_foreign_one(
    tool_client, token, other_org_token, approved_item
):
    unknown = str(uuid.uuid4())
    unknown_text = tool_error(await call_tool(tool_client, "search_knowledge", {"id": unknown}, token))
    foreign_text = tool_error(
        await call_tool(tool_client, "search_knowledge", {"id": approved_item}, other_org_token)
    )
    assert unknown_text.replace(unknown, "<id>") == foreign_text.replace(approved_item, "<id>")


async def test_query_or_handle_is_required(tool_client, token):
    result = await call_tool(tool_client, "search_knowledge", {}, token)
    assert "Provide either 'query' for search or 'id' to fetch a specific item." in tool_error(result)
