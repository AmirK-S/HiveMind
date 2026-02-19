"""LLM-assisted conflict resolution with four possible outcomes (KM-07).

When the dedup pipeline finds a near-duplicate, resolve_conflict() determines
the relationship between the new content and the existing item, then
apply_conflict_resolution() executes the appropriate database action.

Outcome vocabulary:
  UPDATE         — new supersedes existing (expire old, insert new)
  ADD            — items coexist (insert new, leave old unchanged)
  NOOP           — new adds nothing (block insert, return informational response)
  VERSION_FORK   — both valid but for different version scopes (world-time split)
  FLAGGED_FOR_REVIEW — multi-hop conflict; human review required

Fallback behavior:
  - If no LLM API key configured → defaults to ADD (let the item through)
  - If LLM API call fails → defaults to ADD (non-blocking degradation)
  - Multi-hop conflicts (is_direct_conflict=false) → FLAGGED_FOR_REVIEW
"""

from __future__ import annotations

import json
import logging
import re

import httpx

logger = logging.getLogger(__name__)

# Timeout for conflict resolution LLM calls
_LLM_TIMEOUT_SECONDS = 10.0

# Prompt template for conflict resolution
_CONFLICT_PROMPT = """\
You are a knowledge conflict resolver. Compare NEW knowledge with EXISTING knowledge \
and determine the appropriate action. Respond with JSON only — no explanation outside the JSON:

{{"action": "UPDATE" | "ADD" | "NOOP" | "VERSION_FORK", "reason": string, "is_direct_conflict": bool}}

Rules:
- UPDATE: New knowledge supersedes existing (newer version, corrected info, better explanation)
- ADD: New knowledge is distinct enough to coexist (different angle, complementary perspective)
- NOOP: New knowledge adds nothing beyond existing (exact or near-exact semantic duplicate)
- VERSION_FORK: Both are valid but for different versions/contexts (e.g. Python 3.11 vs 3.12 behavior)
- Only resolve DIRECT single-hop conflicts. If the conflict involves multi-hop reasoning \
across multiple items, set is_direct_conflict=false.

NEW KNOWLEDGE:
{new_content}

EXISTING KNOWLEDGE:
{existing_content}"""

# Valid outcome values
_VALID_ACTIONS = frozenset({"UPDATE", "ADD", "NOOP", "VERSION_FORK"})


async def _call_conflict_llm(prompt: str, api_key: str, model: str) -> str:
    """Call the Anthropic messages API for conflict resolution.

    Args:
        prompt:  The formatted conflict resolution prompt.
        api_key: Anthropic API key.
        model:   Model identifier.

    Returns:
        The model's text response as a string.

    Raises:
        httpx.HTTPError: On network or API errors.
        httpx.TimeoutException: If the call exceeds _LLM_TIMEOUT_SECONDS.
    """
    async with httpx.AsyncClient(timeout=_LLM_TIMEOUT_SECONDS) as client:
        response = await client.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": model,
                "max_tokens": 256,
                "messages": [{"role": "user", "content": prompt}],
            },
        )
        response.raise_for_status()
        data = response.json()
        return data["content"][0]["text"]


def _parse_conflict_response(raw: str) -> dict:
    """Parse the LLM conflict resolution JSON response.

    Args:
        raw: The raw LLM text response (may contain markdown fencing).

    Returns:
        Dict with action (str), reason (str), is_direct_conflict (bool).
        Falls back to {"action": "ADD", ...} on parse failure.
    """
    # Strip markdown code fences if present
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw.strip(), flags=re.MULTILINE)
    try:
        parsed = json.loads(cleaned)
        action = str(parsed.get("action", "ADD")).upper()
        # Validate action is one of the four expected values
        if action not in _VALID_ACTIONS:
            logger.warning(
                "Conflict resolver: unexpected action '%s' — defaulting to ADD", action
            )
            action = "ADD"
        return {
            "action": action,
            "reason": str(parsed.get("reason", "")),
            "is_direct_conflict": bool(parsed.get("is_direct_conflict", True)),
        }
    except (json.JSONDecodeError, KeyError, TypeError) as exc:
        logger.warning(
            "Conflict resolver: failed to parse LLM response — %s. Raw: %.200s", exc, raw
        )
        return {
            "action": "ADD",
            "reason": f"Parse error — defaulting to ADD: {exc}",
            "is_direct_conflict": True,
        }


