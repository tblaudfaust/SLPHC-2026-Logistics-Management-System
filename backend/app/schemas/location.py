import uuid

from pydantic import BaseModel


class RegionRead(BaseModel):
    id: uuid.UUID
    name: str
    code: str

    model_config = {"from_attributes": True}


class RegionCreate(BaseModel):
    name: str
    code: str


class DistrictRead(BaseModel):
    id: uuid.UUID
    name: str
    code: str
    region_id: uuid.UUID

    model_config = {"from_attributes": True}


class DistrictCreate(BaseModel):
    name: str
    code: str
    region_id: uuid.UUID


class LocationTypeRead(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None

    model_config = {"from_attributes": True}


class LocationTypeCreate(BaseModel):
    name: str
    description: str | None = None


class LocationCreate(BaseModel):
    location_type_id: uuid.UUID
    region_id: uuid.UUID | None = None
    district_id: uuid.UUID | None = None
    name: str
    address: str | None = None
    gps_latitude: float | None = None
    gps_longitude: float | None = None


class LocationUpdate(BaseModel):
    name: str | None = None
    address: str | None = None
    gps_latitude: float | None = None
    gps_longitude: float | None = None
    is_active: bool | None = None


class LocationRead(BaseModel):
    id: uuid.UUID
    location_type_id: uuid.UUID
    region_id: uuid.UUID | None
    district_id: uuid.UUID | None
    name: str
    address: str | None
    gps_latitude: float | None
    gps_longitude: float | None
    is_active: bool

    model_config = {"from_attributes": True}
