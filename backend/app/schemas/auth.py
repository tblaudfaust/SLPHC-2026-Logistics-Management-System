import uuid

from pydantic import BaseModel, EmailStr


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class CurrentUser(BaseModel):
    id: uuid.UUID
    email: str
    first_name: str
    last_name: str
    roles: list[str]
    permissions: list[str]
    region_id: uuid.UUID | None
    district_id: uuid.UUID | None

    model_config = {"from_attributes": True}
