import uuid
from datetime import datetime

from pydantic import BaseModel


class AuditLogRead(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID | None
    action: str
    entity_type: str
    entity_id: str | None
    old_value: dict | None
    new_value: dict | None
    reason: str | None
    ip_address: str | None
    created_at: datetime

    model_config = {"from_attributes": True}
