import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, EmailStr, Field


class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    first_name: str
    last_name: str
    phone: str | None = None
    role_ids: list[uuid.UUID] = Field(default_factory=list)
    region_id: uuid.UUID | None = None
    district_id: uuid.UUID | None = None


class UserUpdate(BaseModel):
    first_name: str | None = None
    last_name: str | None = None
    email: EmailStr | None = None
    phone: str | None = None
    is_active: bool | None = None
    role_ids: list[uuid.UUID] | None = None
    region_id: uuid.UUID | None = None
    district_id: uuid.UUID | None = None


class PasswordChange(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8)


class RoleSummary(BaseModel):
    id: uuid.UUID
    name: str

    model_config = {"from_attributes": True}


class UserRead(BaseModel):
    id: uuid.UUID
    email: str
    first_name: str
    last_name: str
    phone: str | None
    is_active: bool
    roles: list[RoleSummary]
    region_id: uuid.UUID | None
    district_id: uuid.UUID | None
    last_login_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


class EffectivePermission(BaseModel):
    """One row of a user's full permission picture: whether their roles grant
    it, whether an individual override sits on top, and the resulting
    effective yes/no — everything the per-user permissions editor needs to
    render in one call."""

    id: uuid.UUID
    code: str
    module: str
    description: str | None
    from_role: bool
    override: Literal["GRANT", "REVOKE"] | None
    effective: bool


class PermissionOverrideEntry(BaseModel):
    permission_id: uuid.UUID
    effect: Literal["GRANT", "REVOKE"]


class UserPermissionOverridesUpdate(BaseModel):
    overrides: list[PermissionOverrideEntry]


class WarehouseAccessRead(BaseModel):
    id: uuid.UUID
    name: str


class WarehouseAccessUpdate(BaseModel):
    warehouse_ids: list[uuid.UUID]
