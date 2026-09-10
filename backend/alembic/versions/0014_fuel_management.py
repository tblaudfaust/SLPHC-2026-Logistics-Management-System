"""Fuel Management module: full allocation -> request -> approval -> issuance
-> receipt -> reconciliation accountability chain for vehicle, generator and
Starlink field-kit fuel use. Vehicles and Generators extend the existing
Asset register the same way StarlinkKit does; Suppliers double as fuel
vendors; depots reuse Location. Genuinely new: census_activities,
fuel_sequence_counters, fuel_stations, fuel_allocations, fuel_requests,
fuel_approvals, fuel_issues, fuel_receipts, fuel_vouchers,
fuel_stock_transactions, fuel_reconciliations, plus the vehicles/generators
extension tables.

Revision ID: 0014
Revises: 0013
Create Date: 2026-09-10

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0014"
down_revision: Union[str, None] = "0013"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "census_activities",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(120), nullable=False, unique=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "fuel_sequence_counters",
        sa.Column("entity_type", sa.String(30), primary_key=True),
        sa.Column("next_sequence", sa.Integer, nullable=False, server_default="0"),
    )

    op.create_table(
        "vehicles",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("asset_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("assets.id"), nullable=False, unique=True),
        sa.Column("registration_number", sa.String(30), nullable=False, unique=True),
        sa.Column("vehicle_type", sa.String(20), nullable=False, server_default="CAR"),
        sa.Column("make", sa.String(80), nullable=True),
        sa.Column("model", sa.String(80), nullable=True),
        sa.Column("fuel_type", sa.String(10), nullable=False, server_default="DIESEL"),
        sa.Column("tank_capacity", sa.Numeric(8, 2), nullable=True),
        sa.Column("assigned_driver_name", sa.String(150), nullable=True),
        sa.Column("current_odometer", sa.Integer, nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "generators",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("asset_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("assets.id"), nullable=False, unique=True),
        sa.Column("capacity_kva", sa.Numeric(8, 2), nullable=True),
        sa.Column("fuel_type", sa.String(10), nullable=False, server_default="DIESEL"),
        sa.Column("current_hour_meter", sa.Numeric(10, 2), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "fuel_stations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("supplier_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("suppliers.id"), nullable=False),
        sa.Column("name", sa.String(150), nullable=False),
        sa.Column("location_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("locations.id"), nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "fuel_allocations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("allocation_reference", sa.String(40), nullable=False, unique=True),
        sa.Column("region_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("regions.id"), nullable=True),
        sa.Column("district_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("districts.id"), nullable=True),
        sa.Column("activity_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("census_activities.id"), nullable=True),
        sa.Column("fuel_type", sa.String(10), nullable=False),
        sa.Column("allocated_litres", sa.Numeric(12, 2), nullable=False),
        sa.Column("allocated_budget", sa.Numeric(14, 2), nullable=True),
        sa.Column("start_date", sa.Date, nullable=False),
        sa.Column("end_date", sa.Date, nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="ACTIVE"),
        sa.Column("created_by_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("low_balance_notified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_fuel_allocations_status", "fuel_allocations", ["status"])

    op.create_table(
        "fuel_requests",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("request_reference", sa.String(40), nullable=False, unique=True),
        sa.Column("requester_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("region_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("regions.id"), nullable=True),
        sa.Column("district_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("districts.id"), nullable=True),
        sa.Column("activity_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("census_activities.id"), nullable=True),
        sa.Column("allocation_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("fuel_allocations.id"), nullable=True),
        sa.Column("asset_type", sa.String(20), nullable=False),
        sa.Column("vehicle_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("vehicles.id"), nullable=True),
        sa.Column("generator_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("generators.id"), nullable=True),
        sa.Column("starlink_kit_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("starlink_kits.id"), nullable=True),
        sa.Column("fuel_type", sa.String(10), nullable=False),
        sa.Column("quantity_requested", sa.Numeric(10, 2), nullable=False),
        sa.Column("purpose", sa.String(500), nullable=True),
        sa.Column("destination", sa.String(255), nullable=True),
        sa.Column("date_required", sa.Date, nullable=True),
        sa.Column("current_odometer", sa.Integer, nullable=True),
        sa.Column("expected_distance", sa.Integer, nullable=True),
        sa.Column("operating_hours", sa.Numeric(8, 2), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="DRAFT"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_fuel_requests_status", "fuel_requests", ["status"])
    op.create_index("ix_fuel_requests_requester_id", "fuel_requests", ["requester_id"])

    op.create_table(
        "fuel_approvals",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("fuel_request_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("fuel_requests.id"), nullable=False),
        sa.Column("approver_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("approval_level", sa.Integer, nullable=False),
        sa.Column("requested_quantity", sa.Numeric(10, 2), nullable=False),
        sa.Column("approved_quantity", sa.Numeric(10, 2), nullable=True),
        sa.Column("decision", sa.String(10), nullable=False),
        sa.Column("comments", sa.String(500), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_fuel_approvals_fuel_request_id", "fuel_approvals", ["fuel_request_id"])

    op.create_table(
        "fuel_issues",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("issue_reference", sa.String(40), nullable=False, unique=True),
        sa.Column(
            "fuel_request_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("fuel_requests.id"),
            nullable=False, unique=True,
        ),
        sa.Column("supplier_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("suppliers.id"), nullable=True),
        sa.Column("fuel_station_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("fuel_stations.id"), nullable=True),
        sa.Column("quantity_approved", sa.Numeric(10, 2), nullable=False),
        sa.Column("quantity_issued", sa.Numeric(10, 2), nullable=False),
        sa.Column("price_per_litre", sa.Numeric(8, 2), nullable=True),
        sa.Column("total_cost", sa.Numeric(12, 2), nullable=True),
        sa.Column("voucher_number", sa.String(40), nullable=True),
        sa.Column("issued_by_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("received_by_name", sa.String(150), nullable=True),
        sa.Column("witness_name", sa.String(150), nullable=True),
        sa.Column("issue_date", sa.Date, nullable=False),
        sa.Column("odometer_reading", sa.Integer, nullable=True),
        sa.Column("comments", sa.String(500), nullable=True),
        sa.Column("reconciliation_overdue_notified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "fuel_receipts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "fuel_issue_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("fuel_issues.id"),
            nullable=False, unique=True,
        ),
        sa.Column("receiver_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("quantity_received", sa.Numeric(10, 2), nullable=False),
        sa.Column("date_received", sa.Date, nullable=False),
        sa.Column("receipt_number", sa.String(40), nullable=True),
        sa.Column("acknowledgement", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("attachment", sa.String(500), nullable=True),
        sa.Column("remarks", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "fuel_vouchers",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("voucher_number", sa.String(40), nullable=False, unique=True),
        sa.Column("value", sa.Numeric(12, 2), nullable=True),
        sa.Column("litres", sa.Numeric(10, 2), nullable=True),
        sa.Column("assigned_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("assigned_asset_description", sa.String(255), nullable=True),
        sa.Column("date_issued", sa.Date, nullable=True),
        sa.Column("date_redeemed", sa.Date, nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="AVAILABLE"),
        sa.Column("remarks", sa.String(500), nullable=True),
        sa.Column("created_by_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_fuel_vouchers_status", "fuel_vouchers", ["status"])

    op.create_table(
        "fuel_stock_transactions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("depot_location_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("locations.id"), nullable=False),
        sa.Column("fuel_type", sa.String(10), nullable=False),
        sa.Column("transaction_type", sa.String(20), nullable=False),
        sa.Column("quantity", sa.Numeric(12, 2), nullable=False),
        sa.Column("reference_type", sa.String(40), nullable=True),
        sa.Column("reference_id", sa.String(80), nullable=True),
        sa.Column("remarks", sa.String(500), nullable=True),
        sa.Column("performed_by_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index(
        "ix_fuel_stock_transactions_depot_fuel_type", "fuel_stock_transactions", ["depot_location_id", "fuel_type"]
    )

    op.create_table(
        "fuel_reconciliations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "fuel_issue_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("fuel_issues.id"),
            nullable=False, unique=True,
        ),
        sa.Column("reconciled_by_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("quantity_issued", sa.Numeric(10, 2), nullable=False),
        sa.Column("quantity_used", sa.Numeric(10, 2), nullable=True),
        sa.Column("balance", sa.Numeric(10, 2), nullable=True),
        sa.Column("distance_travelled", sa.Integer, nullable=True),
        sa.Column("hours_operated", sa.Numeric(8, 2), nullable=True),
        sa.Column("comments", sa.String(500), nullable=True),
        sa.Column("reconciliation_date", sa.Date, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("fuel_reconciliations")
    op.drop_table("fuel_stock_transactions")
    op.drop_table("fuel_vouchers")
    op.drop_table("fuel_receipts")
    op.drop_table("fuel_issues")
    op.drop_table("fuel_approvals")
    op.drop_table("fuel_requests")
    op.drop_table("fuel_allocations")
    op.drop_table("fuel_stations")
    op.drop_table("generators")
    op.drop_table("vehicles")
    op.drop_table("fuel_sequence_counters")
    op.drop_table("census_activities")
