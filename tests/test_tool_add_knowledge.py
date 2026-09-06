"""add_knowledge : contribuer une connaissance et recevoir un handle frappe par le serveur."""

from __future__ import annotations

import uuid

from tests.conftest import (
    AUTH_ERROR,
    ORG_A,
    ORG_B,
    SAMPLE_CONTENT,
    call_tool,
    requires_database,
    tool_error,
    tool_ok,
)

pytestmark = requires_database


async def test_contribution_is_queued_and_returns_a_server_minted_handle(tool_client, token, sql):
    result = await call_tool(
        tool_client, "add_knowledge", {"content": SAMPLE_CONTENT, "category": "general"}, token
    )
    payload = tool_ok(result)
    assert payload["status"] == "queued"
    handle = uuid.UUID(payload["contribution_id"])
    rows = sql("SELECT org_id FROM pending_contributions WHERE id = %s", (str(handle),))
    assert rows == [(ORG_A,)]


async def test_auto_approve_rule_writes_straight_into_the_commons(tool_client, token, sql, auto_approve):
    result = await call_tool(
        tool_client, "add_knowledge", {"content": SAMPLE_CONTENT, "category": "general"}, token
    )
    payload = tool_ok(result)
    assert payload["status"] == "auto_approved"
    rows = sql(
        "SELECT org_id, is_public, deleted_at FROM knowledge_items WHERE id = %s",
        (payload["contribution_id"],),
    )
    assert rows == [(ORG_A, False, None)]


async def test_missing_token_is_refused(tool_client):
    result = await call_tool(
        tool_client, "add_knowledge", {"content": SAMPLE_CONTENT, "category": "general"}
    )
    assert AUTH_ERROR in tool_error(result)


async def test_contribution_lands_in_the_callers_organisation_only(
    tool_client, token, other_org_token, sql
):
    result = await call_tool(
        tool_client, "add_knowledge", {"content": SAMPLE_CONTENT, "category": "general"}, other_org_token
    )
    payload = tool_ok(result)
    rows = sql("SELECT org_id FROM pending_contributions WHERE id = %s", (payload["contribution_id"],))
    assert rows == [(ORG_B,)]

    listing = tool_ok(await call_tool(tool_client, "list_knowledge", {}, token))
    assert listing["total_count"] == 0


async def test_unknown_category_is_refused(tool_client, token):
    result = await call_tool(
        tool_client, "add_knowledge", {"content": SAMPLE_CONTENT, "category": "inconnue"}, token
    )
    assert "'inconnue' is not a valid category" in tool_error(result)
