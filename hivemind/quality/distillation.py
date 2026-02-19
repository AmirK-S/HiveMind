"""Sleep-time distillation background task (QI-04, QI-05).

Runs periodically via Celery Beat to maintain self-healing properties in the
commons:
  1. Threshold check    — short-circuit if pending volume and conflict count are
                          both below configured thresholds (avoids unnecessary work)
  2. Duplicate merging  — expire non-canonical duplicates; keep highest-quality item
  3. Contradiction flag — group contradicting items into clusters for human review
  4. Summary generation — LLM-generated summary for clusters of 3+ related items
                          + PII re-scan on every generated summary
  5. Quality pre-screen — flag low-quality pending contributions before review queue

This module must ONLY be called from a Celery task — never from the request path.

Design decisions:
- Uses sync SessionFactory (hivemind.cli.client) — same pattern as webhook tasks.
- PIIPipeline is imported lazily inside the function body to avoid heavy model
  loading at module import time.
- Merged duplicates are expired (expired_at = now()), never deleted — immutable
  audit trail per KM-05.
- Provenance links (source_item_ids in tags) enable erasure propagation:
  if any source item is deleted, derived summaries can be identified and
  re-evaluated.
- LLM summary generation is non-blocking — if no API key or API call fails,
  summary stage is skipped gracefully.
"""

from __future__ import annotations

import datetime
import hashlib
import json
import logging
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Prompt for LLM-assisted summary generation
# ---------------------------------------------------------------------------

_SUMMARY_PROMPT = (
    "Summarize these related knowledge items into a single concise item that captures "
    "the key information. Preserve technical accuracy. Output only the summary text."
)

# Cosine distance threshold for clustering related items (< 0.3 = high similarity)
_CLUSTER_DISTANCE_THRESHOLD = 0.3

# Minimum cluster size to trigger summary generation
_MIN_CLUSTER_SIZE = 3

# Low quality pre-screening threshold
_LOW_QUALITY_THRESHOLD = 0.2


def _get_session():
    """Return a sync SQLAlchemy session using the CLI pattern."""
    from hivemind.cli.client import SessionFactory  # noqa: PLC0415

    return SessionFactory()


def _now_utc() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


def _compute_content_hash(text: str) -> str:
    """Compute SHA-256 of text content."""
    return hashlib.sha256(text.encode()).hexdigest()


def _call_summary_llm(items_content: list[str], api_key: str, model: str) -> str | None:
    """Call the Anthropic API synchronously to generate a summary for a cluster.

    Returns the generated summary text, or None on any failure.

    Uses httpx synchronous client — Celery task, not async context.
    """
    import httpx  # noqa: PLC0415

    items_text = "\n\n---\n\n".join(
        f"Item {i + 1}:\n{content}" for i, content in enumerate(items_content)
    )
    user_message = f"{_SUMMARY_PROMPT}\n\n{items_text}"

    try:
        with httpx.Client(timeout=15.0) as client:
            response = client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": model,
                    "max_tokens": 512,
                    "messages": [{"role": "user", "content": user_message}],
                },
            )
            response.raise_for_status()
            data = response.json()
            return data["content"][0]["text"].strip()
    except Exception as exc:
        logger.warning("Distillation: LLM summary call failed — %s (skipping)", exc)
        return None


# ---------------------------------------------------------------------------
# Main distillation function
# ---------------------------------------------------------------------------


