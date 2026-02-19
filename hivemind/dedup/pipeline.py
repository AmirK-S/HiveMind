"""Three-stage near-duplicate detection pipeline (KM-03).

Orchestrates the three dedup stages in sequence:
  Stage 1 (Cosine): Find top-10 most similar items by embedding distance.
  Stage 2 (MinHash): Narrow candidates to those also matching by Jaccard similarity.
  Stage 3 (LLM): Confirm semantic duplicates above confidence threshold.

Each stage acts as a filter — returning early with ADD if the evidence for
duplication is insufficient. Only items confirmed by all three stages result
in a DUPLICATE action.

LLM stage is optional (graceful degradation when API key is missing):
  - No API key → cosine + MinHash stages run, LLM is skipped, returns ADD.

The pipeline is non-blocking: if any stage fails internally, it degrades
gracefully rather than surfacing errors to the caller.
"""

from __future__ import annotations

import logging

from hivemind.dedup.cosine_stage import find_cosine_candidates
from hivemind.dedup.llm_stage import confirm_duplicate_llm
from hivemind.dedup.minhash_stage import find_minhash_candidates

logger = logging.getLogger(__name__)

# Maximum number of candidates passed to the LLM stage — keeps API costs bounded
_MAX_LLM_CANDIDATES = 3


async def run_dedup_pipeline(content: str, org_id: str) -> dict:
    """Run the three-stage dedup pipeline for a candidate knowledge item.

    Stages are run in order. Each stage filters the candidate set — if the
    filtered set becomes empty, the pipeline returns ADD immediately without
    running remaining stages.

    Args:
        content: The new knowledge content to check for near-duplicates.
        org_id:  The contributing org's ID for namespace-scoped candidate search.

    Returns:
        Dict with:
          action (str):        "ADD" or "DUPLICATE".
          duplicate_of (str):  ID of the best duplicate match (DUPLICATE only).
          confidence (float):  LLM confidence score (DUPLICATE only).
          duplicates (list):   All candidate dicts found across stages.
          stages_run (list):   Names of stages that were executed, in order.
    """
    stages_run: list[str] = []

    # ------------------------------------------------------------------
    # Stage 1: Cosine similarity candidate retrieval
    # ------------------------------------------------------------------
    stages_run.append("cosine")
    cosine_candidates = await find_cosine_candidates(content, org_id, top_k=10)

    if not cosine_candidates:
        # No candidates within similarity threshold — clearly not a duplicate
        logger.debug("Dedup pipeline: no cosine candidates found — ADD")
        return {
            "action": "ADD",
            "duplicate_of": None,
            "confidence": None,
            "duplicates": [],
            "stages_run": stages_run,
        }

    # ------------------------------------------------------------------
    # Stage 2: MinHash LSH — lexical near-duplicate filter
    # Keeps only candidates that appear in BOTH cosine and MinHash results.
    # ------------------------------------------------------------------
    stages_run.append("minhash")
    minhash_ids = set(find_minhash_candidates(content))

    cosine_ids = {c["id"] for c in cosine_candidates}
    intersection_ids = cosine_ids & minhash_ids

    if not intersection_ids:
        # Items are similar by embedding but NOT by Jaccard — different content.
        # Return ADD with cosine candidates so caller has context.
        logger.debug(
            "Dedup pipeline: %d cosine candidates but no MinHash overlap — ADD",
            len(cosine_candidates),
        )
        return {
            "action": "ADD",
            "duplicate_of": None,
            "confidence": None,
            "duplicates": cosine_candidates,
            "stages_run": stages_run,
        }

    # Narrow candidates to intersection only
    intersection_candidates = [c for c in cosine_candidates if c["id"] in intersection_ids]

    # ------------------------------------------------------------------
    # Stage 3: LLM semantic confirmation (optional — graceful skip)
    # ------------------------------------------------------------------
    stages_run.append("llm")

    # Limit to top candidates by cosine distance (already sorted ascending)
    llm_candidates = intersection_candidates[:_MAX_LLM_CANDIDATES]

    best_match_id: str | None = None
    best_confidence: float = 0.0
    best_reason: str = ""
    confirmed = False

    for candidate in llm_candidates:
        result = await confirm_duplicate_llm(content, candidate["content"])

        if result["is_duplicate"]:
            # Track the best confirmed match by confidence
            if result["confidence"] > best_confidence:
                best_confidence = result["confidence"]
                best_match_id = candidate["id"]
                best_reason = result["reason"]
                confirmed = True

    if confirmed:
        logger.info(
            "Dedup pipeline: DUPLICATE confirmed (id=%s, confidence=%.2f)",
            best_match_id,
            best_confidence,
        )
        return {
            "action": "DUPLICATE",
            "duplicate_of": best_match_id,
            "confidence": best_confidence,
            "reason": best_reason,
            "duplicates": intersection_candidates,
            "stages_run": stages_run,
        }

    # LLM did not confirm any duplicate — items are similar but semantically distinct
    logger.debug(
        "Dedup pipeline: %d intersection candidates, LLM did not confirm duplicate — ADD",
        len(intersection_candidates),
    )
    return {
        "action": "ADD",
        "duplicate_of": None,
        "confidence": best_confidence,
        "duplicates": intersection_candidates,
        "stages_run": stages_run,
    }
