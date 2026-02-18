"""Initial schema — pgvector extension, core tables, indexes.

Revision ID: 001
Revises:
Create Date: 2026-02-18

Creates:
- deployment_config       : key/value store for deployment metadata (e.g. pinned model revision)
- pending_contributions   : inbound knowledge queue awaiting user approval (PII-stripped)
- knowledge_items         : approved knowledge with embeddings and HNSW index
- knowledgecategory       : PostgreSQL enum matching KnowledgeCategory Python enum

Indexes created at table-creation time to avoid locking large tables later:
- ix_pending_contributions_org_id          : org namespace filtering
- ix_knowledge_items_org_id                : org namespace filtering
- ix_knowledge_items_embedding_hnsw        : HNSW approximate nearest neighbour (cosine)
- ix_knowledge_items_org_public            : composite for search query filter
- uq_knowledge_items_hash_org              : unique(content_hash, org_id) prevents intra-org dups

Design notes:
- pgvector VECTOR(384) for all-MiniLM-L6-v2 embeddings (384 dimensions)
- HNSW parameters: m=16, ef_construction=64 (pgvector recommended defaults for balanced recall/speed)
- Unique constraint is (content_hash, org_id) not just content_hash — two orgs can hold
  identical knowledge without conflicting (pitfall 4 from research)
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers used by Alembic
revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Install pgvector extension (idempotent)
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # 2. Create the KnowledgeCategory enum type
    knowledgecategory_enum = postgresql.ENUM(
        "bug_fix",
        "config",
        "domain_expertise",
        "workaround",
        "pricing_data",
        "regulatory_rule",
        "tooling",
        "reasoning_trace",
        "failed_approach",
        "version_workaround",
        "general",
        name="knowledgecategory",
    )
    knowledgecategory_enum.create(op.get_bind())

    # 3. deployment_config — key/value store for deployment metadata
    op.create_table(
        "deployment_config",
        sa.Column("key", sa.String(255), primary_key=True),
        sa.Column("value", sa.Text, nullable=False),
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

    # 4. pending_contributions — inbound queue (PII already stripped before insert)
    op.create_table(
        "pending_contributions",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("org_id", sa.String(255), nullable=False),
        sa.Column("source_agent_id", sa.String(255), nullable=False),
        sa.Column("run_id", sa.String(255), nullable=True),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column(
            "category",
            knowledgecategory_enum,
            nullable=False,
        ),
        sa.Column("confidence", sa.Float, nullable=False, server_default="0.8"),
        sa.Column("framework", sa.String(100), nullable=True),
        sa.Column("language", sa.String(50), nullable=True),
        sa.Column("version", sa.String(50), nullable=True),
        sa.Column("tags", postgresql.JSONB, nullable=True),
        sa.Column(
            "contributed_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "is_sensitive_flagged",
            sa.Boolean,
            nullable=False,
            server_default="false",
        ),
    )

    # Index on org_id for efficient namespace-scoped queries
    op.create_index(
        "ix_pending_contributions_org_id",
        "pending_contributions",
        ["org_id"],
    )

    # 5. knowledge_items — approved knowledge with embeddings
    op.create_table(
        "knowledge_items",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("org_id", sa.String(255), nullable=False),
        sa.Column("is_public", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("source_agent_id", sa.String(255), nullable=False),
        sa.Column("run_id", sa.String(255), nullable=True),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column(
            "category",
            knowledgecategory_enum,
            nullable=False,
        ),
        sa.Column("confidence", sa.Float, nullable=False, server_default="0.8"),
        sa.Column("framework", sa.String(100), nullable=True),
        sa.Column("language", sa.String(50), nullable=True),
        sa.Column("version", sa.String(50), nullable=True),
        sa.Column("tags", postgresql.JSONB, nullable=True),
        # VECTOR type for pgvector — 384 dims matches all-MiniLM-L6-v2 output
        sa.Column("embedding", sa.Text, nullable=True),  # placeholder; overridden below
        sa.Column("contributed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "approved_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    # Replace the placeholder embedding column with the actual VECTOR type
    # (Using raw SQL because SQLAlchemy Column creation doesn't support VECTOR(384) DDL directly
    #  without the pgvector extension already loaded — which we ensured above)
    op.execute("ALTER TABLE knowledge_items DROP COLUMN embedding")
    op.execute(
        "ALTER TABLE knowledge_items ADD COLUMN embedding vector(384)"
    )

    # Unique constraint: (content_hash, org_id) — intra-org dedup; cross-org allowed
    op.create_unique_constraint(
        "uq_knowledge_items_hash_org",
        "knowledge_items",
        ["content_hash", "org_id"],
    )

    # HNSW index for approximate cosine similarity search
    # m=16, ef_construction=64 are pgvector recommended defaults for balanced recall/speed
    op.execute(
        """
        CREATE INDEX ix_knowledge_items_embedding_hnsw
        ON knowledge_items
        USING hnsw (embedding vector_cosine_ops)
        WITH (m = 16, ef_construction = 64)
        """
    )

    # Composite index for the common search filter: WHERE org_id = ? AND is_public = ?
    op.create_index(
        "ix_knowledge_items_org_public",
        "knowledge_items",
        ["org_id", "is_public"],
    )

    # Index on org_id alone for efficient namespace-scoped queries
    op.create_index(
        "ix_knowledge_items_org_id",
        "knowledge_items",
        ["org_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_knowledge_items_org_id", table_name="knowledge_items")
    op.drop_index("ix_knowledge_items_org_public", table_name="knowledge_items")
    op.execute("DROP INDEX IF EXISTS ix_knowledge_items_embedding_hnsw")
    op.drop_constraint(
        "uq_knowledge_items_hash_org", "knowledge_items", type_="unique"
    )
    op.drop_table("knowledge_items")
    op.drop_index(
        "ix_pending_contributions_org_id", table_name="pending_contributions"
    )
    op.drop_table("pending_contributions")
    op.drop_table("deployment_config")

    # Drop the PostgreSQL enum type
    op.execute("DROP TYPE IF EXISTS knowledgecategory")

    # Drop pgvector extension (only if no other tables use it)
    op.execute("DROP EXTENSION IF EXISTS vector")
