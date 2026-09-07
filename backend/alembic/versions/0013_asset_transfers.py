"""Two-phase asset transfers for serialized categories: an AssetTransfer
header (mirrors StockTransfer's IN_TRANSIT/RECEIVED lifecycle) with
AssetTransferItem rows picking specific assets by id, since each serialized
unit has its own identity rather than a bulk quantity.

Revision ID: 0013
Revises: 0012
Create Date: 2026-09-08

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0013"
down_revision: Union[str, None] = "0012"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "asset_transfers",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("from_warehouse_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("locations.id"), nullable=False),
        sa.Column("to_warehouse_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("locations.id"), nullable=False),
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
    op.create_index("ix_asset_transfers_status", "asset_transfers", ["status"])
    op.create_index("ix_asset_transfers_expected_delivery_date", "asset_transfers", ["expected_delivery_date"])

    op.create_table(
        "asset_transfer_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "asset_transfer_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("asset_transfers.id"), nullable=False
        ),
        sa.Column("asset_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("assets.id"), nullable=False),
    )
    op.create_index("ix_asset_transfer_items_asset_transfer_id", "asset_transfer_items", ["asset_transfer_id"])
    op.create_index("ix_asset_transfer_items_asset_id", "asset_transfer_items", ["asset_id"])


def downgrade() -> None:
    op.drop_table("asset_transfer_items")
    op.drop_table("asset_transfers")
