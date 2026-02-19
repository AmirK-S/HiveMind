"""Create api_keys table for API key authentication with tiers (INFRA-04).

Revision ID: 003
Revises: 002
Create Date: 2026-02-19

Creates:
- api_keys : stores hashed API keys with tier metadata and usage counters

Columns:
- id                        : UUID primary key
- key_prefix                : String(8) — first 8 chars of the raw key (safe to display)
- key_hash                  : String(64), unique — SHA-256 of the full API key
- org_id                    : String(255) — namespace isolation
- agent_id                  : String(255) — which agent this key belongs to
- tier                      : String(20), default 'free' — "free" | "pro" | "enterprise"
- request_count             : Integer, default 0 — cumulative count within billing period
- billing_period_start      : DateTime — start of current billing window
- billing_period_reset_days : Integer, default 30 — window length
- is_active                 : Boolean, default true — soft-disable without deleting
- created_at                : DateTime — creation timestamp
- last_used_at              : DateTime, nullable — set on each successful auth

Indexes:
- ix_api_keys_key_hash : unique hash for O(1) key verification
- ix_api_keys_org_id   : org-scoped key listing

Design notes:
- Raw key is never stored — only SHA-256 hash (similar to GitHub API key design)
- key_prefix allows safe display of "hm_12345..." in UI without exposing full key
- Unique constraint on key_hash is the primary lookup path for authentication
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers used by Alembic
revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "api_keys",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("key_prefix", sa.String(8), nullable=False),
        sa.Column("key_hash", sa.String(64), nullable=False),
        sa.Column("org_id", sa.String(255), nullable=False),
        sa.Column("agent_id", sa.String(255), nullable=False),
        sa.Column("tier", sa.String(20), nullable=False, server_default="free"),
        sa.Column("request_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column(
            "billing_period_start",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "billing_period_reset_days",
            sa.Integer,
            nullable=False,
            server_default="30",
        ),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
    )

    # Unique constraint on key_hash — primary auth lookup path
    op.create_unique_constraint(
        "uq_api_keys_key_hash",
        "api_keys",
        ["key_hash"],
    )

    # Explicit index on key_hash for O(1) key verification lookups
    op.create_index(
        "ix_api_keys_key_hash",
        "api_keys",
        ["key_hash"],
    )

    # Index on org_id for per-org key listing
    op.create_index(
        "ix_api_keys_org_id",
        "api_keys",
        ["org_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_api_keys_org_id", table_name="api_keys")
    op.drop_index("ix_api_keys_key_hash", table_name="api_keys")
    op.drop_constraint("uq_api_keys_key_hash", "api_keys", type_="unique")
    op.drop_table("api_keys")
