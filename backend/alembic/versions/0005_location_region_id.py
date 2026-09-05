"""Add locations.region_id — lets a facility be regional-level (no single
district), not just district-level or national (both null).

Revision ID: 0005
Revises: 0004
Create Date: 2026-09-04

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("locations", sa.Column("region_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key("fk_locations_region_id", "locations", "regions", ["region_id"], ["id"])
    op.create_index("ix_locations_region_id", "locations", ["region_id"])


def downgrade() -> None:
    op.drop_index("ix_locations_region_id", table_name="locations")
    op.drop_constraint("fk_locations_region_id", "locations", type_="foreignkey")
    op.drop_column("locations", "region_id")
