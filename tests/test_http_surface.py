"""La surface HTTP annoncee par le README : /health, /mcp, la carte serveur.

Le point MCP doit repondre sur /mcp, pas sur /mcp/mcp. Avant correction,
POST /mcp renvoyait 307 vers /mcp/ puis 404 (mesure du 05/09/2026).
"""

from __future__ import annotations


from tests.conftest import EXPECTED_TOOLS, MCP_HEADERS


def _tools_list_request(request_id: int = 1) -> dict:
    return {"jsonrpc": "2.0", "id": request_id, "method": "tools/list", "params": {}}


async def test_health_returns_ok(http_client):
    response = await http_client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


async def test_mcp_endpoint_is_served_at_slash_mcp(http_client):
    response = await http_client.post("/mcp", json=_tools_list_request(), headers=MCP_HEADERS)
    assert response.status_code == 200, f"{response.status_code} {response.text[:300]}"
    payload = response.json()
    names = {tool["name"] for tool in payload["result"]["tools"]}
    assert names == EXPECTED_TOOLS


async def test_mcp_endpoint_is_not_doubled(http_client):
    response = await http_client.post("/mcp/mcp", json=_tools_list_request(), headers=MCP_HEADERS)
    assert response.status_code == 404, "le point MCP repond encore sur /mcp/mcp"


async def test_server_card_advertises_slash_mcp(http_client):
    response = await http_client.get("/.well-known/mcp/server-card.json")
    assert response.status_code == 200
    assert "/mcp" in response.text
    assert "/mcp/mcp" not in response.text