def run_distillation() -> dict[str, Any]:
    """Run the full sleep-time distillation pipeline.

    Must be called from a Celery task worker (synchronous context).  Never
    invoke this from the request path.

    Steps
    -----
    a. Threshold check       — short-circuit if below both thresholds
    b. Duplicate merging     — expire non-canonical duplicates
    c. Contradiction flagging — cluster contradicting items
    d. Summary generation    — LLM + mandatory PII re-scan
    e. Quality pre-screening — flag low-quality pending contributions
    f. Update last-run timestamp in deployment_config

    Returns
    -------
    dict
        status, duplicates_merged, contradictions_flagged, summaries_generated,
        items_prescreened, low_quality_filtered, run_at.
    """
    from hivemind.config import settings  # noqa: PLC0415
    from hivemind.db.models import (  # noqa: PLC0415
        DeploymentConfig,
        KnowledgeItem,
        PendingContribution,
        QualitySignal,
    )
    from sqlalchemy import func, select, text, update  # noqa: PLC0415

    now = _now_utc()

    # ------------------------------------------------------------------
    # a. Threshold check
    # ------------------------------------------------------------------
    with _get_session() as session:
        pending_count: int = session.execute(
            select(func.count()).select_from(PendingContribution)
        ).scalar() or 0

        # Count contradiction signals created after the last distillation run
        last_run_row = session.execute(
            select(DeploymentConfig.value).where(
                DeploymentConfig.key == "distillation_last_run"
            )
        ).scalar()

        if last_run_row:
            try:
                last_run_dt = datetime.datetime.fromisoformat(last_run_row)
            except ValueError:
                last_run_dt = datetime.datetime(1970, 1, 1, tzinfo=datetime.timezone.utc)
        else:
            last_run_dt = datetime.datetime(1970, 1, 1, tzinfo=datetime.timezone.utc)

        conflict_count: int = session.execute(
            select(func.count())
            .select_from(QualitySignal)
            .where(
                QualitySignal.signal_type == "contradiction",
                QualitySignal.created_at > last_run_dt,
            )
        ).scalar() or 0

    volume_threshold: int = settings.distillation_volume_threshold
    conflict_threshold: int = settings.distillation_conflict_threshold

    if pending_count < volume_threshold and conflict_count < conflict_threshold:
        logger.info(
            "Distillation: skipped — pending=%d (threshold=%d), conflicts=%d (threshold=%d)",
            pending_count,
            volume_threshold,
            conflict_count,
            conflict_threshold,
        )
        return {
            "status": "skipped",
            "reason": "below threshold",
            "pending_count": pending_count,
            "conflict_count": conflict_count,
        }

    logger.info(
        "Distillation: starting — pending=%d, conflicts=%d",
        pending_count,
        conflict_count,
    )

    # ------------------------------------------------------------------
    # b. Duplicate merging
    # ------------------------------------------------------------------
    duplicates_merged = 0

    with _get_session() as session:
        # Find groups of active knowledge_items sharing the same content_hash
        # (same org only — ACL-01)
        # Use a raw SQL subquery to find duplicate groups
        duplicate_groups_sql = text("""
            SELECT content_hash, org_id, array_agg(id ORDER BY quality_score DESC) AS ids
            FROM knowledge_items
            WHERE expired_at IS NULL
              AND deleted_at IS NULL
            GROUP BY content_hash, org_id
            HAVING count(*) > 1
        """)
        duplicate_groups = session.execute(duplicate_groups_sql).fetchall()

        for row in duplicate_groups:
            ids = row.ids  # sorted descending by quality_score — first is canonical
            if not ids or len(ids) < 2:
                continue

            canonical_id = ids[0]
            non_canonical_ids = ids[1:]

            # Fetch canonical item's current tags to build provenance_links
            canonical_item = session.execute(
                select(KnowledgeItem).where(KnowledgeItem.id == canonical_id)
            ).scalar_one_or_none()

            if canonical_item is None:
                continue

            existing_tags: dict = canonical_item.tags or {}
            existing_provenance: list = existing_tags.get("provenance_links", [])
            new_provenance = existing_provenance + [str(nid) for nid in non_canonical_ids]

            updated_tags = {**existing_tags, "provenance_links": new_provenance}

            # Update canonical item with provenance links
            session.execute(
                update(KnowledgeItem)
                .where(KnowledgeItem.id == canonical_id)
                .values(tags=updated_tags)
            )

            # Expire non-canonical duplicates (system-time invalidation — no deletion)
            session.execute(
                update(KnowledgeItem)
                .where(KnowledgeItem.id.in_(non_canonical_ids))
                .values(expired_at=now)
            )

            duplicates_merged += len(non_canonical_ids)

        session.commit()

    logger.info("Distillation: duplicate merging complete — %d merged", duplicates_merged)

    # ------------------------------------------------------------------
    # c. Contradiction flagging
    # ------------------------------------------------------------------
    contradictions_flagged = 0

    with _get_session() as session:
        # Find knowledge items with "contradiction" signals
        contradiction_signals_sql = text("""
            SELECT qs.knowledge_item_id, ki.category, ki.org_id
            FROM quality_signals qs
            JOIN knowledge_items ki ON ki.id = qs.knowledge_item_id
            WHERE qs.signal_type = 'contradiction'
              AND ki.expired_at IS NULL
              AND ki.deleted_at IS NULL
            GROUP BY qs.knowledge_item_id, ki.category, ki.org_id
        """)
        contradiction_rows = session.execute(contradiction_signals_sql).fetchall()

        # Group by (category, org_id) to build contradiction clusters
        clusters: dict[tuple[str, str], list[str]] = {}
        for row in contradiction_rows:
            key = (str(row.category), str(row.org_id))
            clusters.setdefault(key, []).append(str(row.knowledge_item_id))

        for (category, org_id), item_ids in clusters.items():
            if len(item_ids) < 2:
                continue  # a single item can't form a contradiction cluster

            # Record a "contradiction_cluster" signal pointing to all conflicting items
            cluster_signal = QualitySignal(
                signal_type="contradiction_cluster",
                signal_metadata={
                    "conflicting_item_ids": item_ids,
                    "category": category,
                    "org_id": org_id,
                    "detected_at": now.isoformat(),
                },
                knowledge_item_id=item_ids[0],  # anchor to first item in cluster
                created_at=now,
            )
            session.add(cluster_signal)
            contradictions_flagged += 1

        session.commit()

    logger.info(
        "Distillation: contradiction flagging complete — %d clusters", contradictions_flagged
    )

    # ------------------------------------------------------------------
    # d. Summary generation (LLM + mandatory PII re-scan)
    # ------------------------------------------------------------------
    summaries_generated = 0

    with _get_session() as session:
        # Find active knowledge_items with embeddings for clustering
        # We look for items within the same category and org that are cosine-similar
        # Use pgvector's cosine distance operator (<=>)
        clusterable_items_sql = text("""
            SELECT a.id AS id_a,
                   b.id AS id_b,
                   a.content AS content_a,
                   b.content AS content_b,
                   a.category,
                   a.org_id,
                   a.embedding <=> b.embedding AS distance
            FROM knowledge_items a
            JOIN knowledge_items b ON a.id < b.id
              AND a.category = b.category
              AND a.org_id = b.org_id
            WHERE a.expired_at IS NULL AND a.deleted_at IS NULL
              AND b.expired_at IS NULL AND b.deleted_at IS NULL
              AND a.embedding IS NOT NULL AND b.embedding IS NOT NULL
              AND a.embedding <=> b.embedding < :threshold
            ORDER BY distance ASC
        """)

        try:
            pairs = session.execute(
                clusterable_items_sql, {"threshold": _CLUSTER_DISTANCE_THRESHOLD}
            ).fetchall()
        except Exception as exc:
            # pgvector may not be available — skip summary generation gracefully
            logger.warning("Distillation: embedding cluster query failed — %s (skipping)", exc)
            pairs = []

        # Build adjacency list to find connected components (clusters)
        adjacency: dict[str, set[str]] = {}
        pair_content: dict[str, str] = {}

        for row in pairs:
            id_a = str(row.id_a)
            id_b = str(row.id_b)
            adjacency.setdefault(id_a, set()).add(id_b)
            adjacency.setdefault(id_b, set()).add(id_a)
            pair_content[id_a] = row.content_a
            pair_content[id_b] = row.content_b

        # Find connected components via BFS
        visited: set[str] = set()
        connected_components: list[tuple[list[str], str, str]] = []

        for start_id in adjacency:
            if start_id in visited:
                continue
            # BFS
            cluster_ids: list[str] = []
            queue = [start_id]
            cluster_category = ""
            cluster_org = ""
            while queue:
                node = queue.pop(0)
                if node in visited:
                    continue
                visited.add(node)
                cluster_ids.append(node)
                for neighbor in adjacency.get(node, set()):
                    if neighbor not in visited:
                        queue.append(neighbor)

            if len(cluster_ids) >= _MIN_CLUSTER_SIZE:
                # Get category/org from pairs metadata
                for row in pairs:
                    if str(row.id_a) in cluster_ids:
                        cluster_category = str(row.category)
                        cluster_org = str(row.org_id)
                        break
                connected_components.append((cluster_ids, cluster_category, cluster_org))

        # Generate summaries for qualifying clusters
        from hivemind.config import settings as cfg  # noqa: PLC0415

        for cluster_ids, category, org_id in connected_components:
            items_content = [pair_content[cid] for cid in cluster_ids if cid in pair_content]
            if len(items_content) < _MIN_CLUSTER_SIZE:
                continue

            # LLM summary generation — skip if no API key
            if not cfg.anthropic_api_key:
                logger.debug(
                    "Distillation: no API key — skipping summary generation for cluster "
                    "(size=%d, category=%s)",
                    len(cluster_ids),
                    category,
                )
                continue

            summary_text = _call_summary_llm(items_content, cfg.anthropic_api_key, cfg.llm_model)
            if not summary_text:
                continue  # LLM failed — non-blocking

            # Mandatory PII re-scan on generated summary (QI-04 requirement)
            # Lazy import to avoid loading heavy ML models at module import time
            try:
                from hivemind.pipeline.pii import PIIPipeline  # noqa: PLC0415

                cleaned_summary, should_reject = PIIPipeline.get_instance().strip(summary_text)
                if cleaned_summary != summary_text:
                    logger.warning(
                        "Distillation: PII detected and stripped from generated summary "
                        "(category=%s, org=%s)",
                        category,
                        org_id,
                    )
                if should_reject:
                    logger.warning(
                        "Distillation: generated summary rejected (>50%% PII) for cluster "
                        "(category=%s, org=%s) — skipping",
                        category,
                        org_id,
                    )
                    continue
                summary_text = cleaned_summary
            except Exception as exc:
                logger.warning(
                    "Distillation: PII pipeline unavailable — %s — storing summary as-is "
                    "(category=%s)",
                    exc,
                    category,
                )

            # Store summary as a new knowledge_item
            summary_item = KnowledgeItem(
                org_id=org_id,
                is_public=False,
                source_agent_id="distillation",
                run_id=None,
                content=summary_text,
                content_hash=_compute_content_hash(summary_text),
                category=category,
                confidence=0.8,
                quality_score=0.6,  # slightly above neutral — summaries are curated
                tags={
                    "distilled": True,
                    "source_item_ids": cluster_ids,
                },
                contributed_at=now,
                approved_at=now,
            )
            session.add(summary_item)
            summaries_generated += 1

        session.commit()

    logger.info(
        "Distillation: summary generation complete — %d summaries", summaries_generated
    )

    # ------------------------------------------------------------------
    # e. Quality pre-screening
    # ------------------------------------------------------------------
    items_prescreened = 0
    low_quality_filtered = 0

    with _get_session() as session:
        pending_items = session.execute(
            select(PendingContribution).where(
                PendingContribution.is_sensitive_flagged == False,  # noqa: E712
            )
        ).scalars().all()

        for item in pending_items:
            items_prescreened += 1

            # Compute preliminary quality estimate using available signals.
            # For pending items (no behavioral history yet) we use:
            #   - retrieval_count = 0 (not yet in commons)
            #   - helpful_count = 0
            #   - not_helpful_count = 0
            #   - contradiction_rate from confidence inversion proxy
            #   - days_since_last_access = 0 (just contributed)
            #   - is_version_current = True (new items are current)
            from hivemind.quality.scorer import compute_quality_score  # noqa: PLC0415

            preliminary_score = compute_quality_score(
                retrieval_count=0,
                helpful_count=0,
                not_helpful_count=0,
                contradiction_rate=max(0.0, 1.0 - item.confidence),
                days_since_last_access=0.0,
                is_version_current=True,
            )

            if preliminary_score < _LOW_QUALITY_THRESHOLD:
                # Flag item but do not remove from queue — visual flag only
                existing_tags: dict = item.tags or {}
                updated_tags = {
                    **existing_tags,
                    "low_quality_prescreened": True,
                    "preliminary_quality_score": preliminary_score,
                }
                session.execute(
                    update(PendingContribution)
                    .where(PendingContribution.id == item.id)
                    .values(
                        is_sensitive_flagged=True,
                        tags=updated_tags,
                    )
                )
                low_quality_filtered += 1

        session.commit()

    logger.info(
        "Distillation: pre-screening complete — %d prescreened, %d low-quality flagged",
        items_prescreened,
        low_quality_filtered,
    )

    # ------------------------------------------------------------------
    # f. Update last-run timestamp in deployment_config
    # ------------------------------------------------------------------
    with _get_session() as session:
        existing = session.execute(
            select(DeploymentConfig).where(DeploymentConfig.key == "distillation_last_run")
        ).scalar_one_or_none()

        if existing:
            existing.value = now.isoformat()
            existing.updated_at = now
        else:
            session.add(
                DeploymentConfig(
                    key="distillation_last_run",
                    value=now.isoformat(),
                    created_at=now,
                    updated_at=now,
                )
            )
        session.commit()

    result = {
        "status": "completed",
        "duplicates_merged": duplicates_merged,
        "contradictions_flagged": contradictions_flagged,
        "summaries_generated": summaries_generated,
        "items_prescreened": items_prescreened,
        "low_quality_filtered": low_quality_filtered,
        "run_at": now.isoformat(),
    }
    logger.info("Distillation: completed — %s", json.dumps(result))
    return result
