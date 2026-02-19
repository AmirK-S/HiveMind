"""Signal recording and retrieval helpers for quality intelligence (QI-01, QI-02).

This module provides async helpers to:
- Record behavioral signals (retrievals, outcome reports, contradiction flags)
  into the quality_signals table.
- Retrieve signals for a given knowledge item.
- Atomically increment the denormalized retrieval_count on knowledge_items.

All functions use the `async with get_session()` pattern consistent with the
rest of the HiveMind codebase.
"""

import uuid
import datetime
from typing import Optional

import sqlalchemy as sa

from hivemind.db.models import KnowledgeItem, QualitySignal
from hivemind.db.session import get_session


async def record_signal(
    knowledge_item_id: str,
    signal_type: str,
    agent_id: Optional[str] = None,
    run_id: Optional[str] = None,
    metadata: Optional[dict] = None,
) -> str:
    """Insert a behavioral signal for a knowledge item.

    Parameters
    ----------
    knowledge_item_id : str
        UUID string of the target knowledge item.
    signal_type : str
        Event type — one of "retrieval", "outcome_solved",
        "outcome_not_helpful", "contradiction".
    agent_id : str | None
        ID of the agent generating this signal (for attribution).
    run_id : str | None
        Agent run ID — used for deduplication (same run should not
        produce duplicate outcome signals for the same item).
    metadata : dict | None
        Extensible signal-specific payload (e.g. search query, score).

    Returns
    -------
    str
        UUID string of the newly created QualitySignal row.
    """
    signal_id = uuid.uuid4()
    async with get_session() as session:
        signal = QualitySignal(
            id=signal_id,
            knowledge_item_id=uuid.UUID(knowledge_item_id),
            signal_type=signal_type,
            agent_id=agent_id,
            run_id=run_id,
            signal_metadata=metadata,
            created_at=datetime.datetime.utcnow(),
        )
        session.add(signal)
        await session.commit()
    return str(signal_id)


async def get_signals_for_item(knowledge_item_id: str) -> list[dict]:
    """Retrieve all signals for a knowledge item.

    Parameters
    ----------
    knowledge_item_id : str
        UUID string of the target knowledge item.

    Returns
    -------
    list[dict]
        List of signal dicts with keys: id, signal_type, agent_id, created_at.
        Ordered by created_at ascending (oldest first).
    """
    async with get_session() as session:
        result = await session.execute(
            sa.select(
                QualitySignal.id,
                QualitySignal.signal_type,
                QualitySignal.agent_id,
                QualitySignal.created_at,
            )
            .where(
                QualitySignal.knowledge_item_id == uuid.UUID(knowledge_item_id)
            )
            .order_by(QualitySignal.created_at.asc())
        )
        rows = result.all()

    return [
        {
            "id": str(row.id),
            "signal_type": row.signal_type,
            "agent_id": row.agent_id,
            "created_at": row.created_at.isoformat() if row.created_at else None,
        }
        for row in rows
    ]


async def increment_retrieval_count(knowledge_item_id: str) -> None:
    """Atomically increment the retrieval_count on a knowledge item.

    Uses a raw SQL UPDATE to avoid race conditions — no ORM read+write
    round-trip.  Safe for concurrent callers.

    Parameters
    ----------
    knowledge_item_id : str
        UUID string of the target knowledge item.
    """
    async with get_session() as session:
        await session.execute(
            sa.update(KnowledgeItem)
            .where(KnowledgeItem.id == uuid.UUID(knowledge_item_id))
            .values(retrieval_count=KnowledgeItem.retrieval_count + 1)
        )
        await session.commit()
