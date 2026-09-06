"""ICT & Connectivity Assets > Starlink Management: field teams, funding
sources, hard-to-reach area classification, and the full Starlink kit
lifecycle (installation, subscription, field-team assignment, movement,
check-in, fault, return, documents) layered on top of the existing Asset
Register rather than duplicating it.

Revision ID: 0012
Revises: 0011
Create Date: 2026-09-06

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0012"
down_revision: Union[str, None] = "0011"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "field_teams",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("team_code", sa.String(30), nullable=False, unique=True),
        sa.Column("name", sa.String(150), nullable=False),
        sa.Column("team_type", sa.String(100), nullable=True),
        sa.Column("team_leader_name", sa.String(150), nullable=True),
        sa.Column("team_leader_phone", sa.String(30), nullable=True),
        sa.Column("members", sa.Text(), nullable=True),
        sa.Column("region_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("regions.id"), nullable=True),
        sa.Column("district_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("districts.id"), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("notes", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "funding_sources",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(150), nullable=False, unique=True),
        sa.Column("description", sa.String(255), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "hard_to_reach_areas",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(150), nullable=False),
        sa.Column("district_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("districts.id"), nullable=False),
        sa.Column("chiefdom", sa.String(150), nullable=True),
        sa.Column("classification", sa.String(30), nullable=False, server_default="HARD_TO_REACH"),
        sa.Column("starlink_required", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("notes", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "starlink_kits",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("asset_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("assets.id"), nullable=False, unique=True),
        sa.Column("kit_type", sa.String(10), nullable=False),
        sa.Column("terminal_id", sa.String(100), nullable=True),
        sa.Column("router_serial_number", sa.String(150), nullable=True),
        sa.Column("funding_source_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("funding_sources.id"), nullable=True),
        sa.Column("current_field_team_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("field_teams.id"), nullable=True),
        sa.Column(
            "current_hard_to_reach_area_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("hard_to_reach_areas.id"),
            nullable=True,
        ),
        sa.Column("operational_status", sa.String(30), nullable=False, server_default="NOT_DEPLOYED"),
        sa.Column("installation_status", sa.String(30), nullable=False, server_default="NOT_INSTALLED"),
        sa.Column("subscription_status", sa.String(30), nullable=False, server_default="PENDING_ACTIVATION"),
        sa.Column("last_connectivity_quality", sa.String(20), nullable=True),
        sa.Column("last_checkin_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_starlink_kits_kit_type", "starlink_kits", ["kit_type"])

    op.create_table(
        "starlink_components",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("kit_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("starlink_kits.id"), nullable=False),
        sa.Column("component_name", sa.String(100), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("condition", sa.String(20), nullable=False, server_default="NEW"),
        sa.Column("notes", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "starlink_installations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("kit_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("starlink_kits.id"), nullable=False),
        sa.Column("installation_type", sa.String(20), nullable=False),
        sa.Column("location_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("locations.id"), nullable=True),
        sa.Column("gps_latitude", sa.Numeric(9, 6), nullable=True),
        sa.Column("gps_longitude", sa.Numeric(9, 6), nullable=True),
        sa.Column("installation_date", sa.Date(), nullable=False),
        sa.Column("technician_name", sa.String(150), nullable=True),
        sa.Column("installation_company", sa.String(150), nullable=True),
        sa.Column("mounting_method", sa.String(100), nullable=True),
        sa.Column("power_source", sa.String(100), nullable=True),
        sa.Column("backup_power_available", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("installation_cost", sa.Numeric(12, 2), nullable=True),
        sa.Column("router_installed", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("connectivity_tested", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("download_speed_mbps", sa.Numeric(8, 2), nullable=True),
        sa.Column("upload_speed_mbps", sa.Numeric(8, 2), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("installed_by_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("verified_by_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("acceptance_status", sa.String(30), nullable=True),
        sa.Column("remarks", sa.String(1000), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "starlink_subscriptions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("kit_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("starlink_kits.id"), nullable=False),
        sa.Column("account_reference", sa.String(100), nullable=True),
        sa.Column("plan_name", sa.String(100), nullable=True),
        sa.Column("subscription_type", sa.String(50), nullable=True),
        sa.Column("activation_date", sa.Date(), nullable=True),
        sa.Column("subscription_start_date", sa.Date(), nullable=True),
        sa.Column("billing_cycle", sa.String(30), nullable=True),
        sa.Column("monthly_cost", sa.Numeric(12, 2), nullable=True),
        sa.Column("annual_estimated_cost", sa.Numeric(12, 2), nullable=True),
        sa.Column("currency", sa.String(10), nullable=True),
        sa.Column("last_payment_date", sa.Date(), nullable=True),
        sa.Column("next_payment_date", sa.Date(), nullable=True),
        sa.Column("renewal_date", sa.Date(), nullable=True),
        sa.Column("expiry_date", sa.Date(), nullable=True),
        sa.Column("status", sa.String(30), nullable=False, server_default="PENDING_ACTIVATION"),
        sa.Column("responsible_officer_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("is_current", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("expiry_alert_sent_at", sa.String(20), nullable=True),
        sa.Column("remarks", sa.String(1000), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_starlink_subscriptions_kit_current", "starlink_subscriptions", ["kit_id", "is_current"])
    op.create_index("ix_starlink_subscriptions_expiry_date", "starlink_subscriptions", ["expiry_date"])

    op.create_table(
        "starlink_subscription_payments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "subscription_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("starlink_subscriptions.id"), nullable=False
        ),
        sa.Column("payment_date", sa.Date(), nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("currency", sa.String(10), nullable=True),
        sa.Column("payment_reference", sa.String(100), nullable=True),
        sa.Column("payment_status", sa.String(30), nullable=False, server_default="PAID"),
        sa.Column("recorded_by_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("remarks", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "starlink_team_assignments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("kit_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("starlink_kits.id"), nullable=False),
        sa.Column("field_team_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("field_teams.id"), nullable=False),
        sa.Column("region_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("regions.id"), nullable=True),
        sa.Column("district_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("districts.id"), nullable=True),
        sa.Column("chiefdom", sa.String(150), nullable=True),
        sa.Column("section", sa.String(150), nullable=True),
        sa.Column("locality", sa.String(150), nullable=True),
        sa.Column("enumeration_area", sa.String(100), nullable=True),
        sa.Column("field_location", sa.String(255), nullable=True),
        sa.Column(
            "hard_to_reach_area_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("hard_to_reach_areas.id"), nullable=True
        ),
        sa.Column("assignment_purpose", sa.String(255), nullable=True),
        sa.Column("deployment_start_date", sa.Date(), nullable=False),
        sa.Column("expected_return_date", sa.Date(), nullable=False),
        sa.Column("actual_return_date", sa.Date(), nullable=True),
        sa.Column("released_by_name", sa.String(150), nullable=False),
        sa.Column("received_by_name", sa.String(150), nullable=True),
        sa.Column("witnessed_by_name", sa.String(150), nullable=True),
        sa.Column("equipment_condition_at_release", sa.String(20), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="ACTIVE"),
        sa.Column("remarks", sa.String(1000), nullable=True),
        sa.Column("created_by_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("overdue_notified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_starlink_team_assignments_status", "starlink_team_assignments", ["status"])
    # A kit may have at most one ACTIVE assignment — enforced at the DB level
    # (not just in the service layer) via a partial unique index.
    op.create_index(
        "uq_starlink_team_assignments_one_active_per_kit",
        "starlink_team_assignments",
        ["kit_id"],
        unique=True,
        postgresql_where=sa.text("status = 'ACTIVE'"),
    )

    op.create_table(
        "starlink_movements",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("kit_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("starlink_kits.id"), nullable=False),
        sa.Column("origin_location_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("locations.id"), nullable=True),
        sa.Column("destination_location_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("locations.id"), nullable=True),
        sa.Column("from_custodian_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("to_custodian_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("field_team_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("field_teams.id"), nullable=True),
        sa.Column("transfer_date", sa.Date(), nullable=False),
        sa.Column("purpose", sa.String(255), nullable=True),
        sa.Column("released_by_name", sa.String(150), nullable=True),
        sa.Column("received_by_name", sa.String(150), nullable=True),
        sa.Column("witnessed_by_name", sa.String(150), nullable=True),
        sa.Column("condition_at_release", sa.String(20), nullable=True),
        sa.Column("condition_at_receipt", sa.String(20), nullable=True),
        sa.Column("accessories_issued", sa.String(500), nullable=True),
        sa.Column("accessories_received", sa.String(500), nullable=True),
        sa.Column("remarks", sa.String(1000), nullable=True),
        sa.Column("performed_by_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "starlink_checkins",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("kit_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("starlink_kits.id"), nullable=False),
        sa.Column("field_team_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("field_teams.id"), nullable=True),
        sa.Column("checkin_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("region_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("regions.id"), nullable=True),
        sa.Column("district_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("districts.id"), nullable=True),
        sa.Column("chiefdom_section", sa.String(150), nullable=True),
        sa.Column("current_location", sa.String(255), nullable=True),
        sa.Column("gps_latitude", sa.Numeric(9, 6), nullable=True),
        sa.Column("gps_longitude", sa.Numeric(9, 6), nullable=True),
        sa.Column("starlink_available", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("starlink_operational", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("internet_available", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("power_available", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("equipment_condition", sa.String(20), nullable=True),
        sa.Column("connectivity_quality", sa.String(20), nullable=False, server_default="GOOD"),
        sa.Column("technical_problem", sa.String(500), nullable=True),
        sa.Column("technical_support_required", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("comment", sa.String(500), nullable=True),
        sa.Column("submitted_by_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_starlink_checkins_kit_checkin_at", "starlink_checkins", ["kit_id", "checkin_at"])

    op.create_table(
        "starlink_faults",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("ticket_number", sa.String(30), nullable=False, unique=True),
        sa.Column("kit_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("starlink_kits.id"), nullable=False),
        sa.Column("date_reported", sa.Date(), nullable=False),
        sa.Column("reported_by_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("current_location_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("locations.id"), nullable=True),
        sa.Column("fault_description", sa.String(1000), nullable=False),
        sa.Column("fault_category", sa.String(100), nullable=True),
        sa.Column("priority", sa.String(20), nullable=False, server_default="MEDIUM"),
        sa.Column("technician_assigned", sa.String(150), nullable=True),
        sa.Column("diagnosis", sa.String(1000), nullable=True),
        sa.Column("repair_action", sa.String(1000), nullable=True),
        sa.Column("replacement_parts", sa.String(500), nullable=True),
        sa.Column("repair_cost", sa.Numeric(12, 2), nullable=True),
        sa.Column("date_resolved", sa.Date(), nullable=True),
        sa.Column("resolved_by_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("verified_by_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("downtime_hours", sa.Numeric(8, 2), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="REPORTED"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_starlink_faults_status", "starlink_faults", ["status"])

    op.create_table(
        "starlink_returns",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "assignment_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("starlink_team_assignments.id"),
            nullable=False,
            unique=True,
        ),
        sa.Column("kit_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("starlink_kits.id"), nullable=False),
        sa.Column("returned_by_name", sa.String(150), nullable=True),
        sa.Column("received_by_name", sa.String(150), nullable=False),
        sa.Column("witnessed_by_name", sa.String(150), nullable=True),
        sa.Column("return_date", sa.Date(), nullable=False),
        sa.Column("dish_condition", sa.String(20), nullable=True),
        sa.Column("router_condition", sa.String(20), nullable=True),
        sa.Column("power_supply_condition", sa.String(20), nullable=True),
        sa.Column("missing_accessories", sa.String(500), nullable=True),
        sa.Column("damaged_accessories", sa.String(500), nullable=True),
        sa.Column("subscription_status_at_return", sa.String(30), nullable=True),
        sa.Column("final_condition", sa.String(20), nullable=True),
        sa.Column("reassignment_required", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("maintenance_required", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("remarks", sa.String(1000), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "starlink_documents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("kit_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("starlink_kits.id"), nullable=False),
        sa.Column("document_type", sa.String(50), nullable=False),
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("content_b64", sa.Text(), nullable=False),
        sa.Column("mime_type", sa.String(100), nullable=True),
        sa.Column("uploaded_by_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("notes", sa.String(255), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("starlink_documents")
    op.drop_table("starlink_returns")
    op.drop_table("starlink_faults")
    op.drop_table("starlink_checkins")
    op.drop_table("starlink_movements")
    op.drop_table("starlink_team_assignments")
    op.drop_table("starlink_subscription_payments")
    op.drop_table("starlink_subscriptions")
    op.drop_table("starlink_installations")
    op.drop_table("starlink_components")
    op.drop_table("starlink_kits")
    op.drop_table("hard_to_reach_areas")
    op.drop_table("funding_sources")
    op.drop_table("field_teams")
