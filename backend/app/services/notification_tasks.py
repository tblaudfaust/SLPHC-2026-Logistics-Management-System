import base64
import json
from datetime import datetime, timezone

from celery.exceptions import MaxRetriesExceededError

from app.core.celery_app import celery_app
from app.db.session import SessionLocal
from app.models.notification import Notification
from app.services.email_service import EmailSendError, send_email
from app.services.sms_service import SmsSendError, send_sms


@celery_app.task(name="notifications.send_email", bind=True, max_retries=3, default_retry_delay=60)
def send_email_notification(self, notification_id: str) -> None:
    """Runs in the celery_worker container, decoupled from the request that
    created the Notification row — a mail-server outage delays delivery and
    retries here, it never fails the asset/inventory transaction that
    triggered it (brief §12). Status stays PENDING across retries (so a retry
    attempt doesn't see a terminal status and skip itself) and only flips to
    FAILED once retries are actually exhausted."""
    db = SessionLocal()
    try:
        notification = db.get(Notification, notification_id)
        if not notification or notification.status != "PENDING":
            return

        try:
            response = send_email(
                to_address=notification.recipient_email,
                subject=notification.subject,
                body=notification.body,
                attachment_filename=notification.attachment_filename,
                attachment_content=(
                    base64.b64decode(notification.attachment_content_b64)
                    if notification.attachment_content_b64
                    else None
                ),
                attachment_mime_type=notification.attachment_mime_type,
            )
        except EmailSendError as exc:
            try:
                raise self.retry(exc=exc)
            except MaxRetriesExceededError:
                notification.status = "FAILED"
                notification.provider_response = str(exc)[:2000]
                db.commit()
            return

        notification.status = "SENT"
        notification.provider_response = response
        notification.sent_at = datetime.now(timezone.utc)
        db.commit()
    finally:
        db.close()


@celery_app.task(name="notifications.send_sms", bind=True, max_retries=3, default_retry_delay=60)
def send_sms_notification(self, notification_id: str) -> None:
    """Mirrors send_email_notification's retry/status pattern exactly, for
    the SMS channel via the AppHiveSL gateway."""
    db = SessionLocal()
    try:
        notification = db.get(Notification, notification_id)
        if not notification or notification.status != "PENDING":
            return

        try:
            response = send_sms(
                to_phone=notification.recipient_phone, content=notification.body,
                reference=str(notification.id),
            )
        except SmsSendError as exc:
            try:
                raise self.retry(exc=exc)
            except MaxRetriesExceededError:
                notification.status = "FAILED"
                notification.provider_response = str(exc)[:2000]
                db.commit()
            return

        notification.status = "SENT"
        notification.provider_response = json.dumps(response)[:2000]
        notification.sent_at = datetime.now(timezone.utc)
        db.commit()
    finally:
        db.close()


@celery_app.task(name="notifications.check_overdue_transfers")
def check_overdue_transfers() -> None:
    """Runs on Celery Beat's schedule (see celery_app.py's beat_schedule) —
    flags stock transfers still IN_TRANSIT past their expected delivery date
    and notifies both parties: whoever dispatched it by name, plus everyone
    holding inventory.reconcile (the destination-side role in practice, since
    there's no single named 'expected receiver' field to target instead)."""
    # Imported here, not at module level: notification_service imports this
    # module too (to call .delay() on send_email_notification), so a
    # top-level import here would be circular.
    from app.services import inventory_service, notification_service

    db = SessionLocal()
    try:
        overdue = inventory_service.find_newly_overdue_transfers(db)
        for transfer in overdue:
            recipients = notification_service.get_users_with_permission(db, "inventory.reconcile")
            recipient_ids = {u.id for u in recipients}
            if transfer.dispatched_by and transfer.dispatched_by.id not in recipient_ids:
                recipients = recipients + [transfer.dispatched_by]

            notifications = notification_service.notify(
                db, event_type="inventory.transfer_overdue",
                context={
                    "category_name": transfer.category.name, "quantity": transfer.quantity,
                    "from_warehouse": transfer.from_warehouse.name, "to_warehouse": transfer.to_warehouse.name,
                    "released_by": transfer.released_by_name,
                    "expected_delivery_date": transfer.expected_delivery_date.isoformat(),
                },
                recipients=recipients,
                related_entity_type="stock_transfer", related_entity_id=str(transfer.id),
            )
            transfer.overdue_notified_at = datetime.now(timezone.utc)
            db.commit()
            notification_service.dispatch(notifications)
    finally:
        db.close()


