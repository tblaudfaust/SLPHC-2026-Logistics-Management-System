import uuid

from pydantic import BaseModel


class WarehouseCreate(BaseModel):
    location_id: uuid.UUID
    code: str
    is_central: bool = False
    notes: str | None = None


class WarehouseUpdate(BaseModel):
    code: str | None = None
    is_central: bool | None = None
    notes: str | None = None
    is_active: bool | None = None


class WarehouseRead(BaseModel):
    id: uuid.UUID
    location_id: uuid.UUID
    code: str
    is_central: bool
    notes: str | None
    is_active: bool

    model_config = {"from_attributes": True}
