"""manage_roles MCP tool for HiveMind.

Organization admins can manage agent roles and access policies within their
namespace. Supports three RBAC levels: namespace, category, and item (ACL-03).

Admin check: The calling agent must have the 'admin' role in their org's domain.
If not, the request is rejected (ACL-04).

Supported actions:
- assign_role:      Assign a role to an agent in the org namespace.
- get_roles:        List all roles assigned to an agent in the org namespace.
- add_permission:   Add a policy granting an agent/role access to a resource.
- remove_permission: Remove an existing access policy.

Object (obj) format examples:
- "namespace:<org_id>"   — org-wide access
- "category:bug_fix"     — category-level access
- "item:<uuid>"          — item-level access

Requirements: ACL-03 (three-level RBAC), ACL-04 (org admin role management).
"""

from __future__ import annotations

from fastmcp.server.dependencies import get_http_headers
from mcp.types import CallToolResult, TextContent

from hivemind.server.auth import decode_token


def _extract_auth(headers: dict[str, str]):
    """Extract and decode the Authorization bearer token.

    Args:
        headers: HTTP headers dict from get_http_headers().

    Returns:
        AuthContext with org_id and agent_id.

    Raises:
        ValueError: If the Authorization header is missing, malformed, or the
                    token is invalid.
    """
    auth_header = headers.get("authorization", "")
    if not auth_header.startswith("Bearer "):
        raise ValueError("Missing or invalid Authorization header. Expected 'Bearer <token>'.")
    token = auth_header[len("Bearer "):]
    return decode_token(token)


def _error(message: str) -> CallToolResult:
    """Return a structured MCP isError response."""
    return CallToolResult(
        content=[TextContent(type="text", text=message)],
        isError=True,
    )


async def manage_roles(
    action: str,
    agent_id: str,
    role: str | None = None,
    obj: str | None = None,
    permission: str | None = None,
) -> dict | CallToolResult:
    """Manage agent roles and access policies within an org namespace.

    Organization admins can assign roles, query role assignments, and manage
    fine-grained access policies at the namespace, category, or item level.

    Admin gate: The calling agent must have the 'admin' role in their org.
    Non-admin callers receive an error regardless of the requested action (ACL-04).

    Args:
        action:     Operation to perform. One of:
                    - "assign_role":       Assign *role* to *agent_id*.
                    - "get_roles":         List all roles for *agent_id*.
                    - "add_permission":    Add policy (agent_id/role, obj, permission).
                    - "remove_permission": Remove policy (agent_id/role, obj, permission).
        agent_id:   Target agent (or role name for permission actions).
        role:       Role name for "assign_role" action (e.g. "admin", "contributor").
        obj:        Resource object for permission actions. Format:
                    - "namespace:<org_id>"  — org-wide
                    - "category:<cat>"      — category-level
                    - "item:<uuid>"         — item-level
        permission: Permission for policy actions (e.g. "read", "write", "*").

    Returns:
        Dict describing the outcome on success.
        CallToolResult with isError=True on any failure.

    Requirements: ACL-03 (three-level RBAC), ACL-04 (org admin management).
    """
    from hivemind.security.rbac import (  # noqa: PLC0415
        add_policy,
        add_role_for_user,
        enforce,
        get_roles_for_user,
        remove_policy,
    )

    # Step 1: Extract auth context from bearer token
    try:
        headers = get_http_headers()
        auth = _extract_auth(headers)
    except ValueError as exc:
        return _error(str(exc))

    # Step 2: Admin gate — caller must have admin role for their org namespace (ACL-04)
    namespace_obj = f"namespace:{auth.org_id}"
    is_admin = await enforce(auth.agent_id, auth.org_id, namespace_obj, "*")
    if not is_admin:
        return _error(
            "Only organization admins can manage roles. "
            "Your agent does not have admin privileges in this org."
        )

    # Step 3: Dispatch to the requested action
    valid_actions = ["assign_role", "get_roles", "add_permission", "remove_permission"]

    if action == "assign_role":
        # Requires: agent_id, role
        if not role:
            return _error("'assign_role' action requires the 'role' parameter.")
        await add_role_for_user(agent_id, role, auth.org_id)
        return {
            "action": "assign_role",
            "agent_id": agent_id,
            "role": role,
            "domain": auth.org_id,
            "message": f"Role '{role}' assigned to agent '{agent_id}' in org '{auth.org_id}'.",
        }

    elif action == "get_roles":
        # Requires: agent_id
        roles = await get_roles_for_user(agent_id, auth.org_id)
        return {
            "action": "get_roles",
            "agent_id": agent_id,
            "domain": auth.org_id,
            "roles": roles,
        }

    elif action == "add_permission":
        # Requires: agent_id (or role name as agent_id), obj, permission
        if not obj:
            return _error(
                "'add_permission' requires the 'obj' parameter. "
                "Examples: 'namespace:<org_id>', 'category:bug_fix', 'item:<uuid>'."
            )
        if not permission:
            return _error(
                "'add_permission' requires the 'permission' parameter. "
                "Examples: 'read', 'write', '*'."
            )
        added = await add_policy(agent_id, auth.org_id, obj, permission)
        return {
            "action": "add_permission",
            "subject": agent_id,
            "domain": auth.org_id,
            "obj": obj,
            "permission": permission,
            "added": added,
            "message": (
                f"Permission '{permission}' on '{obj}' granted to '{agent_id}'."
                if added else
                f"Permission already exists for '{agent_id}' on '{obj}' with action '{permission}'."
            ),
        }

    elif action == "remove_permission":
        # Requires: agent_id (or role name), obj, permission
        if not obj:
            return _error(
                "'remove_permission' requires the 'obj' parameter. "
                "Examples: 'namespace:<org_id>', 'category:bug_fix', 'item:<uuid>'."
            )
        if not permission:
            return _error(
                "'remove_permission' requires the 'permission' parameter. "
                "Examples: 'read', 'write', '*'."
            )
        removed = await remove_policy(agent_id, auth.org_id, obj, permission)
        return {
            "action": "remove_permission",
            "subject": agent_id,
            "domain": auth.org_id,
            "obj": obj,
            "permission": permission,
            "removed": removed,
            "message": (
                f"Permission '{permission}' on '{obj}' removed from '{agent_id}'."
                if removed else
                f"No matching permission found for '{agent_id}' on '{obj}' with action '{permission}'."
            ),
        }

    else:
        return _error(
            f"Unknown action '{action}'. Valid actions: {', '.join(valid_actions)}."
        )
