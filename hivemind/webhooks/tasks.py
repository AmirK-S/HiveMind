"""Celery webhook delivery tasks for HiveMind (INFRA-03).

Implements near-real-time push delivery to external consumers when knowledge
items are approved.  The delivery model is fire-and-forget with retry:
- deliver_webhook is a Celery task that POSTs to a single webhook endpoint
- dispatch_webhooks is a helper that fans out to all active endpoints for an org

**Design:**
- Celery broker and result backend are both Redis (same instance as rate limiter)
- Serialization is JSON — payloads are always JSON-serializable dicts
- deliver_webhook retries up to 3 times with 5-second delay on any failure
- dispatch_webhooks uses the sync SQLAlchemy session (same pattern as cli/client.py)
  because it is called from the CLI approval flow which is synchronous

**Event payload shape:**
    {
        "event": "knowledge.approved",          # event type string
        "knowledge_item_id": "<uuid>",           # UUID of the approved item
        "org_id": "<org>",                       # organisation namespace
        "category": "bug_fix",                  # knowledge category value
        "timestamp": "2026-02-19T03:30:00Z"     # ISO 8601 UTC timestamp
    }

References:
  - INFRA-03: Near-real-time push delivery to external consumers
  - WebhookEndpoint model: hivemind/db/models.py
  - Approval flow: hivemind/cli/client.py (approve_contribution)
"""

from celery import Celery

# ---------------------------------------------------------------------------
# Celery application
# ---------------------------------------------------------------------------

celery_app = Celery("hivemind")


def configure_celery(redis_url: str) -> None:
    """Configure Celery broker and result backend.

    Call this during server lifespan startup (e.g. in the FastAPI/FastMCP
    lifespan context) after the Redis URL is known from settings.

    Also registers the Celery Beat periodic schedule:
    - quality-signal-aggregation: every 10 minutes (QI-02, QI-03)
    - distillation-every-30m:     every 30 minutes (QI-04, QI-05)

    Note: Celery Beat only supports time-based triggering.  Condition checks
    (volume/conflict thresholds) live inside the task body — research Pitfall 6.

    Args:
        redis_url: Redis connection URL (e.g. "redis://localhost:6379/0").
    """
    from celery.schedules import crontab  # noqa: PLC0415

    celery_app.conf.broker_url = redis_url
    celery_app.conf.result_backend = redis_url
    celery_app.conf.task_serializer = "json"
    celery_app.conf.accept_content = ["json"]

    celery_app.conf.beat_schedule = {
        "quality-signal-aggregation": {
            "task": "hivemind.aggregate_quality_signals",
            "schedule": crontab(minute="*/10"),  # every 10 minutes
        },
        "distillation-every-30m": {
            "task": "hivemind.distill",
            "schedule": crontab(minute="*/30"),  # every 30 minutes
        },
    }


# ---------------------------------------------------------------------------
# Webhook delivery task
# ---------------------------------------------------------------------------


@celery_app.task(bind=True, max_retries=3, default_retry_delay=5)
def deliver_webhook(self, webhook_url: str, payload: dict) -> dict:
    """POST a knowledge event to a single webhook endpoint.

    Retries up to 3 times with 5-second delay on any failure (network error,
    non-2xx response, timeout, etc.).

    Uses httpx synchronous client — Celery tasks run in a synchronous worker
    process and cannot use asyncio.

    Args:
        webhook_url: The URL to POST to.
        payload:     JSON-serializable event payload containing:
                         - event: event type string (e.g. "knowledge.approved")
                         - knowledge_item_id: UUID string
                         - org_id: organisation namespace
                         - category: knowledge category
                         - timestamp: ISO 8601 timestamp

    Returns:
        Dict with status_code and url on success.

    Raises:
        self.retry: On any exception — propagates after max_retries exhausted.
    """
    import httpx  # noqa: PLC0415

    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.post(webhook_url, json=payload)
            response.raise_for_status()
            return {"status_code": response.status_code, "url": webhook_url}
    except Exception as exc:
        raise self.retry(exc=exc)


# ---------------------------------------------------------------------------
# Fan-out helper
# ---------------------------------------------------------------------------


def dispatch_webhooks(
    org_id: str,
    event: str,
    knowledge_item_id: str,
    category: str,
) -> int:
    """Dispatch webhook delivery tasks for all active endpoints in an org.

    Queries the webhook_endpoints table for active endpoints belonging to the org,
    filters by event_types subscription if configured, and enqueues a
    deliver_webhook Celery task for each matched endpoint.

    Uses sync SQLAlchemy session (same pattern as cli/client.py) because this
    is called from the CLI approval flow which is synchronous.

    Args:
        org_id:              Organisation namespace.
        event:               Event type string (e.g. "knowledge.approved").
        knowledge_item_id:   UUID string of the approved/published item.
        category:            Knowledge category value.

    Returns:
        Number of webhook delivery tasks dispatched (0 if no active endpoints).
    """
    import datetime  # noqa: PLC0415

    from hivemind.cli.client import SessionFactory  # noqa: PLC0415
    from hivemind.db.models import WebhookEndpoint  # noqa: PLC0415

    with SessionFactory() as session:
        endpoints = (
            session.query(WebhookEndpoint)
            .filter(
                WebhookEndpoint.org_id == org_id,
                WebhookEndpoint.is_active == True,  # noqa: E712
            )
            .all()
        )

    payload = {
        "event": event,
        "knowledge_item_id": knowledge_item_id,
        "org_id": org_id,
        "category": category,
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }

    dispatched = 0
    for endpoint in endpoints:
        # Filter by event_types subscription if the endpoint has configured types
        if endpoint.event_types:
            event_list = endpoint.event_types.get("types", [])
            if event_list and event not in event_list:
                continue  # this endpoint is not subscribed to this event type

        deliver_webhook.delay(endpoint.url, payload)
        dispatched += 1

    return dispatched


# ---------------------------------------------------------------------------
# Quality signal aggregation task
# ---------------------------------------------------------------------------


@celery_app.task(name="hivemind.aggregate_quality_signals")
def aggregate_quality_signals_task() -> dict:
    """Quality signal aggregation — called by Celery Beat every 10 minutes.

    Queries knowledge items that received new behavioral signals since the last
    aggregation, recomputes their quality_score via the weighted formula in
    scorer.py, and writes the updated score back to the database.

    Closes the feedback loop: agent outcomes -> signals -> aggregation -> ranking.

    Uses lazy import to avoid loading database models in the worker on startup
    before the Celery app is fully configured.

    Returns:
        Dict with items_updated (int) and run_at (ISO 8601 str).
    """
    from hivemind.quality.aggregator import aggregate_quality_signals  # noqa: PLC0415

    return aggregate_quality_signals()


# ---------------------------------------------------------------------------
# Sleep-time distillation task
# ---------------------------------------------------------------------------


@celery_app.task(name="hivemind.distill")
def run_distillation_task() -> dict:
    """Sleep-time distillation — called by Celery Beat every 30 minutes.

    Evaluates volume/conflict thresholds inside the task body and short-circuits
    if conditions are not met (Celery Beat only supports time-based triggering;
    condition logic must live in the task body — research Pitfall 6).

    Merges confirmed duplicates, flags contradiction clusters, generates
    LLM summaries with mandatory PII re-scan, and pre-screens pending
    contributions for quality before they reach the review queue.

    Uses lazy import for the distillation module to avoid loading heavy
    ML models (PII pipeline, embeddings) in the Celery worker on startup.

    Returns:
        Dict with status and counts for each distillation step.
    """
    from hivemind.quality.distillation import run_distillation  # noqa: PLC0415

    return run_distillation()
