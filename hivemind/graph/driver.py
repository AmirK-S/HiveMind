"""Knowledge store driver abstraction for HiveMind (INFRA-02).

Follows Graphiti's GraphDriver interface pattern — a backend-agnostic ABC that
allows knowledge storage implementations to be swapped without changing callers.

**Design intent:**
- pgvector remains the operational store (PgVectorDriver wraps existing queries)
- FalkorDB is scaffolded for future graph traversal capabilities (Phase 3)
- get_driver() factory selects the backend by name string from config/env

**Abstraction shape:**
The ABC defines 7 core operations modeled after Graphiti's GraphDriver:
  store, fetch, search, delete, verify_integrity, find_similar, health_check

These map directly onto the operations already present in search_knowledge.py
and cli/client.py — the driver layer unifies them behind a single interface.

References:
  - INFRA-02: Backend-agnostic knowledge store interface
  - graphiti-core GraphDriver pattern: 11 core graph operations adapted to
    HiveMind's knowledge domain (no graph-specific nodes/edges at this layer)
"""

from __future__ import annotations

import hashlib
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


# ---------------------------------------------------------------------------
# Shared data types
# ---------------------------------------------------------------------------


@dataclass
class KnowledgeNode:
    """Unified knowledge representation across backends.

    Provides a backend-agnostic container that maps to KnowledgeItem ORM rows
    for PgVectorDriver and to graph entity nodes for FalkorDBDriver.
    """

    id: str
    content: str
    content_hash: str
    category: str
    org_id: str
    embedding: list[float] | None = None
    metadata: dict[str, Any] | None = field(default_factory=dict)


@dataclass
class SearchResult:
    """Search result with relevance score.

    score is normalised to [0.0, 1.0] where 1.0 means identical.  Derived
    from cosine distance: score = 1 - cosine_distance (unit vectors).
    """

    node: KnowledgeNode
    score: float  # 0.0 to 1.0 (higher = more relevant)


# ---------------------------------------------------------------------------
# Abstract base class
# ---------------------------------------------------------------------------


class KnowledgeStoreDriver(ABC):
    """Backend-agnostic interface for knowledge storage (INFRA-02).

    All methods are async so implementations can use asyncio DB clients,
    HTTP connections to graph databases, or any other async I/O.

    Callers depend only on this ABC — swapping backends requires only changing
    the driver returned by get_driver().
    """

    # ------------------------------------------------------------------
    # Write operations
    # ------------------------------------------------------------------

    @abstractmethod
    async def store(self, node: KnowledgeNode) -> str:
        """Persist a knowledge node.

        Args:
            node: The knowledge node to store.

        Returns:
            The stored node's ID (may differ from node.id if backend assigns IDs).
        """

    @abstractmethod
    async def delete(self, node_id: str, org_id: str) -> bool:
        """Soft-delete a knowledge node.

        Sets deleted_at rather than removing the row so provenance is preserved.

        Args:
            node_id: UUID string of the node to delete.
            org_id:  Organisation namespace — enforces ACL-01 isolation.

        Returns:
            True if the node existed and was deleted; False if not found.
        """

    # ------------------------------------------------------------------
    # Read operations
    # ------------------------------------------------------------------

    @abstractmethod
    async def fetch(self, node_id: str, org_id: str) -> KnowledgeNode | None:
        """Fetch a single knowledge node by ID with org scoping.

        Args:
            node_id: UUID string of the node to fetch.
            org_id:  Organisation namespace — enforces ACL-01 isolation.

        Returns:
            The KnowledgeNode if found and accessible; None otherwise.
        """

    @abstractmethod
    async def search(
        self,
        query_embedding: list[float],
        org_id: str,
        limit: int = 10,
        category: str | None = None,
    ) -> list[SearchResult]:
        """Vector similarity search over the knowledge store.

        Performs cosine distance ranking (same operation as _search() in
        search_knowledge.py) scoped to the org's private namespace plus public items.

        Args:
            query_embedding: Pre-computed embedding vector for the search query.
            org_id:          Organisation namespace — enforces ACL-01 isolation.
            limit:           Maximum number of results to return.
            category:        Optional category filter string.

        Returns:
            List of SearchResult ordered by descending relevance score.
        """

    @abstractmethod
    async def find_similar(
        self,
        content_embedding: list[float],
        org_id: str,
        threshold: float = 0.35,
        limit: int = 3,
    ) -> list[SearchResult]:
        """Near-duplicate detection — find existing nodes close to the given embedding.

        Uses the same cosine distance threshold as find_similar_knowledge() in
        cli/client.py.  The threshold is a *distance* value (lower = more similar):
        0.35 corresponds to ~65% similarity.

        Args:
            content_embedding: Pre-computed embedding for the candidate content.
            org_id:            Organisation namespace.
            threshold:         Maximum cosine distance (0.35 ≈ 65% similarity).
            limit:             Maximum number of results to return.

        Returns:
            List of SearchResult ordered by descending relevance score.
        """

    # ------------------------------------------------------------------
    # Integrity / health
    # ------------------------------------------------------------------

    @abstractmethod
    async def verify_integrity(self, node_id: str) -> bool:
        """Verify that stored content matches its content_hash.

        Fetches the node, recomputes SHA-256 of content, and compares with
        the stored content_hash field.  Returns False if the node is missing.

        Args:
            node_id: UUID string of the node to verify.

        Returns:
            True if content hash matches; False if tampered or not found.
        """

    @abstractmethod
    async def health_check(self) -> bool:
        """Check whether the backend is reachable.

        Returns:
            True if the backend responds successfully; False otherwise.
        """


