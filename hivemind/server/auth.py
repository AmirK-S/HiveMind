"""Bearer token authentication for the HiveMind MCP server.

Design decisions:
- JWT tokens carry org_id and agent_id claims
- hm_-prefixed tokens are API keys routed through validate_api_key()
- org_id is ALWAYS extracted from the token, never from tool arguments (ACL-01)
- decode_token() raises ValueError for invalid/missing tokens so callers can
  return a structured isError response to the agent
- decode_token_async() is the preferred entry point for MCP tool handlers
  as it supports both JWT and hm_-prefixed API keys natively (INFRA-04)
- create_token() is provided for testing and CLI use only

Usage in tool functions (preferred — handles both JWT and API keys):
    from fastmcp.server.dependencies import get_http_headers
    from hivemind.server.auth import decode_token_async, AuthContext

    async def some_tool(...) -> ...:
        headers = get_http_headers()
        auth_header = headers.get("authorization", "")
        if not auth_header.startswith("Bearer "):
            return error_response("Missing or invalid Authorization header")
        token = auth_header[len("Bearer "):]
        ctx = await decode_token_async(token)
        # Use ctx.org_id, ctx.agent_id, ctx.tier

Usage for JWT-only callers (backward compatible):
    from hivemind.server.auth import decode_token, AuthContext

    def some_tool(...) -> ...:
        token = ...
        ctx = decode_token(token)  # JWT only — does not handle hm_ keys
"""

from __future__ import annotations

from dataclasses import dataclass, field

from jose import JWTError, jwt

from hivemind.config import settings


@dataclass
class AuthContext:
    """Authentication context extracted from a verified JWT or API key.

    Attributes:
        org_id:   Organisation identifier — used for namespace isolation (ACL-01).
        agent_id: Agent identifier — stored as source_agent_id in DB records.
        tier:     Billing tier from API key authentication (e.g. "free", "pro",
                  "enterprise"). None when authenticated via JWT (INFRA-04).
    """

    org_id: str
    agent_id: str
    tier: str | None = field(default=None)  # Set when authenticated via API key (INFRA-04)


def decode_token(token: str) -> AuthContext:
    """Decode a HS256 JWT and return an AuthContext.

    JWT-only entry point — does NOT handle hm_-prefixed API keys. Use
    decode_token_async() in async contexts (e.g. MCP tool handlers) to
    support both JWT and API key authentication.

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


async def decode_token_async(token: str) -> AuthContext:
    """Decode a JWT or validate an hm_-prefixed API key. Async entry point.

    Preferred over decode_token() in async contexts (MCP tool handlers).
    Detects hm_-prefixed tokens and routes them through validate_api_key()
    to return an AuthContext with tier information (INFRA-04). JWT tokens
    fall through to the synchronous decode_token() logic.

    Args:
        token: Raw token string (without 'Bearer ' prefix). May be a JWT
               or an hm_-prefixed API key.

    Returns:
        AuthContext populated from JWT claims or API key DB record.
        When authenticated via API key, ctx.tier is set to the key's tier.

    Raises:
        ValueError: If the token is invalid, expired, missing required claims,
                    or the API key is inactive/not found.

    Requirements: INFRA-04 (API key auth with tier and request counting).
    """
    # INFRA-04: Detect hm_-prefixed API keys and route through validate_api_key()
    if token.startswith("hm_"):
        from hivemind.security.api_key import (  # noqa: PLC0415
            increment_request_count,
            validate_api_key,
        )

        result = await validate_api_key(raw_key=token)
        if result is None:
            raise ValueError("Invalid or inactive API key")

        # Increment request count (best-effort — don't block auth on counter failure)
        try:
            await increment_request_count(result["api_key_id"])
        except Exception:
            pass

        return AuthContext(
            org_id=result["org_id"],
            agent_id=result["agent_id"],
            tier=result["tier"],
        )

    # Fall through to existing JWT decode logic (synchronous — no DB query needed)
    return decode_token(token)


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
