"""Quality signal aggregation for HiveMind (QI-02, QI-03).

This module provides a function that aggregates behavioral signals for knowledge
items and recomputes their quality_score. It is designed to run as a Celery
periodic task (registered in hivemind/webhooks/tasks.py) on a 10-minute schedule.

Design:
- Incremental: only items with new signals since last aggregation are recomputed.
  This scales with signal volume, not total item count.
- Synchronous: Celery workers run in sync processes. Use the sync SessionFactory
  pattern from hivemind/cli/client.py — NOT asyncio or async SQLAlchemy.
- last_run timestamp is stored in the deployment_config table under the key
  "quality_aggregation_last_run" (ISO 8601 UTC string).
- Quality score formula is delegated to compute_quality_score() in scorer.py.

Feedback loop closed:
  agent outcome reports -> quality_signals table
  -> aggregate_quality_signals() (every 10 min)
  -> updated KnowledgeItem.quality_score
  -> higher quality items rank above lower-quality items in search (QI-03)
"""

from __future__ import annotations

import datetime
import logging
import uuid

logger = logging.getLogger(__name__)


def aggregate_quality_signals() -> dict:
    """Aggregate behavioral signals and recompute quality_score for affected items.

    Queries all knowledge items that received new quality_signals since the last
    aggregation run (stored in deployment_config). For each affected item, computes
    an updated quality_score using compute_quality_score() and writes it back.

    Uses the sync SQLAlchemy SessionFactory (cli pattern) because Celery workers
    are synchronous — asyncio is not available in worker process context.

    Returns:
        dict with:
            items_updated (int): number of knowledge items whose quality_score was updated
            run_at (str): ISO 8601 UTC timestamp of this aggregation run
    """
    from sqlalchemy import select, text, update  # noqa: PLC0415

    from hivemind.cli.client import SessionFactory  # noqa: PLC0415
    from hivemind.db.models import DeploymentConfig, KnowledgeItem, QualitySignal  # noqa: PLC0415
    from hivemind.quality.scorer import compute_quality_score  # noqa: PLC0415

    LAST_RUN_KEY = "quality_aggregation_last_run"
    run_at = datetime.datetime.now(datetime.timezone.utc)
    run_at_str = run_at.isoformat()

    with SessionFactory() as session:
        # -------------------------------------------------------------------
        # Step 1: Determine last aggregation time from deployment_config
        # -------------------------------------------------------------------
        last_run_row = session.execute(
            select(DeploymentConfig.value).where(DeploymentConfig.key == LAST_RUN_KEY)
        ).scalar_one_or_none()

        if last_run_row is not None:
            try:
                last_run = datetime.datetime.fromisoformat(last_run_row)
            except ValueError:
                # Corrupt value — treat as epoch (process all items)
                last_run = datetime.datetime(1970, 1, 1, tzinfo=datetime.timezone.utc)
                logger.warning(
                    "quality_aggregation_last_run has invalid value '%s' — resetting to epoch",
                    last_run_row,
                )
        else:
            # First run — process all items with any signals
            last_run = datetime.datetime(1970, 1, 1, tzinfo=datetime.timezone.utc)
            logger.info("quality_aggregation_last_run not set — first run, processing all items.")

        # -------------------------------------------------------------------
        # Step 2: Find items with new signals since last aggregation
        # -------------------------------------------------------------------
        affected_ids_result = session.execute(
            select(QualitySignal.knowledge_item_id.distinct()).where(
                QualitySignal.created_at > last_run
            )
        ).scalars().all()

        affected_ids = list(affected_ids_result)
        logger.info(
            "quality signal aggregation: %d items to recompute (since %s)",
            len(affected_ids),
            last_run.isoformat(),
        )

        if not affected_ids:
            # No new signals — update timestamp and return early
            _upsert_last_run(session, LAST_RUN_KEY, run_at_str, last_run_row)
            session.commit()
            return {"items_updated": 0, "run_at": run_at_str}

        # -------------------------------------------------------------------
        # Step 3: Recompute quality_score for each affected item
        # -------------------------------------------------------------------
        items_updated = 0

        for item_id in affected_ids:
            # Fetch the item's current denormalized signal counts
            item = session.execute(
                select(KnowledgeItem).where(KnowledgeItem.id == item_id)
            ).scalar_one_or_none()

            if item is None:
                logger.warning(
                    "aggregate_quality_signals: item %s in signals but not in knowledge_items — skipping",
                    item_id,
                )
                continue

            # Count total signals and contradiction signals for contradiction_rate
            total_signals_result = session.execute(
                text(
                    "SELECT COUNT(*) FROM quality_signals WHERE knowledge_item_id = :iid"
                ),
                {"iid": item_id},
            ).scalar_one()

            contradiction_signals_result = session.execute(
                text(
                    "SELECT COUNT(*) FROM quality_signals "
                    "WHERE knowledge_item_id = :iid AND signal_type = 'contradiction'"
                ),
                {"iid": item_id},
            ).scalar_one()

            total_signals = int(total_signals_result)
            contradiction_count = int(contradiction_signals_result)
            contradiction_rate = (
                contradiction_count / total_signals if total_signals > 0 else 0.0
            )

            # Compute days_since_last_access from most recent retrieval signal
            last_retrieval_result = session.execute(
                text(
                    "SELECT MAX(created_at) FROM quality_signals "
                    "WHERE knowledge_item_id = :iid AND signal_type = 'retrieval'"
                ),
                {"iid": item_id},
            ).scalar_one()

            if last_retrieval_result is not None:
                last_retrieval_dt = last_retrieval_result
                if last_retrieval_dt.tzinfo is None:
                    last_retrieval_dt = last_retrieval_dt.replace(tzinfo=datetime.timezone.utc)
                delta = run_at - last_retrieval_dt
                days_since_last_access = max(0.0, delta.total_seconds() / 86400.0)
            else:
                # No retrieval signal — compute days since approved_at
                if item.approved_at is not None:
                    approved = item.approved_at
                    if approved.tzinfo is None:
                        approved = approved.replace(tzinfo=datetime.timezone.utc)
                    delta = run_at - approved
                    days_since_last_access = max(0.0, delta.total_seconds() / 86400.0)
                else:
                    days_since_last_access = 0.0

            # Determine is_version_current: True if no newer VERSION_FORK sibling exists
            # A VERSION_FORK sibling has the same content_hash prefix or was derived
            # from this item and has a later contributed_at timestamp.
            # Simplified heuristic: if expired_at is NULL, this is the current version.
            is_version_current = item.expired_at is None

            # Compute the updated quality score
            new_score = compute_quality_score(
                retrieval_count=item.retrieval_count or 0,
                helpful_count=item.helpful_count or 0,
                not_helpful_count=item.not_helpful_count or 0,
                contradiction_rate=contradiction_rate,
                days_since_last_access=days_since_last_access,
                is_version_current=is_version_current,
            )

            # Update quality_score in the database
            session.execute(
                update(KnowledgeItem)
                .where(KnowledgeItem.id == item_id)
                .values(quality_score=new_score)
            )
            items_updated += 1

            logger.debug(
                "Updated quality_score for item %s: %.4f "
                "(retrieval=%d, helpful=%d, not_helpful=%d, contradiction_rate=%.3f, "
                "days_since_access=%.1f, is_version_current=%s)",
                item_id,
                new_score,
                item.retrieval_count or 0,
                item.helpful_count or 0,
                item.not_helpful_count or 0,
                contradiction_rate,
                days_since_last_access,
                is_version_current,
            )

        # -------------------------------------------------------------------
        # Step 4: Update last_run timestamp in deployment_config
        # -------------------------------------------------------------------
        _upsert_last_run(session, LAST_RUN_KEY, run_at_str, last_run_row)
        session.commit()

    logger.info(
        "quality signal aggregation complete: %d items updated at %s",
        items_updated,
        run_at_str,
    )
    return {"items_updated": items_updated, "run_at": run_at_str}


def _upsert_last_run(session, key: str, value: str, existing_row) -> None:
    """Insert or update the quality_aggregation_last_run key in deployment_config."""
    from sqlalchemy import text, update  # noqa: PLC0415

    from hivemind.db.models import DeploymentConfig  # noqa: PLC0415

    now = datetime.datetime.now(datetime.timezone.utc)

    if existing_row is not None:
        # Update existing row
        session.execute(
            update(DeploymentConfig)
            .where(DeploymentConfig.key == key)
            .values(value=value, updated_at=now)
        )
    else:
        # Insert new row
        session.add(
            DeploymentConfig(
                key=key,
                value=value,
                created_at=now,
                updated_at=now,
            )
        )
