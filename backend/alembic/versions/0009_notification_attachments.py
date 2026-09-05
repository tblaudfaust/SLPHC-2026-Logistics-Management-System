"""Optional attachment on a notification, so a report can be emailed as a
PDF/Excel/CSV file through the same delivery-log/retry pipeline as every
other notification.

Revision ID: 0009
Revises: 0008
Create Date: 2026-09-06

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0009"
down_revision: Union[str, None] = "0008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("notifications", sa.Column("attachment_filename", sa.String(255), nullable=True))
    op.add_column("notifications", sa.Column("attachment_content_b64", sa.Text(), nullable=True))
    op.add_column("notifications", sa.Column("attachment_mime_type", sa.String(100), nullable=True))


def downgrade() -> None:
    op.drop_column("notifications", "attachment_mime_type")
    op.drop_column("notifications", "attachment_content_b64")
    op.drop_column("notifications", "attachment_filename")
