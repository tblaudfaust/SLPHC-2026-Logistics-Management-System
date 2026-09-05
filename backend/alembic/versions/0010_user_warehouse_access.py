"""Per-user warehouse access scope: restricts a user to specific warehouse(s)
for inventory operations. No rows for a user means unrestricted (national)
access, unchanged from today's behavior.

Revision ID: 0010
Revises: 0009
Create Date: 2026-09-06

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0010"
down_revision: Union[str, None] = "0009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "user_warehouse_access",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("warehouse_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("locations.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("user_id", "warehouse_id", name="uq_user_warehouse_access"),
    )
    op.create_index("ix_user_warehouse_access_user_id", "user_warehouse_access", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_user_warehouse_access_user_id", table_name="user_warehouse_access")
    op.drop_table("user_warehouse_access")
