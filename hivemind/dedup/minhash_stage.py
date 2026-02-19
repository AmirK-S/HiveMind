"""Stage 2 of the dedup pipeline: MinHash LSH near-duplicate detection.

Uses the datasketch library's MinHash and MinHashLSH to detect lexical
near-duplicates that embedding cosine similarity may miss (e.g., two items
using different but synonymous word choices, or the same content with minor
edits such as punctuation or formatting changes).

The LSH index is a module-level singleton populated incrementally as items
are approved (via insert_into_lsh).  This avoids rebuilding on every request.
"""

from __future__ import annotations

import logging

from datasketch import MinHash, MinHashLSH

logger = logging.getLogger(__name__)

# Module-level singleton — initialized lazily on first call to get_lsh_index()
_lsh_index: MinHashLSH | None = None


def get_lsh_index() -> MinHashLSH:
    """Return the module-level MinHash LSH singleton, creating it if needed.

    Reads minhash_threshold and minhash_num_perm from settings at creation
    time. Uses a lazy import to avoid circular dependency with hivemind.config.

    Returns:
        The initialized MinHashLSH instance.
    """
    global _lsh_index
    if _lsh_index is None:
        from hivemind.config import settings  # lazy import — avoid circular deps

        _lsh_index = MinHashLSH(
            threshold=settings.minhash_threshold,
            num_perm=settings.minhash_num_perm,
        )
        logger.debug(
            "MinHash LSH index created (threshold=%.2f, num_perm=%d)",
            settings.minhash_threshold,
            settings.minhash_num_perm,
        )
    return _lsh_index


def minhash_for_text(text: str, num_perm: int = 128) -> MinHash:
    """Compute a MinHash signature for the given text.

    Tokenizes text by lowercasing and whitespace-splitting, then updates
    the MinHash object with each token's encoded bytes.

    Args:
        text:     The text to compute a MinHash for.
        num_perm: Number of permutations (hash functions). Higher = more
                  accurate but slower. Default 128 matches settings default.

    Returns:
        A MinHash object representing the text's Jaccard similarity signature.
    """
    mh = MinHash(num_perm=num_perm)
    for token in text.lower().split():
        mh.update(token.encode("utf-8"))
    return mh


def insert_into_lsh(item_id: str, content: str) -> None:
    """Insert a knowledge item into the LSH index.

    Computes a MinHash for the content and inserts it using item_id as the key.
    If the item is already in the index (same key), the duplicate is silently
    ignored — this is safe and expected during server restart or re-indexing.

    Args:
        item_id: The knowledge item's UUID string (used as the LSH key).
        content: The item's text content to compute the MinHash from.
    """
    from hivemind.config import settings  # lazy import — avoid circular deps

    lsh = get_lsh_index()
    mh = minhash_for_text(content, num_perm=settings.minhash_num_perm)
    try:
        lsh.insert(item_id, mh)
    except ValueError:
        # Item already in index — safe to ignore (e.g. duplicate insert on restart)
        logger.debug("MinHash LSH: item %s already in index, skipping insert", item_id)


def find_minhash_candidates(content: str) -> list[str]:
    """Query the LSH index for items with Jaccard similarity >= threshold.

    Args:
        content: The text to query against the LSH index.

    Returns:
        List of item ID strings with Jaccard similarity at or above the
        configured minhash_threshold. Returns empty list if index is empty.
    """
    from hivemind.config import settings  # lazy import — avoid circular deps

    lsh = get_lsh_index()
    mh = minhash_for_text(content, num_perm=settings.minhash_num_perm)
    try:
        return lsh.query(mh)
    except Exception as exc:
        logger.warning("MinHash LSH query failed: %s", exc)
        return []


async def rebuild_lsh_index() -> int:
    """Rebuild the LSH index from all active knowledge items in the database.

    Drops and recreates the module-level singleton, then queries all
    non-deleted, non-expired items and inserts their MinHash signatures.

    Use this at server startup or when minhash_threshold/num_perm config
    changes (config changes require a restart anyway).

    Returns:
        The count of items successfully indexed.
    """
    global _lsh_index

    from hivemind.config import settings  # lazy import — avoid circular deps
    from hivemind.db.models import KnowledgeItem
    from hivemind.db.session import get_session
    from sqlalchemy import select

    # Drop and recreate the singleton with current config
    _lsh_index = MinHashLSH(
        threshold=settings.minhash_threshold,
        num_perm=settings.minhash_num_perm,
    )

    count = 0
    async with get_session() as session:
        stmt = (
            select(KnowledgeItem.id, KnowledgeItem.content)
            .where(KnowledgeItem.deleted_at.is_(None))
            .where(KnowledgeItem.expired_at.is_(None))
        )
        result = await session.execute(stmt)
        rows = result.all()

    for item_id, content in rows:
        mh = minhash_for_text(content, num_perm=settings.minhash_num_perm)
        try:
            _lsh_index.insert(str(item_id), mh)
            count += 1
        except ValueError:
            logger.debug("rebuild_lsh_index: item %s already in index", item_id)

    logger.info("MinHash LSH index rebuilt — %d items indexed", count)
    return count