@celery_app.task(name="notifications.check_starlink_alerts")
def check_starlink_alerts() -> None:
    """Runs on Celery Beat's schedule — scans for subscription milestones
    (30/14/7/3 days out, and expired), unpaid subscriptions, and roaming
    kits overdue for return. Each condition is only ever alerted on once
    (StarlinkSubscription.expiry_alert_sent_at / StarlinkTeamAssignment.overdue_notified_at
    dedupe it), same principle as check_overdue_transfers above."""
    from datetime import date

    from app.models.starlink import StarlinkSubscription, StarlinkTeamAssignment
    from app.services import notification_service

    db = SessionLocal()
    try:
        today = date.today()
        recipients = notification_service.get_users_with_permission(db, "starlink.subscription")

        for sub in db.query(StarlinkSubscription).filter(StarlinkSubscription.is_current.is_(True)).all():
            kit = sub.kit
            already = set((sub.expiry_alert_sent_at or "").split(",")) - {""}
            event_type = None
            milestone = None

            if sub.expiry_date:
                days_remaining = (sub.expiry_date - today).days
                if days_remaining < 0 and "expired" not in already:
                    event_type, milestone = "starlink.subscription_expired", "expired"
                    sub.status = "EXPIRED"
                    kit.subscription_status = "EXPIRED"
                else:
                    for threshold in (30, 14, 7, 3):
                        if 0 <= days_remaining <= threshold and str(threshold) not in already:
                            event_type, milestone = "starlink.subscription_expiring", str(threshold)
                            if sub.status == "ACTIVE":
                                sub.status = "EXPIRING_SOON"
                                kit.subscription_status = "EXPIRING_SOON"
                            break

            if event_type:
                notifications = notification_service.notify(
                    db, event_type=event_type,
                    context={
                        "asset_tag": kit.asset.asset_tag, "kit_type": kit.kit_type,
                        "plan_name": sub.plan_name or "Starlink", "expiry_date": sub.expiry_date.isoformat(),
                        "days_remaining": max(days_remaining, 0),
                    },
                    recipients=recipients, related_entity_type="starlink_kit", related_entity_id=str(kit.id),
                )
                sub.expiry_alert_sent_at = ",".join(sorted(already | {milestone}))
                db.commit()
                notification_service.dispatch(notifications)
            elif sub.status == "PAYMENT_DUE" and sub.next_payment_date and sub.next_payment_date < today:
                sub.status = "PAYMENT_OVERDUE"
                kit.subscription_status = "PAYMENT_OVERDUE"
                notifications = notification_service.notify(
                    db, event_type="starlink.payment_overdue",
                    context={
                        "asset_tag": kit.asset.asset_tag, "plan_name": sub.plan_name or "Starlink",
                        "next_payment_date": sub.next_payment_date.isoformat(),
                    },
                    recipients=recipients, related_entity_type="starlink_kit", related_entity_id=str(kit.id),
                )
                db.commit()
                notification_service.dispatch(notifications)

        assign_recipients = notification_service.get_users_with_permission(db, "starlink.assign")
        overdue_assignments = (
            db.query(StarlinkTeamAssignment)
            .filter(
                StarlinkTeamAssignment.status == "ACTIVE",
                StarlinkTeamAssignment.expected_return_date < today,
                StarlinkTeamAssignment.overdue_notified_at.is_(None),
            )
            .all()
        )
        for assignment in overdue_assignments:
            notifications = notification_service.notify(
                db, event_type="starlink.kit_overdue_return",
                context={
                    "asset_tag": assignment.kit.asset.asset_tag,
                    "team_name": assignment.field_team.name,
                    "expected_return_date": assignment.expected_return_date.isoformat(),
                },
                recipients=assign_recipients,
                related_entity_type="starlink_kit", related_entity_id=str(assignment.kit_id),
            )
            assignment.overdue_notified_at = datetime.now(timezone.utc)
            db.commit()
            notification_service.dispatch(notifications)
    finally:
        db.close()
