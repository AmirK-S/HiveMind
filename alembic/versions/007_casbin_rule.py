"""Create casbin_rule, the policy table the RBAC enforcer loads at startup.

Revision ID: 007
Revises: 006
Create Date: 2026-09-05

casbin-async-sqlalchemy-adapter reads and writes this table but does not
create it. The server initialises the enforcer during its lifespan, so a
database migrated to head must already contain it. Column layout follows the
adapter's own CasbinRule model: an integer key, the policy type and six
string slots v0 to v5.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "007"
down_revision: Union[str, None] = "006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "casbin_rule",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("ptype", sa.String(length=255), nullable=True),
        sa.Column("v0", sa.String(length=255), nullable=True),
        sa.Column("v1", sa.String(length=255), nullable=True),
        sa.Column("v2", sa.String(length=255), nullable=True),
        sa.Column("v3", sa.String(length=255), nullable=True),
        sa.Column("v4", sa.String(length=255), nullable=True),
        sa.Column("v5", sa.String(length=255), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("casbin_rule")
