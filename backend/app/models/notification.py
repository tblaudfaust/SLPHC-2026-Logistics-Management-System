import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.mixins import UUIDPKMixin

NOTIFICATION_STATUSES = ["PENDING", "SENT", "FAILED", "SKIPPED"]


class NotificationTemplate(Base, UUIDPKMixin):
    """Database-driven wording per event type (brief §5 'notification centre,
    rules and delivery logs') — admins can edit copy without a code change.
    `{placeholders}` are filled via str.format() from the event context."""

    __tablename__ = "notification_templates"

    event_type: Mapped[str] = mapped_column(String(60), unique=True, nullable=False)
    subject_template: Mapped[str] = mapped_column(String(255), nullable=False)
    body_template: Mapped[str] = mapped_column(Text, nullable=False)
    sms_body_template: Mapped[str | None] = mapped_column(Text)
    """Null means this event doesn't send SMS at all (brief §12.4's priority
    table treats SMS as opt-in per event, not every event) — notify() skips
    the SMS channel entirely for an event with no SMS body, regardless of
    whether recipients have phone numbers on file."""
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)


class Notification(Base, UUIDPKMixin):
    """Permanent delivery log (brief §12.5: 'Maintain permanent communication
    delivery logs with recipient, channel, event, timestamp, provider
    response and status'). Rows are written synchronously in the same
    transaction as the triggering business event so the log can never lose an
    entry — actual sending happens afterward via a queued Celery task, which
    is what keeps a slow/down mail server from blocking that transaction."""

    __tablename__ = "notifications"

    event_type: Mapped[str] = mapped_column(String(60), nullable=False)
    channel: Mapped[str] = mapped_column(String(20), nullable=False, default="email")
    """'email' or 'sms'."""
    recipient_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    recipient_email: Mapped[str | None] = mapped_column(String(255))
    recipient_phone: Mapped[str | None] = mapped_column(String(30))
    """Exactly one of recipient_email/recipient_phone is set, matching `channel`."""
    subject: Mapped[str] = mapped_column(String(255), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="PENDING")
    provider_response: Mapped[str | None] = mapped_column(Text)
    """Success confirmation or error detail from the SMTP call, for debugging."""
    related_entity_type: Mapped[str | None] = mapped_column(String(80))
    related_entity_id: Mapped[str | None] = mapped_column(String(80))
    attachment_filename: Mapped[str | None] = mapped_column(String(255))
    attachment_content_b64: Mapped[str | None] = mapped_column(Text)
    """Base64 text, not raw bytes — reports are small (single-digit MB at
    most) and this keeps the attachment in the same row/transaction as the
    rest of the delivery-log entry rather than needing object storage, which
    this project doesn't have set up yet."""
    attachment_mime_type: Mapped[str | None] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    recipient: Mapped["User | None"] = relationship()
