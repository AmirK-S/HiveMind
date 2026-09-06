"""The server speaks the sessionless MCP revision 2026-07-28, and still serves the handshake era.

Request shapes checked against the Python SDK v2: a 2026-07-28 request is a
self-contained POST, with an MCP-Protocol-Version header, an Mcp-Method header
equal to the method in the body, an Mcp-Name header for tools/call, and a _meta
envelope carrying the client version and capabilities. No initialize, no
Mcp-Session-Id.
"""

from __future__ import annotations

from tests.conftest import (
    AUTH_ERROR,
    EXPECTED_TOOLS,
    MCP_HEADERS,
    call_tool,
    requires_database,
    tool_error,
    tool_ok,
)

MODERN_VERSION = "2026-07-28"
LEGACY_VERSION = "2025-11-25"
MODERN_META = {
    "io.modelcontextprotocol/protocolVersion": MODERN_VERSION,
    "io.modelcontextprotocol/clientCapabilities": {},
}


def _modern_headers(method: str, name: str | None = None) -> dict:
    headers = {**MCP_HEADERS, "MCP-Protocol-Version": MODERN_VERSION, "Mcp-Method": method}
    if name is not None:
        headers["Mcp-Name"] = name
    return headers


def _modern_body(method: str, params: dict | None = None, request_id: int = 1) -> dict:
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "method": method,
        "params": {**(params or {}), "_meta": MODERN_META},
    }


async def test_server_discover_answers_without_handshake_or_session(http_client):
    response = await http_client.post(
        "/mcp", json=_modern_body("server/discover"), headers=_modern_headers("server/discover")
    )
    assert response.status_code == 200, response.text[:300]
    assert "mcp-session-id" not in {k.lower() for k in response.headers}
    result = response.json()["result"]
    assert MODERN_VERSION in result["supportedVersions"]
    assert result["resultType"] == "complete"
    assert "tools" in result["capabilities"]


async def test_tools_list_on_the_modern_era_carries_cache_hints(http_client):
    response = await http_client.post(
        "/mcp", json=_modern_body("tools/list"), headers=_modern_headers("tools/list")
    )
    assert response.status_code == 200, response.text[:300]
    result = response.json()["result"]
    assert {tool["name"] for tool in result["tools"]} == EXPECTED_TOOLS
    assert isinstance(result["ttlMs"], int)
    assert result["cacheScope"] in {"public", "private"}
    assert result["resultType"] == "complete"


async def test_mismatched_mcp_method_header_is_rejected(http_client):
    response = await http_client.post(
        "/mcp", json=_modern_body("tools/list"), headers=_modern_headers("tools/call")
    )
    assert response.status_code == 400, response.text[:300]


async def test_legacy_era_is_still_served_on_the_same_url(http_client):
    initialize = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": LEGACY_VERSION,
            "capabilities": {},
            "clientInfo": {"name": "tests", "version": "0"},
        },
    }
    response = await http_client.post("/mcp", json=initialize, headers=MCP_HEADERS)
    assert response.status_code == 200, response.text[:300]
    assert response.json()["result"]["protocolVersion"] == LEGACY_VERSION

    headers = {**MCP_HEADERS, "MCP-Protocol-Version": LEGACY_VERSION}
    session_id = response.headers.get("mcp-session-id")
    if session_id:
        headers["Mcp-Session-Id"] = session_id
    listing = await http_client.post(
        "/mcp", json={"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}, headers=headers
    )
    assert listing.status_code == 200, listing.text[:300]
    assert {tool["name"] for tool in listing.json()["result"]["tools"]} == EXPECTED_TOOLS


async def test_foreign_host_header_is_refused(http_client):
    """DNS rebinding protection: an unknown Host must not reach the server."""
    headers = {**_modern_headers("tools/list"), "Host": "evil.example.com"}
    response = await http_client.post("/mcp", json=_modern_body("tools/list"), headers=headers)
    assert response.status_code in {400, 403, 421}, response.text[:300]


@requires_database
async def test_bearer_token_reaches_the_tools_on_the_modern_era(tool_client, token):
    """The refusal without a token and the success with one, both on the sessionless era."""
    body = _modern_body("tools/call", {"name": "list_knowledge", "arguments": {}})
    headers = _modern_headers("tools/call", "list_knowledge")

    refused = await tool_client.post("/mcp", json=body, headers=headers)
    assert refused.status_code == 200, refused.text[:300]
    assert AUTH_ERROR in tool_error(refused.json()["result"])

    accepted = await tool_client.post("/mcp", json=body, headers={**headers, "Authorization": f"Bearer {token}"})
    assert accepted.status_code == 200, accepted.text[:300]
    payload = tool_ok(accepted.json()["result"])
    assert payload["total_count"] == 0


async def test_server_discover_reports_the_hivemind_version_not_the_framework(http_client):
    import hivemind

    response = await http_client.post(
        "/mcp", json=_modern_body("server/discover"), headers=_modern_headers("server/discover")
    )
    server_info = response.json()["result"]["_meta"]["io.modelcontextprotocol/serverInfo"]
    assert server_info["name"] == "HiveMind"
    assert server_info["version"] == hivemind.__version__
