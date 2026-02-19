"""Add quality scoring and bi-temporal columns to knowledge_items; create quality_signals table.

Revision ID: 006
Revises: 005
Create Date: 2026-02-19

This migration creates the data foundation for all Quality Intelligence features (Phase 3).
Every subsequent plan in Phase 3 depends on the columns and table created here.

Adds to knowledge_items:
- quality_score        : Float, NOT NULL, server_default=0.5 (QI-01: neutral prior for new items)
- retrieval_count      : Integer, NOT NULL, server_default=0 (QI-02: denormalized for dashboard)
- helpful_count        : Integer, NOT NULL, server_default=0 (QI-02: denormalized for dashboard)
- not_helpful_count    : Integer, NOT NULL, server_default=0 (QI-02: denormalized for dashboard)
- valid_at             : DateTime(tz), nullable (KM-05: world-time start — NULL = "valid since approval")
- invalid_at           : DateTime(tz), nullable (KM-05: world-time end — NULL = "still valid")
- expired_at           : DateTime(tz), nullable (KM-05: system-time end — NULL = "current version")

Note: system-time start is already `contributed_at` (existing column). No duplicate created_at added.

New table quality_signals:
- id                   : UUID primary key
- knowledge_item_id    : UUID FK to knowledge_items.id
- signal_type          : String(50) — "retrieval", "outcome_solved", "outcome_not_helpful", "contradiction"
- agent_id             : String(255), nullable
- run_id               : String(255), nullable — for deduplication of outcome reports
- metadata             : JSONB, nullable — extensible signal-specific data
- created_at           : DateTime(tz), NOT NULL

Backfill:
- Sets quality_score = LEAST(1.0, confidence * 0.5) for existing items
  (items with high agent confidence get a slight head start — research Open Question 5)

Design notes:
- TSTZRANGE columns avoided — SQLAlchemy has known friction with DateTimeTZRange DataError
- Four explicit nullable DateTime(timezone=True) columns used instead
- valid_at is nullable — existing items have no world-time data; NULL is semantically correct
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers used by Alembic
revision: str = "006"
down_revision: Union[str, None] = "005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # -------------------------------------------------------------------------
    # 1. Add quality + temporal columns to knowledge_items
    # -------------------------------------------------------------------------
    op.add_column(
        "knowledge_items",
        sa.Column(
            "quality_score",
            sa.Float,
            nullable=False,
            server_default="0.5",
        ),
    )
    op.add_column(
        "knowledge_items",
        sa.Column(
            "retrieval_count",
            sa.Integer,
            nullable=False,
            server_default="0",
        ),
    )
    op.add_column(
        "knowledge_items",
        sa.Column(
            "helpful_count",
            sa.Integer,
            nullable=False,
            server_default="0",
        ),
    )
    op.add_column(
        "knowledge_items",
        sa.Column(
            "not_helpful_count",
            sa.Integer,
            nullable=False,
            server_default="0",
        ),
    )
    # Temporal columns (KM-05 bi-temporal pattern)
    # valid_at / invalid_at = world-time (business validity window)
    # expired_at = system-time end (NULL = current version)
    # contributed_at (existing) = system-time start
    op.add_column(
        "knowledge_items",
        sa.Column("valid_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "knowledge_items",
        sa.Column("invalid_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "knowledge_items",
        sa.Column("expired_at", sa.DateTime(timezone=True), nullable=True),
    )

    # -------------------------------------------------------------------------
    # 2. Create quality_signals table
    # -------------------------------------------------------------------------
    op.create_table(
        "quality_signals",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "knowledge_item_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("knowledge_items.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("signal_type", sa.String(50), nullable=False),
        sa.Column("agent_id", sa.String(255), nullable=True),
        sa.Column("run_id", sa.String(255), nullable=True),
        sa.Column("metadata", postgresql.JSONB, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    # Index on knowledge_item_id for aggregation queries
    op.create_index(
        "ix_quality_signals_knowledge_item_id",
        "quality_signals",
        ["knowledge_item_id"],
    )

    # Composite index on (knowledge_item_id, signal_type) for filtered aggregation
    op.create_index(
        "ix_quality_signals_item_type",
        "quality_signals",
        ["knowledge_item_id", "signal_type"],
    )

    # -------------------------------------------------------------------------
    # 3. Backfill quality_score for existing knowledge_items
    #    Items with high agent confidence get a slight head start (research Q5)
    # -------------------------------------------------------------------------
    op.execute(
        "UPDATE knowledge_items SET quality_score = LEAST(1.0, confidence * 0.5)"
    )

    # -------------------------------------------------------------------------
    # 4. Partial index on quality_score for quality-ranked queries
    #    WHERE deleted_at IS NULL — active items only
    # -------------------------------------------------------------------------
    op.create_index(
        "ix_knowledge_items_quality_score",
        "knowledge_items",
        ["quality_score"],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )


def downgrade() -> None:
    # Remove quality_score partial index
    op.drop_index("ix_knowledge_items_quality_score", table_name="knowledge_items")

    # Drop quality_signals table (indexes dropped automatically with table)
    op.drop_table("quality_signals")

    # Remove temporal columns from knowledge_items
    op.drop_column("knowledge_items", "expired_at")
    op.drop_column("knowledge_items", "invalid_at")
    op.drop_column("knowledge_items", "valid_at")

    # Remove quality + denormalized columns from knowledge_items
    op.drop_column("knowledge_items", "not_helpful_count")
    op.drop_column("knowledge_items", "helpful_count")
    op.drop_column("knowledge_items", "retrieval_count")
    op.drop_column("knowledge_items", "quality_score")
