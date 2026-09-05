"""SMS as a second notification channel alongside email: an optional
sms_body_template per event, and a phone-number recipient column on
Notification (recipient_email is now nullable — an SMS row has no email).

Revision ID: 0011
Revises: 0010
Create Date: 2026-09-06

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0011"
down_revision: Union[str, None] = "0010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("notification_templates", sa.Column("sms_body_template", sa.Text(), nullable=True))
    op.add_column("notifications", sa.Column("recipient_phone", sa.String(30), nullable=True))
    op.alter_column("notifications", "recipient_email", existing_type=sa.String(255), nullable=True)


def downgrade() -> None:
    op.alter_column("notifications", "recipient_email", existing_type=sa.String(255), nullable=False)
    op.drop_column("notifications", "recipient_phone")
    op.drop_column("notification_templates", "sms_body_template")
