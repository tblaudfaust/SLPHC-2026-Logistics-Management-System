import uuid
from datetime import datetime

from pydantic import BaseModel


class NotificationRead(BaseModel):
    id: uuid.UUID
    event_type: str
    channel: str
    recipient_email: str | None
    recipient_phone: str | None
    subject: str
    status: str
    provider_response: str | None
    related_entity_type: str | None
    related_entity_id: str | None
    created_at: datetime
    sent_at: datetime | None

    model_config = {"from_attributes": True}
