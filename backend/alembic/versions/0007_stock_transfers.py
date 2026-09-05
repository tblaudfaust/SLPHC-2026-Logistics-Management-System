"""Two-phase stock transfers: a StockTransfer header (expected delivery date,
released-by/received-by names, IN_TRANSIT/RECEIVED status) replacing the old
atomic single-step transfer.

Revision ID: 0007
Revises: 0006
Create Date: 2026-09-05

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0007"
down_revision: Union[str, None] = "0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "stock_transfers",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "category_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("asset_categories.id"), nullable=False
        ),
        sa.Column("from_warehouse_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("locations.id"), nullable=False),
        sa.Column("to_warehouse_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("locations.id"), nullable=False),
        sa.Column("quantity", sa.Integer, nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="IN_TRANSIT"),
        sa.Column("expected_delivery_date", sa.Date, nullable=False),
        sa.Column("actual_delivery_date", sa.Date, nullable=True),
        sa.Column("released_by_name", sa.String(150), nullable=False),
        sa.Column("received_by_name", sa.String(150), nullable=True),
        sa.Column("reason", sa.String(500), nullable=True),
        sa.Column("dispatched_by_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("received_by_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("overdue_notified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_stock_transfers_status", "stock_transfers", ["status"])
    op.create_index("ix_stock_transfers_expected_delivery_date", "stock_transfers", ["expected_delivery_date"])


def downgrade() -> None:
    op.drop_table("stock_transfers")