# ---------------------------------------------------------------------------
# PgVector implementation
# ---------------------------------------------------------------------------


class PgVectorDriver(KnowledgeStoreDriver):
    """pgvector backend driver — wraps existing SQLAlchemy async queries.

    Uses get_session() from hivemind.db.session for all DB operations.
    Org isolation follows the ACL-01 pattern established in search_knowledge.py:
    results are scoped to (org_id == :org_id) OR (is_public == True).

    This driver consolidates the patterns already present in:
    - hivemind/server/tools/search_knowledge.py (_search, _fetch_by_id)
    - hivemind/cli/client.py (find_similar_knowledge)
    - hivemind/server/tools/delete_knowledge.py
    """

    async def store(self, node: KnowledgeNode) -> str:
        """Create a KnowledgeItem from a KnowledgeNode."""
        import datetime
        import uuid

        from sqlalchemy import select

        from hivemind.db.models import KnowledgeCategory, KnowledgeItem
        from hivemind.db.session import get_session

        async with get_session() as session:
            item = KnowledgeItem(
                org_id=node.org_id,
                source_agent_id=(node.metadata or {}).get("source_agent_id", "driver"),
                run_id=(node.metadata or {}).get("run_id"),
                content=node.content,
                content_hash=node.content_hash,
                category=KnowledgeCategory(node.category),
                confidence=(node.metadata or {}).get("confidence", 0.8),
                framework=(node.metadata or {}).get("framework"),
                language=(node.metadata or {}).get("language"),
                version=(node.metadata or {}).get("version"),
                tags=(node.metadata or {}).get("tags"),
                is_public=(node.metadata or {}).get("is_public", False),
                embedding=node.embedding,
                contributed_at=datetime.datetime.now(datetime.timezone.utc),
                approved_at=datetime.datetime.now(datetime.timezone.utc),
            )
            session.add(item)
            await session.commit()
            await session.refresh(item)
            return str(item.id)

    async def fetch(self, node_id: str, org_id: str) -> KnowledgeNode | None:
        """Fetch a single knowledge item with org isolation."""
        import uuid

        from sqlalchemy import select

        from hivemind.db.models import KnowledgeItem
        from hivemind.db.session import get_session

        try:
            item_uuid = uuid.UUID(node_id)
        except ValueError:
            return None

        async with get_session() as session:
            from sqlalchemy import select

            stmt = select(KnowledgeItem).where(
                KnowledgeItem.id == item_uuid,
                (KnowledgeItem.org_id == org_id) | (KnowledgeItem.is_public == True),  # noqa: E712
                KnowledgeItem.deleted_at.is_(None),
            )
            result = await session.execute(stmt)
            item = result.scalar_one_or_none()

        if item is None:
            return None

        return KnowledgeNode(
            id=str(item.id),
            content=item.content,
            content_hash=item.content_hash,
            category=item.category.value,
            org_id=item.org_id,
            embedding=list(item.embedding) if item.embedding is not None else None,
            metadata={
                "source_agent_id": item.source_agent_id,
                "run_id": item.run_id,
                "confidence": item.confidence,
                "framework": item.framework,
                "language": item.language,
                "version": item.version,
                "tags": item.tags,
                "is_public": item.is_public,
                "contributed_at": item.contributed_at.isoformat(),
                "approved_at": item.approved_at.isoformat(),
            },
        )

    async def search(
        self,
        query_embedding: list[float],
        org_id: str,
        limit: int = 10,
        category: str | None = None,
    ) -> list[SearchResult]:
        """Cosine distance search — same pattern as _search() in search_knowledge.py."""
        from sqlalchemy import select

        from hivemind.db.models import KnowledgeCategory, KnowledgeItem
        from hivemind.db.session import get_session

        async with get_session() as session:
            distance_col = KnowledgeItem.embedding.cosine_distance(query_embedding).label(
                "distance"
            )

            stmt = (
                select(KnowledgeItem, distance_col)
                .where(
                    (KnowledgeItem.org_id == org_id) | (KnowledgeItem.is_public == True)  # noqa: E712
                )
                .where(KnowledgeItem.embedding.isnot(None))
                .where(KnowledgeItem.deleted_at.is_(None))
            )

            if category is not None:
                try:
                    category_enum = KnowledgeCategory(category)
                    stmt = stmt.where(KnowledgeItem.category == category_enum)
                except ValueError:
                    return []

            stmt = stmt.order_by(distance_col.asc()).limit(limit)

            result = await session.execute(stmt)
            rows = result.all()

        return [
            SearchResult(
                node=KnowledgeNode(
                    id=str(item.id),
                    content=item.content,
                    content_hash=item.content_hash,
                    category=item.category.value,
                    org_id=item.org_id,
                    embedding=list(item.embedding) if item.embedding is not None else None,
                ),
                score=round(1 - distance, 4),
            )
            for item, distance in rows
        ]

    async def delete(self, node_id: str, org_id: str) -> bool:
        """Soft-delete a knowledge item — sets deleted_at timestamp."""
        import datetime
        import uuid

        from sqlalchemy import select

        from hivemind.db.models import KnowledgeItem
        from hivemind.db.session import get_session

        try:
            item_uuid = uuid.UUID(node_id)
        except ValueError:
            return False

        async with get_session() as session:
            stmt = select(KnowledgeItem).where(
                KnowledgeItem.id == item_uuid,
                KnowledgeItem.org_id == org_id,
                KnowledgeItem.deleted_at.is_(None),
            )
            result = await session.execute(stmt)
            item = result.scalar_one_or_none()

            if item is None:
                return False

            item.deleted_at = datetime.datetime.now(datetime.timezone.utc)
            await session.commit()
            return True

    async def verify_integrity(self, node_id: str) -> bool:
        """Recompute SHA-256 of content and compare with stored content_hash."""
        import uuid

        from sqlalchemy import select

        from hivemind.db.models import KnowledgeItem
        from hivemind.db.session import get_session

        try:
            item_uuid = uuid.UUID(node_id)
        except ValueError:
            return False

        async with get_session() as session:
            stmt = select(KnowledgeItem).where(KnowledgeItem.id == item_uuid)
            result = await session.execute(stmt)
            item = result.scalar_one_or_none()

        if item is None:
            return False

        computed_hash = hashlib.sha256(item.content.encode()).hexdigest()
        return computed_hash == item.content_hash

    async def find_similar(
        self,
        content_embedding: list[float],
        org_id: str,
        threshold: float = 0.35,
        limit: int = 3,
    ) -> list[SearchResult]:
        """Near-duplicate detection — same pattern as find_similar_knowledge() in cli/client.py."""
        from sqlalchemy import select

        from hivemind.db.models import KnowledgeItem
        from hivemind.db.session import get_session

        async with get_session() as session:
            distance_col = KnowledgeItem.embedding.cosine_distance(content_embedding).label(
                "distance"
            )

            stmt = (
                select(KnowledgeItem, distance_col)
                .where(
                    (KnowledgeItem.org_id == org_id) | (KnowledgeItem.is_public == True)  # noqa: E712
                )
                .where(KnowledgeItem.deleted_at.is_(None))
                .where(KnowledgeItem.embedding.isnot(None))
                .order_by(distance_col.asc())
                .limit(limit)
            )

            result = await session.execute(stmt)
            rows = result.all()

        return [
            SearchResult(
                node=KnowledgeNode(
                    id=str(item.id),
                    content=item.content,
                    content_hash=item.content_hash,
                    category=item.category.value,
                    org_id=item.org_id,
                    embedding=list(item.embedding) if item.embedding is not None else None,
                ),
                score=round(1 - distance, 4),
            )
            for item, distance in rows
            if distance <= threshold
        ]

    async def health_check(self) -> bool:
        """Execute SELECT 1 to verify DB connectivity."""
        from sqlalchemy import text

        from hivemind.db.session import get_session

        try:
            async with get_session() as session:
                await session.execute(text("SELECT 1"))
            return True
        except Exception:
            return False


