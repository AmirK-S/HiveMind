"""Stage 3 of the dedup pipeline: LLM semantic duplicate confirmation.

Calls an LLM to confirm whether two knowledge items are semantic duplicates
(same information, possibly different wording). This is the final gate before
a DUPLICATE action is returned.

The LLM stage is optional:
- If no API key is configured, it returns is_duplicate=False with a
  descriptive reason — the cosine + MinHash stages still provide value.
- If the LLM API call fails or times out (10s), it logs a warning and
  returns is_duplicate=False (non-blocking degradation).

Supported providers: anthropic (default). The _call_llm() abstraction allows
swapping to another provider by overriding the internal function.
"""

from __future__ import annotations

import json
import logging
import re

import httpx

logger = logging.getLogger(__name__)

# Timeout for LLM API calls — avoids blocking the dedup pipeline indefinitely
_LLM_TIMEOUT_SECONDS = 10.0

# Prompt template for semantic duplicate detection
_DEDUP_PROMPT = (
    "You are a deduplication assistant. Compare these two knowledge items and "
    "determine if they are semantically duplicate (same information, possibly "
    "different wording). Respond with JSON only — no explanation outside the JSON:\n\n"
    '{{"is_duplicate": bool, "confidence": float, "reason": string}}\n\n'
    "ITEM A:\n{content_a}\n\nITEM B:\n{content_b}"
)


async def _call_llm(prompt: str, api_key: str, model: str) -> str:
    """Call the Anthropic messages API with the given prompt.

    Args:
        prompt:  The user message to send.
        api_key: Anthropic API key.
        model:   Model identifier (e.g. "claude-3-haiku-20240307").

    Returns:
        The model's text response as a string.

    Raises:
        httpx.HTTPError: On network or API errors.
        TimeoutError: If the call exceeds _LLM_TIMEOUT_SECONDS.
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
        # Anthropic messages API: content is a list of blocks
        return data["content"][0]["text"]


def _parse_llm_response(raw: str) -> dict:
    """Parse the LLM response JSON, with fallback on malformed output.

    Args:
        raw: The raw LLM text response (may contain markdown fencing).

    Returns:
        Dict with is_duplicate (bool), confidence (float), reason (str).
    """
    # Strip markdown code fences if present
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw.strip(), flags=re.MULTILINE)
    try:
        parsed = json.loads(cleaned)
        return {
            "is_duplicate": bool(parsed.get("is_duplicate", False)),
            "confidence": float(parsed.get("confidence", 0.0)),
            "reason": str(parsed.get("reason", "")),
        }
    except (json.JSONDecodeError, KeyError, TypeError) as exc:
        logger.warning("LLM stage: failed to parse response JSON — %s. Raw: %.200s", exc, raw)
        return {
            "is_duplicate": False,
            "confidence": 0.0,
            "reason": f"LLM stage: response parse failed — {exc}",
        }


async def confirm_duplicate_llm(content_a: str, content_b: str) -> dict:
    """Use the configured LLM to confirm whether two items are semantic duplicates.

    This is Stage 3 of the dedup pipeline. It is intentionally optional:
    - If no API key is configured (settings.anthropic_api_key is empty),
      it returns is_duplicate=False with a "stage skipped" reason.
    - If the LLM API call fails or times out, it logs a warning and returns
      is_duplicate=False — the pipeline continues without blocking.

    Args:
        content_a: The new content being evaluated.
        content_b: The existing knowledge item content to compare against.

    Returns:
        Dict with:
          is_duplicate (bool): True if LLM confirms semantic duplication.
          confidence (float): 0.0–1.0 confidence score.
          reason (str): Human-readable explanation from the LLM.
    """
    from hivemind.config import settings  # lazy import — avoid circular deps

    # Skip LLM stage if no API key configured — graceful degradation
    if not settings.anthropic_api_key:
        return {
            "is_duplicate": False,
            "confidence": 0.0,
            "reason": "LLM stage skipped — no API key configured",
        }

    prompt = _DEDUP_PROMPT.format(content_a=content_a, content_b=content_b)

    try:
        raw_response = await _call_llm(
            prompt=prompt,
            api_key=settings.anthropic_api_key,
            model=settings.llm_model,
        )
        return _parse_llm_response(raw_response)
    except httpx.TimeoutException:
        logger.warning("LLM stage: API call timed out after %ss — skipping stage", _LLM_TIMEOUT_SECONDS)
        return {
            "is_duplicate": False,
            "confidence": 0.0,
            "reason": f"LLM stage skipped — API call timed out after {_LLM_TIMEOUT_SECONDS}s",
        }
    except httpx.HTTPError as exc:
        logger.warning("LLM stage: HTTP error calling LLM API — %s", exc)
        return {
            "is_duplicate": False,
            "confidence": 0.0,
            "reason": f"LLM stage skipped — API error: {exc}",
        }
    except Exception as exc:
        logger.warning("LLM stage: unexpected error — %s", exc)
        return {
            "is_duplicate": False,
            "confidence": 0.0,
            "reason": f"LLM stage skipped — unexpected error: {exc}",
        }
