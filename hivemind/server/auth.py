"""Bearer token authentication for the HiveMind MCP server.

Design decisions:
- JWT tokens carry org_id and agent_id claims
- org_id is ALWAYS extracted from the token, never from tool arguments (ACL-01)
- decode_token() raises ValueError for invalid/missing tokens so callers can
  return a structured isError response to the agent
- create_token() is provided for testing and CLI use only

Usage in tool functions:
    from fastmcp.server.dependencies import get_http_headers
    from hivemind.server.auth import decode_token, AuthContext

    def some_tool(...) -> ...:
        headers = get_http_headers()
        auth_header = headers.get("authorization", "")
        if not auth_header.startswith("Bearer "):
            return error_response("Missing or invalid Authorization header")
        token = auth_header[len("Bearer "):]
        ctx = decode_token(token)
        # Use ctx.org_id, ctx.agent_id
"""

from __future__ import annotations

from dataclasses import dataclass

from jose import JWTError, jwt

from hivemind.config import settings


@dataclass
class AuthContext:
    """Authentication context extracted from a verified JWT.

    Attributes:
        org_id:   Organisation identifier — used for namespace isolation (ACL-01).
        agent_id: Agent identifier — stored as source_agent_id in DB records.
    """

    org_id: str
    agent_id: str


def decode_token(token: str) -> AuthContext:
    """Decode a HS256 JWT and return an AuthContext.

    Args:
        token: Raw JWT string (without 'Bearer ' prefix).

    Returns:
        AuthContext populated with org_id and agent_id from token claims.

    Raises:
        ValueError: If the token is invalid, expired, or missing required claims.
    """
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=["HS256"])
    except JWTError as exc:
        raise ValueError(f"Invalid token: {exc}") from exc

    org_id = payload.get("org_id")
    agent_id = payload.get("agent_id")

    if not org_id:
        raise ValueError("Token missing required claim: org_id")
    if not agent_id:
        raise ValueError("Token missing required claim: agent_id")

    return AuthContext(org_id=str(org_id), agent_id=str(agent_id))


def create_token(org_id: str, agent_id: str) -> str:
    """Create a HS256 JWT with org_id and agent_id claims.

    This is a utility function for testing and CLI use only.
    Production tokens should be issued by a proper auth service.

    Args:
        org_id:   Organisation identifier to embed in the token.
        agent_id: Agent identifier to embed in the token.

    Returns:
        Signed JWT string.
    """
    return jwt.encode(
        {"org_id": org_id, "agent_id": agent_id},
        settings.secret_key,
        algorithm="HS256",
    )
