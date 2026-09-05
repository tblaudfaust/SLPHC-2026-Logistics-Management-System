"""Phase 3: suppliers, procurements, the quantity-tracked inventory ledger,
stock counts/reconciliation, and supplier/procurement links on assets.

Revision ID: 0003
Revises: 0002
Create Date: 2026-09-04

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _timestamps():
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    ]


def upgrade() -> None:
    op.create_table(
        "suppliers",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("supplier_type", sa.String(20), nullable=False, server_default="supplier"),
        sa.Column("contact_person", sa.String(150), nullable=True),
        sa.Column("phone", sa.String(30), nullable=True),
        sa.Column("email", sa.String(255), nullable=True),
        sa.Column("address", sa.String(255), nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.true()),
        *_timestamps(),
    )

    op.create_table(
        "procurements",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("supplier_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("suppliers.id"), nullable=True),
        sa.Column("reference", sa.String(100), nullable=False, unique=True),
        sa.Column("description", sa.String(500), nullable=True),
        sa.Column("status", sa.String(30), nullable=False, server_default="DRAFT"),
        sa.Column("order_date", sa.Date, nullable=True),
        sa.Column("expected_delivery_date", sa.Date, nullable=True),
        sa.Column("created_by_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        *_timestamps(),
    )
    op.create_index("ix_procurements_supplier_id", "procurements", ["supplier_id"])

    op.add_column("assets", sa.Column("supplier_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("assets", sa.Column("procurement_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key("fk_assets_supplier_id", "assets", "suppliers", ["supplier_id"], ["id"])
    op.create_foreign_key("fk_assets_procurement_id", "assets", "procurements", ["procurement_id"], ["id"])

    op.create_table(
        "inventory_transactions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("warehouse_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("locations.id"), nullable=False),
        sa.Column(
            "category_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("asset_categories.id"), nullable=False
        ),
        sa.Column("transaction_type", sa.String(20), nullable=False),
        sa.Column("quantity", sa.Integer, nullable=False),
        sa.Column(
            "related_warehouse_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("locations.id"), nullable=True
        ),
        sa.Column("batch_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("reference_type", sa.String(40), nullable=True),
        sa.Column("reference_id", sa.String(80), nullable=True),
        sa.Column("reason", sa.String(500), nullable=True),
        sa.Column("performed_by_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_inventory_transactions_warehouse_id", "inventory_transactions", ["warehouse_id"])
    op.create_index("ix_inventory_transactions_category_id", "inventory_transactions", ["category_id"])
    op.create_index("ix_inventory_transactions_batch_id", "inventory_transactions", ["batch_id"])
    op.create_index(
        "ix_inventory_transactions_warehouse_category", "inventory_transactions", ["warehouse_id", "category_id"]
    )

    op.create_table(
        "stock_counts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("warehouse_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("locations.id"), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="DRAFT"),
        sa.Column("count_date", sa.Date, nullable=False),
        sa.Column("counted_by_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("notes", sa.String(1000), nullable=True),
        *_timestamps(),
    )

    op.create_table(
        "stock_count_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("stock_count_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("stock_counts.id"), nullable=False),
        sa.Column(
            "category_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("asset_categories.id"), nullable=False
        ),
        sa.Column("expected_quantity", sa.Integer, nullable=False),
        sa.Column("physical_quantity", sa.Integer, nullable=False),
        sa.Column("variance_reason", sa.String(500), nullable=True),
    )
    op.create_index("ix_stock_count_items_stock_count_id", "stock_count_items", ["stock_count_id"])


def downgrade() -> None:
    op.drop_table("stock_count_items")
    op.drop_table("stock_counts")
    op.drop_table("inventory_transactions")
    op.drop_constraint("fk_assets_procurement_id", "assets", type_="foreignkey")
    op.drop_constraint("fk_assets_supplier_id", "assets", type_="foreignkey")
    op.drop_column("assets", "procurement_id")
    op.drop_column("assets", "supplier_id")
    op.drop_table("procurements")
    op.drop_table("suppliers")
