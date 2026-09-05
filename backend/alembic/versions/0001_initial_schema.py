"""Phase 1 foundation schema: geography hierarchy, locations, warehouses, RBAC,
users, refresh tokens, audit log.

Revision ID: 0001
Revises:
Create Date: 2026-09-03

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _timestamps():
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    ]


def upgrade() -> None:
    # --- Admin geography hierarchy (brief §17) ---
    op.create_table(
        "regions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(120), nullable=False, unique=True),
        sa.Column("code", sa.String(20), nullable=False, unique=True),
        *_timestamps(),
    )

    op.create_table(
        "districts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("region_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("regions.id"), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("code", sa.String(20), nullable=False, unique=True),
        *_timestamps(),
    )
    op.create_index("ix_districts_region_id", "districts", ["region_id"])

    op.create_table(
        "chiefdoms",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("district_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("districts.id"), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("code", sa.String(20), nullable=False, unique=True),
        *_timestamps(),
    )
    op.create_index("ix_chiefdoms_district_id", "chiefdoms", ["district_id"])

    op.create_table(
        "sections",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("chiefdom_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("chiefdoms.id"), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("code", sa.String(20), nullable=False, unique=True),
        *_timestamps(),
    )
    op.create_index("ix_sections_chiefdom_id", "sections", ["chiefdom_id"])

    op.create_table(
        "supervisory_areas",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("section_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("sections.id"), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("code", sa.String(20), nullable=False, unique=True),
        *_timestamps(),
    )
    op.create_index("ix_supervisory_areas_section_id", "supervisory_areas", ["section_id"])

    op.create_table(
        "enumeration_areas",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "supervisory_area_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("supervisory_areas.id"),
            nullable=False,
        ),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("code", sa.String(20), nullable=False, unique=True),
        *_timestamps(),
    )
    op.create_index("ix_enumeration_areas_supervisory_area_id", "enumeration_areas", ["supervisory_area_id"])

    # --- Logistics facilities ---
    op.create_table(
        "location_types",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(80), nullable=False, unique=True),
        sa.Column("description", sa.String(255), nullable=True),
        *_timestamps(),
    )

    op.create_table(
        "locations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "location_type_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("location_types.id"), nullable=False
        ),
        sa.Column("district_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("districts.id"), nullable=True),
        sa.Column("name", sa.String(150), nullable=False),
        sa.Column("address", sa.String(255), nullable=True),
        sa.Column("gps_latitude", sa.Numeric(9, 6), nullable=True),
        sa.Column("gps_longitude", sa.Numeric(9, 6), nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.true()),
        *_timestamps(),
    )
    op.create_index("ix_locations_district_id", "locations", ["district_id"])
    op.create_index("ix_locations_location_type_id", "locations", ["location_type_id"])

    op.create_table(
        "warehouses",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "location_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("locations.id"), nullable=False, unique=True
        ),
        sa.Column("code", sa.String(30), nullable=False, unique=True),
        sa.Column("is_central", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("notes", sa.String(500), nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.true()),
        *_timestamps(),
    )

    # --- RBAC ---
    op.create_table(
        "roles",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(80), nullable=False, unique=True),
        sa.Column("description", sa.String(255), nullable=True),
        sa.Column("is_system", sa.Boolean, nullable=False, server_default=sa.false()),
        *_timestamps(),
    )

    op.create_table(
        "permissions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("code", sa.String(80), nullable=False, unique=True),
        sa.Column("module", sa.String(50), nullable=False),
        sa.Column("description", sa.String(255), nullable=True),
        *_timestamps(),
    )

    op.create_table(
        "role_permissions",
        sa.Column("role_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("roles.id"), primary_key=True),
        sa.Column(
            "permission_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("permissions.id"), primary_key=True
        ),
    )

    # --- Users ---
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(255), nullable=False, unique=True),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("first_name", sa.String(100), nullable=False),
        sa.Column("last_name", sa.String(100), nullable=False),
        sa.Column("phone", sa.String(30), nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("region_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("regions.id"), nullable=True),
        sa.Column("district_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("districts.id"), nullable=True),
        sa.Column("failed_login_attempts", sa.Integer, nullable=False, server_default="0"),
        sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        *_timestamps(),
    )
    op.create_index("ix_users_email", "users", ["email"])

    op.create_table(
        "user_roles",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), primary_key=True),
        sa.Column("role_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("roles.id"), primary_key=True),
    )

    op.create_table(
        "refresh_tokens",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("replaced_by_token_hash", sa.String(64), nullable=True),
        sa.Column("user_agent", sa.String(255), nullable=True),
        sa.Column("ip_address", sa.String(64), nullable=True),
        *_timestamps(),
    )
    op.create_index("ix_refresh_tokens_token_hash", "refresh_tokens", ["token_hash"])
    op.create_index("ix_refresh_tokens_user_id", "refresh_tokens", ["user_id"])

    # --- Audit log (immutable; no downgrade data recovery attempted) ---
    op.create_table(
        "audit_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("action", sa.String(50), nullable=False),
        sa.Column("entity_type", sa.String(80), nullable=False),
        sa.Column("entity_id", sa.String(80), nullable=True),
        sa.Column("old_value", postgresql.JSONB, nullable=True),
        sa.Column("new_value", postgresql.JSONB, nullable=True),
        sa.Column("reason", sa.String(500), nullable=True),
        sa.Column("ip_address", sa.String(64), nullable=True),
        sa.Column("user_agent", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_audit_logs_entity", "audit_logs", ["entity_type", "entity_id"])
    op.create_index("ix_audit_logs_created_at", "audit_logs", ["created_at"])


def downgrade() -> None:
    op.drop_table("audit_logs")
    op.drop_table("refresh_tokens")
    op.drop_table("user_roles")
    op.drop_table("users")
    op.drop_table("role_permissions")
    op.drop_table("permissions")
    op.drop_table("roles")
    op.drop_table("warehouses")
    op.drop_table("locations")
    op.drop_table("location_types")
    op.drop_table("enumeration_areas")
    op.drop_table("supervisory_areas")
    op.drop_table("sections")
    op.drop_table("chiefdoms")
    op.drop_table("districts")
    op.drop_table("regions")
