import uuid

from pydantic import BaseModel


class PermissionRead(BaseModel):
    id: uuid.UUID
    code: str
    module: str
    description: str | None

    model_config = {"from_attributes": True}


class RoleCreate(BaseModel):
    name: str
    description: str | None = None
    permission_ids: list[uuid.UUID] = []


class RoleUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    permission_ids: list[uuid.UUID] | None = None


class RoleRead(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None
    is_system: bool
    permissions: list[PermissionRead]

    model_config = {"from_attributes": True}
