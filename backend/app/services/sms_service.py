import base64
import re

import httpx

from app.core.config import settings


class SmsSendError(Exception):
    pass


def normalize_phone_e164(raw: str) -> str:
    """AppHiveSL wants "full E164 format (without '+')" — e.g. 23278123456
    for a Sierra Leone number. Users store phone numbers free-form
    (+232-78-123456, 078 123 456, etc.), so this strips everything but
    digits and fixes up a locally-dialled leading 0 into the 232 country
    code. Not a general-purpose phone library — good enough for Sierra
    Leone numbers, which is all this system's users have."""
    digits = re.sub(r"\D", "", raw)
    if digits.startswith("232"):
        return digits
    if digits.startswith("0"):
        return "232" + digits[1:]
    return digits


def send_sms(*, to_phone: str, content: str, reference: str) -> dict:
    """Sends one SMS synchronously via the AppHiveSL gateway
    (api.sierrahive.com). Called only from inside the Celery task
    (app/services/notification_tasks.py) — never from a request handler,
    same never-block-a-transaction rule as email. Returns the parsed JSON
    response (contains "Ticket"/"Id" and initial "Status": "pending") for
    the Notification.provider_response audit field; raises SmsSendError on
    failure or a non-2xx response."""
    if not settings.sms_enabled:
        raise SmsSendError("SMS is not configured (SMS_CLIENT_ID/SECRET/TOKEN unset).")

    basic = base64.b64encode(f"{settings.SMS_CLIENT_ID}:{settings.SMS_CLIENT_SECRET}".encode()).decode()
    headers = {
        "Authorization": f"Basic {basic}",
        "X-Wallet": f"Token {settings.SMS_TOKEN}",
        "Content-Type": "application/json",
    }
    payload = {
        "From": settings.SMS_SENDER_ID,
        "To": normalize_phone_e164(to_phone),
        "Content": content,
        "Reference": reference,
    }

    try:
        response = httpx.post(
            f"{settings.SMS_API_BASE_URL}/v1/messages/sms", json=payload, headers=headers, timeout=15
        )
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        raise SmsSendError(f"{exc.response.status_code}: {exc.response.text[:500]}") from exc
    except httpx.HTTPError as exc:
        raise SmsSendError(str(exc)) from exc

    return response.json()
