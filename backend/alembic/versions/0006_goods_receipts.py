"""Goods receipt header: named accountability (received by, delivered by,
supplier) for a receiving event, linked to its InventoryTransaction rows via
reference_type='goods_receipt'.

Revision ID: 0006
Revises: 0005
Create Date: 2026-09-04

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "goods_receipts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("warehouse_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("locations.id"), nullable=False),
        sa.Column("supplier_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("suppliers.id"), nullable=True),
        sa.Column("procurement_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("procurements.id"), nullable=True),
        sa.Column("received_by_name", sa.String(150), nullable=False),
        sa.Column("delivered_by_name", sa.String(150), nullable=True),
        sa.Column("receipt_date", sa.Date, nullable=False),
        sa.Column("remarks", sa.String(1000), nullable=True),
        sa.Column("created_by_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_goods_receipts_warehouse_id", "goods_receipts", ["warehouse_id"])
    op.create_index("ix_goods_receipts_receipt_date", "goods_receipts", ["receipt_date"])


def downgrade() -> None:
    op.drop_table("goods_receipts")
