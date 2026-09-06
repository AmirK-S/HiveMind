"""report_outcome: report whether a retrieved item helped, deduplicated by run_id."""

from __future__ import annotations

import uuid

from tests.conftest import AUTH_ERROR, call_tool, requires_database, tool_error, tool_ok

pytestmark = requires_database


async def test_outcome_is_recorded_and_counted_once_per_run(tool_client, token, approved_item, sql):
    args = {"item_id": approved_item, "outcome": "solved", "run_id": "run-1"}
    payload = tool_ok(await call_tool(tool_client, "report_outcome", args, token))
    assert payload["status"] == "recorded"
    uuid.UUID(payload["signal_id"])

    again = tool_ok(await call_tool(tool_client, "report_outcome", args, token))
    assert again["status"] == "already_recorded"
    assert again["signal_id"] == payload["signal_id"]

    assert sql(
        "SELECT count(*) FROM quality_signals WHERE knowledge_item_id = %s AND signal_type = 'outcome_solved'",
        (approved_item,),
    ) == [(1,)]
    assert sql("SELECT helpful_count FROM knowledge_items WHERE id = %s", (approved_item,)) == [(1,)]


async def test_missing_token_is_refused(tool_client, approved_item):
    result = await call_tool(tool_client, "report_outcome", {"item_id": approved_item, "outcome": "solved"})
    assert AUTH_ERROR in tool_error(result)


async def test_another_organisation_cannot_rate_a_private_item(tool_client, other_org_token, approved_item, sql):
    result = await call_tool(
        tool_client, "report_outcome", {"item_id": approved_item, "outcome": "solved"}, other_org_token
    )
    assert f"Knowledge item '{approved_item}' not found." in tool_error(result)
    assert sql("SELECT helpful_count FROM knowledge_items WHERE id = %s", (approved_item,)) == [(0,)]


async def test_unknown_handle_records_nothing(tool_client, token, sql):
    unknown = str(uuid.uuid4())
    result = await call_tool(tool_client, "report_outcome", {"item_id": unknown, "outcome": "solved"}, token)
    assert f"Knowledge item '{unknown}' not found." in tool_error(result)
    assert sql("SELECT count(*) FROM quality_signals") == [(0,)]


async def test_unknown_outcome_is_refused(tool_client, token, approved_item):
    result = await call_tool(tool_client, "report_outcome", {"item_id": approved_item, "outcome": "maybe"}, token)
    assert "Invalid outcome 'maybe'. Must be one of: did_not_help, solved" in tool_error(result)