# ---------------------------------------------------------------------------
# FalkorDB implementation (scaffold — Phase 3)
# ---------------------------------------------------------------------------


class FalkorDBDriver(KnowledgeStoreDriver):
    """FalkorDB graph database driver — scaffold for Phase 3 implementation.

    Wraps graphiti-core's FalkorDriver to provide graph-native query capabilities.
    Full implementation is deferred to Phase 3; only health_check is functional.

    All other methods raise NotImplementedError — callers should use PgVectorDriver
    for production knowledge storage until Phase 3 completes this driver.

    Args:
        host:     FalkorDB host address (from settings.falkordb_host).
        port:     FalkorDB port (from settings.falkordb_port).
        database: FalkorDB database name (from settings.falkordb_database).
    """

    def __init__(self, host: str, port: int, database: str) -> None:
        self._host = host
        self._port = port
        self._database = database
        # Lazy import — graphiti-core[falkordb] is optional and may not be installed
        from graphiti_core.driver.falkordb_driver import FalkorDriver  # noqa: PLC0415

        self._driver = FalkorDriver(host=host, port=port, database=database)

    async def store(self, node: KnowledgeNode) -> str:
        raise NotImplementedError(
            "FalkorDB driver not yet fully implemented — use PgVectorDriver"
        )

    async def fetch(self, node_id: str, org_id: str) -> KnowledgeNode | None:
        raise NotImplementedError(
            "FalkorDB driver not yet fully implemented — use PgVectorDriver"
        )

    async def search(
        self,
        query_embedding: list[float],
        org_id: str,
        limit: int = 10,
        category: str | None = None,
    ) -> list[SearchResult]:
        raise NotImplementedError(
            "FalkorDB driver not yet fully implemented — use PgVectorDriver"
        )

    async def delete(self, node_id: str, org_id: str) -> bool:
        raise NotImplementedError(
            "FalkorDB driver not yet fully implemented — use PgVectorDriver"
        )

    async def verify_integrity(self, node_id: str) -> bool:
        raise NotImplementedError(
            "FalkorDB driver not yet fully implemented — use PgVectorDriver"
        )

    async def find_similar(
        self,
        content_embedding: list[float],
        org_id: str,
        threshold: float = 0.35,
        limit: int = 3,
    ) -> list[SearchResult]:
        raise NotImplementedError(
            "FalkorDB driver not yet fully implemented — use PgVectorDriver"
        )

    async def health_check(self) -> bool:
        """Attempt a ping to FalkorDB and return True/False."""
        try:
            await self._driver.execute_query("RETURN 1")
            return True
        except Exception:
            return False


# ---------------------------------------------------------------------------
# Factory function
# ---------------------------------------------------------------------------


def get_driver(backend: str = "pgvector") -> KnowledgeStoreDriver:
    """Return a KnowledgeStoreDriver for the requested backend.

    Args:
        backend: Backend name — "pgvector" (default) or "falkordb".

    Returns:
        Configured KnowledgeStoreDriver instance.

    Raises:
        ValueError: If backend is not a recognised backend name.
    """
    if backend == "pgvector":
        return PgVectorDriver()

    if backend == "falkordb":
        from hivemind.config import settings  # noqa: PLC0415

        return FalkorDBDriver(
            host=settings.falkordb_host,
            port=settings.falkordb_port,
            database=settings.falkordb_database,
        )

    raise ValueError(
        f"Unknown backend '{backend}'. Valid options: 'pgvector', 'falkordb'."
    )
