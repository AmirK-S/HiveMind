"""Create auto_approve_rules table for per-category auto-approval (TRUST-04).

Revision ID: 004
Revises: 003
Create Date: 2026-02-19

Creates:
- auto_approve_rules : per-org, per-category auto-approval settings

Columns:
- id              : UUID primary key
- org_id          : String(255) — which org owns this rule
- category        : knowledgecategory enum — which knowledge category this rule applies to
- is_auto_approve : Boolean, default false — when true, skip human review for this category
- created_at      : DateTime — rule creation timestamp
- updated_at      : DateTime — rule last-modified timestamp

Constraints:
- uq_auto_approve_rules_org_category : unique(org_id, category) — one rule per org/category pair

Design notes:
- References the existing 'knowledgecategory' enum type created by migration 001
- create_type=False ensures we do NOT attempt to recreate the enum
- Unique constraint prevents contradictory entries for the same (org, category) pair
- Default is_auto_approve=False means human approval is required unless explicitly opted in
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers used by Alembic
revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Reference the existing knowledgecategory enum — do NOT create a new type
    knowledgecategory_enum = sa.Enum(
        name="knowledgecategory",
        create_type=False,
    )

    op.create_table(
        "auto_approve_rules",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("org_id", sa.String(255), nullable=False),
        sa.Column("category", knowledgecategory_enum, nullable=False),
        sa.Column(
            "is_auto_approve",
            sa.Boolean,
            nullable=False,
            server_default="false",
        ),
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
        sa.UniqueConstraint(
            "org_id",
            "category",
            name="uq_auto_approve_rules_org_category",
        ),
    )


def downgrade() -> None:
    op.drop_table("auto_approve_rules")
