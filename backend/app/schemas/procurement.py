import uuid
from datetime import date

from pydantic import BaseModel, Field, field_validator

from app.models.procurement import PROCUREMENT_STATUSES
from app.schemas.supplier import SupplierRead


class ProcurementCreate(BaseModel):
    supplier_id: uuid.UUID | None = None
    reference: str
    description: str | None = None
    order_date: date | None = None
    expected_delivery_date: date | None = None


class ProcurementUpdate(BaseModel):
    description: str | None = None
    status: str | None = Field(default=None, description=f"One of: {', '.join(PROCUREMENT_STATUSES)}")
    expected_delivery_date: date | None = None

    @field_validator("status")
    @classmethod
    def _validate_status(cls, value: str | None) -> str | None:
        if value is not None and value not in PROCUREMENT_STATUSES:
            raise ValueError(f"status must be one of: {', '.join(PROCUREMENT_STATUSES)}")
        return value


class ProcurementRead(BaseModel):
    id: uuid.UUID
    supplier: SupplierRead | None
    reference: str
    description: str | None
    status: str
    order_date: date | None
    expected_delivery_date: date | None

    model_config = {"from_attributes": True}
