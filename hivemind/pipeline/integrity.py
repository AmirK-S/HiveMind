"""
Content integrity verification helpers for HiveMind.

Provides SHA-256 hash computation and verification for knowledge item content.
The hash is stored at insert time (content_hash column, set in Phase 1) and
re-verified at retrieval time to detect tampering.

Requirements addressed:
  - SEC-02: Content hash (SHA-256) on every knowledge item for integrity
    verification. Hash storage was implemented in Phase 1; this module provides
    the retrieval-time verification function.

Design decisions:
- Only stdlib hashlib — no external dependencies.
- compute_content_hash() is deterministic and side-effect free: same input
  always produces the same hex digest.
- verify_content_hash() does a constant-time-equivalent comparison via string
  equality on the hex digest (SHA-256 output is 64 ASCII chars; Python string
  equality short-circuits but the attacker controls neither value).

Exports: compute_content_hash, verify_content_hash
"""

from __future__ import annotations

import hashlib


def compute_content_hash(content: str) -> str:
    """Return the SHA-256 hex digest of *content*.

    Args:
        content: The knowledge item's raw text content.

    Returns:
        64-character lowercase hex string (SHA-256 digest).

    Example:
        >>> h = compute_content_hash("Hello, world!")
        >>> len(h)
        64
    """
    return hashlib.sha256(content.encode()).hexdigest()


def verify_content_hash(content: str, stored_hash: str) -> bool:
    """Return True if *content* matches *stored_hash*.

    Args:
        content: The retrieved knowledge item content.
        stored_hash: The SHA-256 hex digest stored at insert time.

    Returns:
        True if the content is intact (hash matches), False if tampered.

    Example:
        >>> h = compute_content_hash("Hello, world!")
        >>> verify_content_hash("Hello, world!", h)
        True
        >>> verify_content_hash("Tampered!", h)
        False
    """
    return compute_content_hash(content) == stored_hash
