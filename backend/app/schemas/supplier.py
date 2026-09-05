import uuid

from pydantic import BaseModel, Field, field_validator

SUPPLIER_TYPES = ["supplier", "donor"]


class SupplierCreate(BaseModel):
    name: str
    supplier_type: str = Field(default="supplier", description="'supplier' or 'donor'")
    contact_person: str | None = None
    phone: str | None = None
    email: str | None = None
    address: str | None = None

    @field_validator("supplier_type")
    @classmethod
    def _validate_type(cls, value: str) -> str:
        if value not in SUPPLIER_TYPES:
            raise ValueError(f"supplier_type must be one of: {', '.join(SUPPLIER_TYPES)}")
        return value


class SupplierUpdate(BaseModel):
    name: str | None = None
    contact_person: str | None = None
    phone: str | None = None
    email: str | None = None
    address: str | None = None
    is_active: bool | None = None


class SupplierRead(BaseModel):
    id: uuid.UUID
    name: str
    supplier_type: str
    contact_person: str | None
    phone: str | None
    email: str | None
    address: str | None
    is_active: bool

    model_config = {"from_attributes": True}
