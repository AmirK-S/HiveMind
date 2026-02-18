"""Add deleted_at soft-delete column to knowledge_items.

Revision ID: 002
Revises: 001
Create Date: 2026-02-18

Adds:
- knowledge_items.deleted_at  : nullable DateTime for soft-delete (delete_knowledge tool)
  NULL = active item; non-NULL = soft-deleted, excluded from search results

Index:
- ix_knowledge_items_deleted_at_null  : partial index on active items (WHERE deleted_at IS NULL)
  speeds up the common case where all search queries exclude soft-deleted items

Design notes:
- Physical rows are retained for audit trail and possible future undelete support
- search_knowledge and list_knowledge queries filter WHERE deleted_at IS NULL
- delete_knowledge sets deleted_at = now() (soft-delete, not physical removal)
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers used by Alembic
revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add nullable deleted_at column to knowledge_items
    op.add_column(
        "knowledge_items",
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )

    # Partial index: only indexes rows where deleted_at IS NULL (active items).
    # Most queries filter for active items, so this index is hit on every search.
    op.execute(
        """
        CREATE INDEX ix_knowledge_items_deleted_at_null
        ON knowledge_items (org_id)
        WHERE deleted_at IS NULL
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_knowledge_items_deleted_at_null")
    op.drop_column("knowledge_items", "deleted_at")
