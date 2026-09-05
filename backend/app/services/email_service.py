import smtplib
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from app.core.config import settings


class EmailSendError(Exception):
    pass


def send_email(
    *,
    to_address: str,
    subject: str,
    body: str,
    attachment_filename: str | None = None,
    attachment_content: bytes | None = None,
    attachment_mime_type: str | None = None,
) -> str:
    """Sends one email synchronously. Called only from inside the Celery task
    (app/services/notification_tasks.py) — never from a request handler, per
    brief §12: a slow/down mail server must never block a core logistics
    transaction. Returns a short human-readable success string for the
    Notification.provider_response audit field; raises EmailSendError on
    failure (the task catches this and marks the row FAILED)."""
    if not settings.email_enabled:
        raise EmailSendError("SMTP is not configured (SMTP_HOST/USERNAME/PASSWORD unset).")

    if attachment_content:
        message: MIMEMultipart | MIMEText = MIMEMultipart()
        message.attach(MIMEText(body, "plain", "utf-8"))
        maintype, _, subtype = (attachment_mime_type or "application/octet-stream").partition("/")
        part = MIMEApplication(attachment_content, _subtype=subtype or "octet-stream")
        part.add_header("Content-Disposition", "attachment", filename=attachment_filename or "attachment")
        message.attach(part)
    else:
        message = MIMEText(body, "plain", "utf-8")

    message["Subject"] = subject
    message["From"] = f"{settings.EMAIL_FROM_NAME} <{settings.EMAIL_FROM_ADDRESS}>"
    message["To"] = to_address

    try:
        if settings.SMTP_USE_SSL:
            server = smtplib.SMTP_SSL(settings.SMTP_HOST, settings.SMTP_PORT, timeout=15)
        else:
            server = smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=15)
        with server:
            if not settings.SMTP_USE_SSL:
                server.starttls()
            server.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
            server.sendmail(settings.EMAIL_FROM_ADDRESS, [to_address], message.as_string())
    except (smtplib.SMTPException, OSError) as exc:
        raise EmailSendError(str(exc)) from exc

    return f"Accepted by {settings.SMTP_HOST} for delivery to {to_address}."
