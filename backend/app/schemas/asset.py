import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field, field_validator

from app.models.asset import ASSET_CONDITIONS, ASSET_STATUSES


class AssetCategoryCreate(BaseModel):
    name: str
    code_prefix: str = Field(min_length=2, max_length=10, pattern=r"^[A-Z0-9]+$")
    tracking_type: str = "serialized"


class AssetCategoryRead(BaseModel):
    id: uuid.UUID
    name: str
    code_prefix: str
    tracking_type: str
    is_active: bool
    next_sequence: int

    model_config = {"from_attributes": True}


class AssetModelCreate(BaseModel):
    category_id: uuid.UUID
    brand: str
    model_name: str
    storage: str | None = None
    ram: str | None = None
    operating_system: str | None = None
    specifications: str | None = None


class AssetModelRead(BaseModel):
    id: uuid.UUID
    category_id: uuid.UUID
    brand: str
    model_name: str
    storage: str | None
    ram: str | None
    operating_system: str | None
    specifications: str | None

    model_config = {"from_attributes": True}


class AssetCreate(BaseModel):
    category_id: uuid.UUID
    model_id: uuid.UUID | None = None
    serial_number: str | None = None
    imei_1: str | None = None
    imei_2: str | None = None
    mac_address: str | None = None
    sim_or_phone_number: str | None = None
    supplier_id: uuid.UUID | None = None
    procurement_id: uuid.UUID | None = None
    supplier_or_donor: str | None = None
    procurement_batch: str | None = None
    purchase_order_ref: str | None = None
    date_acquired: date | None = None
    date_received: date | None = None
    unit_cost: float | None = None
    currency: str | None = None
    warranty_start: date | None = None
    warranty_end: date | None = None
    condition: str = Field(default="NEW", description=f"One of: {', '.join(ASSET_CONDITIONS)}")
    current_location_id: uuid.UUID | None = None
    remarks: str | None = None

    @field_validator("condition")
    @classmethod
    def _validate_condition(cls, value: str) -> str:
        if value not in ASSET_CONDITIONS:
            raise ValueError(f"condition must be one of: {', '.join(ASSET_CONDITIONS)}")
        return value


class AssetUpdate(BaseModel):
    model_id: uuid.UUID | None = None
    serial_number: str | None = None
    imei_1: str | None = None
    imei_2: str | None = None
    mac_address: str | None = None
    sim_or_phone_number: str | None = None
    supplier_id: uuid.UUID | None = None
    procurement_id: uuid.UUID | None = None
    supplier_or_donor: str | None = None
    procurement_batch: str | None = None
    purchase_order_ref: str | None = None
    date_acquired: date | None = None
    date_received: date | None = None
    unit_cost: float | None = None
    currency: str | None = None
    warranty_start: date | None = None
    warranty_end: date | None = None
    remarks: str | None = None


class AssetStatusChange(BaseModel):
    new_status: str = Field(description=f"One of: {', '.join(ASSET_STATUSES)}")
    reason: str | None = None

    @field_validator("new_status")
    @classmethod
    def _validate_status(cls, value: str) -> str:
        if value not in ASSET_STATUSES:
            raise ValueError(f"new_status must be one of: {', '.join(ASSET_STATUSES)}")
        return value


class LocationSummary(BaseModel):
    id: uuid.UUID
    name: str

    model_config = {"from_attributes": True}


class UserSummary(BaseModel):
    id: uuid.UUID
    first_name: str
    last_name: str
    email: str

    model_config = {"from_attributes": True}


class AssetRead(BaseModel):
    id: uuid.UUID
    asset_tag: str
    category: AssetCategoryRead
    model: AssetModelRead | None
    serial_number: str | None
    imei_1: str | None
    imei_2: str | None
    mac_address: str | None
    sim_or_phone_number: str | None
    supplier_id: uuid.UUID | None
    procurement_id: uuid.UUID | None
    supplier_or_donor: str | None
    procurement_batch: str | None
    purchase_order_ref: str | None
    date_acquired: date | None
    date_received: date | None
    unit_cost: float | None
    currency: str | None
    warranty_start: date | None
    warranty_end: date | None
    status: str
    condition: str
    current_location: LocationSummary | None
    current_custodian: UserSummary | None
    remarks: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class AssetListItem(BaseModel):
    """Lighter payload for list views — avoids nested category/model/location
    joins fanning out on every row of a 30,000+ asset register (brief §3)."""

    id: uuid.UUID
    asset_tag: str
    category_id: uuid.UUID
    serial_number: str | None
    status: str
    condition: str
    current_location_id: uuid.UUID | None
    current_custodian_id: uuid.UUID | None
    created_at: datetime

    model_config = {"from_attributes": True}


class AssetStatusEventRead(BaseModel):
    id: uuid.UUID
    event_type: str
    previous_status: str | None
    new_status: str | None
    previous_location_id: uuid.UUID | None
    new_location_id: uuid.UUID | None
    previous_custodian_id: uuid.UUID | None
    new_custodian_id: uuid.UUID | None
    condition: str | None
    reason: str | None
    performed_by: UserSummary | None
    created_at: datetime

    model_config = {"from_attributes": True}


# --- Bulk import (brief §19.1/§19.2: "Upload 25,000+ tablet records from
# Excel"). The Excel file itself is parsed client-side (frontend) — the API
# only ever sees structured rows, so it stays format-agnostic. ---

class BulkImportRow(BaseModel):
    row_number: int
    """1-based row number in the source file, including the header — used so
    error messages point the user at the exact spreadsheet row to fix."""
    serial_number: str | None = None
    imei_1: str | None = None
    imei_2: str | None = None
    box_number: str | None = None


class BulkImportRequest(BaseModel):
    category_id: uuid.UUID
    model_id: uuid.UUID | None = None
    current_location_id: uuid.UUID | None = None
    supplier_id: uuid.UUID | None = None
    procurement_id: uuid.UUID | None = None
    commit: bool = False
    """False (default) = validate only, no DB writes ('preview' in the UI).
    True = actually create the valid rows."""
    rows: list[BulkImportRow] = Field(min_length=1, max_length=50_000)


class BulkImportRowError(BaseModel):
    row_number: int
    serial_number: str | None
    reason: str


class BulkImportResponse(BaseModel):
    total_rows: int
    valid_count: int
    invalid_count: int
    errors: list[BulkImportRowError]
    """Capped (see asset_service.MAX_REPORTED_ERRORS) — invalid_count is the
    true total even when this list is truncated."""
    committed: bool
    created_count: int | None = None
    first_asset_tag: str | None = None
    last_asset_tag: str | None = None