async def resolve_conflict(
    new_content: str,
    existing_item: dict,
    org_id: str,
) -> dict:
    """Determine the relationship between new content and an existing near-duplicate.

    Uses the configured LLM to classify the conflict and recommend an action.
    Multi-hop conflicts are flagged for human review.

    If no API key is configured or the LLM call fails, defaults to ADD (let
    the item through) — non-blocking by design.

    Args:
        new_content:   The new knowledge content being contributed.
        existing_item: Dict representing the existing knowledge item (must have
                       at least 'id' and 'content' keys).
        org_id:        The contributing org's ID (for future routing/logging).

    Returns:
        Dict with:
          action (str):              One of UPDATE, ADD, NOOP, VERSION_FORK,
                                     or FLAGGED_FOR_REVIEW.
          reason (str):              Human-readable explanation.
          is_direct_conflict (bool): Whether this is a single-hop conflict.
          existing_item_id (str):    ID of the existing item being compared.
    """
    from hivemind.config import settings  # lazy import — avoid circular deps

    existing_item_id = existing_item.get("id", "")
    existing_content = existing_item.get("content", "")

    # Fallback: no API key — default to ADD (non-blocking)
    if not settings.anthropic_api_key:
        logger.debug(
            "Conflict resolver: no API key configured — defaulting to ADD (org=%s)", org_id
        )
        return {
            "action": "ADD",
            "reason": "No LLM API key configured — defaulting to ADD",
            "is_direct_conflict": True,
            "existing_item_id": existing_item_id,
        }

    prompt = _CONFLICT_PROMPT.format(
        new_content=new_content,
        existing_content=existing_content,
    )

    try:
        raw_response = await _call_conflict_llm(
            prompt=prompt,
            api_key=settings.anthropic_api_key,
            model=settings.llm_model,
        )
        parsed = _parse_conflict_response(raw_response)

        # Multi-hop conflict: flag for human review (KM-07 explicit constraint)
        if not parsed["is_direct_conflict"]:
            logger.info(
                "Conflict resolver: multi-hop conflict detected — flagging for review "
                "(existing_item=%s)",
                existing_item_id,
            )
            return {
                "action": "FLAGGED_FOR_REVIEW",
                "reason": parsed["reason"],
                "is_direct_conflict": False,
                "existing_item_id": existing_item_id,
            }

        return {
            "action": parsed["action"],
            "reason": parsed["reason"],
            "is_direct_conflict": parsed["is_direct_conflict"],
            "existing_item_id": existing_item_id,
        }

    except httpx.TimeoutException:
        logger.warning(
            "Conflict resolver: LLM API call timed out after %ss — defaulting to ADD",
            _LLM_TIMEOUT_SECONDS,
        )
        return {
            "action": "ADD",
            "reason": f"LLM API timed out after {_LLM_TIMEOUT_SECONDS}s — defaulting to ADD",
            "is_direct_conflict": True,
            "existing_item_id": existing_item_id,
        }
    except httpx.HTTPError as exc:
        logger.warning("Conflict resolver: HTTP error — %s — defaulting to ADD", exc)
        return {
            "action": "ADD",
            "reason": f"LLM API error: {exc} — defaulting to ADD",
            "is_direct_conflict": True,
            "existing_item_id": existing_item_id,
        }
    except Exception as exc:
        logger.warning("Conflict resolver: unexpected error — %s — defaulting to ADD", exc)
        return {
            "action": "ADD",
            "reason": f"Unexpected error: {exc} — defaulting to ADD",
            "is_direct_conflict": True,
            "existing_item_id": existing_item_id,
        }


async def apply_conflict_resolution(
    resolution: dict,
    new_content: str,
    existing_item_id: str,
    org_id: str,
) -> dict:
    """Apply the conflict resolution outcome to the database.

    Executes the appropriate database action based on the resolution action:
    - UPDATE: Expire the existing item (system-time end = now). New item proceeds.
    - ADD: No DB changes. New item proceeds normally.
    - NOOP: Block new item insertion. Returns applied="NOOP".
    - VERSION_FORK: Expire existing item world-time (invalid_at = now).
                    New item will carry valid_at = now. Returns sibling info.

    Args:
        resolution:        The result dict from resolve_conflict().
        new_content:       The new knowledge content (used for logging only).
        existing_item_id:  UUID string of the existing knowledge item.
        org_id:            The contributing org's ID (for org isolation on update).

    Returns:
        Dict with 'applied' key indicating what was done, plus action-specific fields.
    """
    import datetime
    import uuid

    from sqlalchemy import update

    from hivemind.db.models import KnowledgeItem
    from hivemind.db.session import get_session

    action = resolution.get("action", "ADD")
    now = datetime.datetime.now(datetime.timezone.utc)

    if action == "UPDATE":
        # System-time invalidation: expire the existing item so it's no longer "current"
        async with get_session() as session:
            await session.execute(
                update(KnowledgeItem)
                .where(KnowledgeItem.id == uuid.UUID(existing_item_id))
                .where(KnowledgeItem.org_id == org_id)  # org isolation (ACL-01)
                .values(expired_at=now)
            )
            await session.commit()

        logger.info(
            "Conflict resolver: UPDATE applied — expired item %s (org=%s)",
            existing_item_id,
            org_id,
        )
        return {
            "applied": "UPDATE",
            "expired_item_id": existing_item_id,
        }

    elif action == "NOOP":
        # Block the new item — it adds nothing beyond the existing knowledge
        logger.info(
            "Conflict resolver: NOOP — blocking duplicate contribution (existing=%s, org=%s)",
            existing_item_id,
            org_id,
        )
        return {
            "applied": "NOOP",
            "reason": resolution.get("reason", "duplicate"),
        }

    elif action == "VERSION_FORK":
        # World-time invalidation: set invalid_at on existing item.
        # The new item will be inserted by the caller with valid_at = now.
        async with get_session() as session:
            await session.execute(
                update(KnowledgeItem)
                .where(KnowledgeItem.id == uuid.UUID(existing_item_id))
                .where(KnowledgeItem.org_id == org_id)  # org isolation (ACL-01)
                .values(invalid_at=now)
            )
            await session.commit()

        logger.info(
            "Conflict resolver: VERSION_FORK applied — invalidated item %s (org=%s); "
            "new item carries valid_at=%s",
            existing_item_id,
            org_id,
            now.isoformat(),
        )
        return {
            "applied": "VERSION_FORK",
            "sibling_id": existing_item_id,  # the now-invalidated sibling
            "valid_at": now,                 # caller should set this on new item
        }

    else:
        # ADD (or FLAGGED_FOR_REVIEW): no DB changes — new item proceeds
        logger.debug(
            "Conflict resolver: %s — no DB changes, new item proceeds (org=%s)",
            action,
            org_id,
        )
        return {"applied": action}
