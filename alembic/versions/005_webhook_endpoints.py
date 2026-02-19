"""Create webhook_endpoints table for near-real-time push delivery (INFRA-03).

Revision ID: 005
Revises: 004
Create Date: 2026-02-19

Creates:
- webhook_endpoints : registered HTTP endpoints for event-driven push delivery

Columns:
- id          : UUID primary key
- org_id      : String(255) — which org registered this endpoint
- url          : Text — the HTTPS URL to POST events to
- event_types  : JSONB, nullable — JSON array of subscribed event type strings
                 e.g. ["knowledge.approved", "knowledge.published"]
                 NULL = subscribe to all events
- is_active    : Boolean, default true — soft-disable without deleting the endpoint
- created_at   : DateTime — registration timestamp
- updated_at   : DateTime — last modified timestamp

Indexes:
- ix_webhook_endpoints_org_id : org-scoped endpoint listing

Design notes:
- JSONB array for event_types enables flexible subscription model without schema changes
  when new event types are introduced
- NULL event_types acts as a wildcard — receives all events (useful for debugging/audits)
- Soft-delete via is_active preserves configuration history and allows re-activation
- Delivery worker will POST to all active endpoints where org_id matches and
  (event_types IS NULL OR event_type = ANY(event_types))
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers used by Alembic
revision: str = "005"
down_revision: Union[str, None] = "004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "webhook_endpoints",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("org_id", sa.String(255), nullable=False),
        sa.Column("url", sa.Text, nullable=False),
        sa.Column("event_types", postgresql.JSONB, nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
        ),
    )

    # Index on org_id for per-org endpoint listing and delivery targeting
    op.create_index(
        "ix_webhook_endpoints_org_id",
        "webhook_endpoints",
        ["org_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_webhook_endpoints_org_id", table_name="webhook_endpoints")
    op.drop_table("webhook_endpoints")
