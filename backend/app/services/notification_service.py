import base64

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.notification import Notification, NotificationTemplate
from app.models.user import User
from app.services import notification_tasks
from app.services.permission_service import effective_permission_codes


def get_users_with_permission(db: Session, permission_code: str) -> list[User]:
    """Recipient resolution, v1: everyone holding a given permission (reused
    from RBAC rather than a separate subscriptions table). E.g. asset events
    go to whoever can manage the asset catalogue, inventory events to whoever
    can reconcile stock — deliberately narrower than 'everyone who can view',
    to avoid paging every read-only user on every event. A per-user opt-out
    or a proper notification_rules table is the natural next step if this
    turns out to be the wrong set for some event. Includes per-user permission
    overrides, so a user individually GRANTed this permission gets notified
    even without the role, and one individually REVOKEd from it doesn't."""
    # A 3-way roles/role_permissions join is possible in SQL, but role and
    # permission counts are small (tens, not thousands) — filtering in Python
    # after one query is simpler and clearer here.
    users = db.scalars(select(User).where(User.is_active.is_(True))).all()
    return [u for u in users if permission_code in effective_permission_codes(u)]


def notify(
    db: Session,
    *,
    event_type: str,
    context: dict,
    recipients: list[User],
    related_entity_type: str | None = None,
    related_entity_id: str | None = None,
) -> list[Notification]:
    """Renders the DB-driven template for `event_type` and writes one
    Notification (delivery-log) row per recipient, in the SAME transaction as
    the business event that triggered it — added to `db` but not committed;
    the caller commits once, then calls dispatch() with the return value so
    a task is never enqueued for a row that didn't actually get persisted."""
    template = db.scalar(
        select(NotificationTemplate).where(
            NotificationTemplate.event_type == event_type, NotificationTemplate.is_active.is_(True)
        )
    )
    if not template or not recipients:
        return []

    try:
        subject = template.subject_template.format(**context)
        body = template.body_template.format(**context)
        sms_body = template.sms_body_template.format(**context) if template.sms_body_template else None
    except (KeyError, IndexError):
        # A template referencing a placeholder this event doesn't provide
        # must not break the underlying business transaction.
        return []

    created = []
    for user in recipients:
        email_notification = Notification(
            event_type=event_type,
            channel="email",
            recipient_user_id=user.id,
            recipient_email=user.email,
            subject=subject,
            body=body,
            status="PENDING" if settings.email_enabled else "SKIPPED",
            provider_response=None if settings.email_enabled else "SMTP not configured",
            related_entity_type=related_entity_type,
            related_entity_id=related_entity_id,
        )
        db.add(email_notification)
        created.append(email_notification)

        # SMS is opt-in per event (sms_body_template set) and needs a phone
        # number on file — silently skipped otherwise, same as how a missing
        # SMTP config silently marks the email row SKIPPED rather than erroring.
        if sms_body and user.phone:
            sms_notification = Notification(
                event_type=event_type,
                channel="sms",
                recipient_user_id=user.id,
                recipient_phone=user.phone,
                subject=subject,
                body=sms_body,
                status="PENDING" if settings.sms_enabled else "SKIPPED",
                provider_response=None if settings.sms_enabled else "SMS not configured",
                related_entity_type=related_entity_type,
                related_entity_id=related_entity_id,
            )
            db.add(sms_notification)
            created.append(sms_notification)
    return created


def send_direct_email(
    db: Session,
    *,
    recipient_emails: list[str],
    subject: str,
    body: str,
    attachment: tuple[str, bytes, str] | None = None,
    related_entity_type: str | None = None,
    related_entity_id: str | None = None,
) -> list[Notification]:
    """A user-triggered, one-off email — e.g. 'email this report to these
    addresses now' — as opposed to notify()'s DB-templated system events with
    permission-resolved recipients. Goes through the same delivery-log /
    retry / attachment pipeline as every other notification so it shows up
    consistently in the Notification Delivery Report, it's just not backed by
    a NotificationTemplate row and the recipients aren't necessarily system
    users (recipient_user_id stays null when the address isn't a known
    account). `attachment` is (filename, raw bytes, mime type); stored as
    base64 text on the Notification row (see model docstring)."""
    filename, content, mime_type = attachment if attachment else (None, None, None)
    content_b64 = base64.b64encode(content).decode("ascii") if content else None

    created = []
    for email in recipient_emails:
        notification = Notification(
            event_type="reports.email",
            channel="email",
            recipient_user_id=None,
            recipient_email=email,
            subject=subject,
            body=body,
            status="PENDING" if settings.email_enabled else "SKIPPED",
            provider_response=None if settings.email_enabled else "SMTP not configured",
            related_entity_type=related_entity_type,
            related_entity_id=related_entity_id,
            attachment_filename=filename,
            attachment_content_b64=content_b64,
            attachment_mime_type=mime_type,
        )
        db.add(notification)
        created.append(notification)
    return created


def dispatch(notifications: list[Notification]) -> None:
    """Call once, after the enclosing db.commit() has actually succeeded —
    enqueues only the rows that are ready to send, routed to the right
    channel's Celery task."""
    for notification in notifications:
        if notification.status != "PENDING":
            continue
        if notification.channel == "sms":
            notification_tasks.send_sms_notification.delay(str(notification.id))
        else:
            notification_tasks.send_email_notification.delay(str(notification.id))
