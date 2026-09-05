"""Phase 2: asset catalogue (categories/models) and the serialized asset
register with its append-only status/journey event log.

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-04

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _timestamps():
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    ]


def upgrade() -> None:
    op.create_table(
        "asset_categories",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False, unique=True),
        sa.Column("code_prefix", sa.String(10), nullable=False, unique=True),
        sa.Column("tracking_type", sa.String(20), nullable=False, server_default="serialized"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("next_sequence", sa.Integer, nullable=False, server_default="0"),
        *_timestamps(),
    )

    op.create_table(
        "asset_models",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "category_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("asset_categories.id"), nullable=False
        ),
        sa.Column("brand", sa.String(100), nullable=False),
        sa.Column("model_name", sa.String(150), nullable=False),
        sa.Column("storage", sa.String(50), nullable=True),
        sa.Column("ram", sa.String(50), nullable=True),
        sa.Column("operating_system", sa.String(100), nullable=True),
        sa.Column("specifications", sa.String(1000), nullable=True),
        *_timestamps(),
    )
    op.create_index("ix_asset_models_category_id", "asset_models", ["category_id"])

    op.create_table(
        "assets",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("asset_tag", sa.String(40), nullable=False, unique=True),
        sa.Column(
            "category_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("asset_categories.id"), nullable=False
        ),
        sa.Column("model_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("asset_models.id"), nullable=True),
        sa.Column("serial_number", sa.String(150), nullable=True),
        sa.Column("imei_1", sa.String(20), nullable=True),
        sa.Column("imei_2", sa.String(20), nullable=True),
        sa.Column("mac_address", sa.String(30), nullable=True),
        sa.Column("sim_or_phone_number", sa.String(30), nullable=True),
        sa.Column("supplier_or_donor", sa.String(200), nullable=True),
        sa.Column("procurement_batch", sa.String(100), nullable=True),
        sa.Column("purchase_order_ref", sa.String(100), nullable=True),
        sa.Column("date_acquired", sa.Date, nullable=True),
        sa.Column("date_received", sa.Date, nullable=True),
        sa.Column("unit_cost", sa.Numeric(12, 2), nullable=True),
        sa.Column("currency", sa.String(10), nullable=True),
        sa.Column("warranty_start", sa.Date, nullable=True),
        sa.Column("warranty_end", sa.Date, nullable=True),
        sa.Column("status", sa.String(30), nullable=False, server_default="AVAILABLE"),
        sa.Column("condition", sa.String(20), nullable=False, server_default="NEW"),
        sa.Column("current_location_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("locations.id"), nullable=True),
        sa.Column("current_custodian_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_by_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("remarks", sa.String(1000), nullable=True),
        *_timestamps(),
    )
    op.create_index("ix_assets_asset_tag", "assets", ["asset_tag"])
    op.create_index("ix_assets_serial_number", "assets", ["serial_number"])
    op.create_index("ix_assets_category_id", "assets", ["category_id"])
    op.create_index("ix_assets_status", "assets", ["status"])
    op.create_index("ix_assets_current_location_id", "assets", ["current_location_id"])
    op.create_index("ix_assets_current_custodian_id", "assets", ["current_custodian_id"])

    op.create_table(
        "asset_status_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("asset_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("assets.id"), nullable=False),
        sa.Column("event_type", sa.String(40), nullable=False),
        sa.Column("previous_status", sa.String(30), nullable=True),
        sa.Column("new_status", sa.String(30), nullable=True),
        sa.Column(
            "previous_location_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("locations.id"), nullable=True
        ),
        sa.Column("new_location_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("locations.id"), nullable=True),
        sa.Column(
            "previous_custodian_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True
        ),
        sa.Column("new_custodian_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("condition", sa.String(20), nullable=True),
        sa.Column("reason", sa.String(500), nullable=True),
        sa.Column("performed_by_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_asset_status_events_asset_id", "asset_status_events", ["asset_id"])
    op.create_index("ix_asset_status_events_created_at", "asset_status_events", ["created_at"])


def downgrade() -> None:
    op.drop_table("asset_status_events")
    op.drop_table("assets")
    op.drop_table("asset_models")
    op.drop_table("asset_categories")
