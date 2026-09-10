import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field

from app.models.fuel import FUEL_REQUEST_ASSET_TYPES, VEHICLE_TYPES


# --- Shared summaries (kept local to this module, same convention already
# used by schemas/starlink.py rather than cross-importing between domains) ---

class UserSummary(BaseModel):
    id: uuid.UUID
    first_name: str
    last_name: str
    email: str

    model_config = {"from_attributes": True}


class LocationSummary(BaseModel):
    id: uuid.UUID
    name: str

    model_config = {"from_attributes": True}


class RegionSummary(BaseModel):
    id: uuid.UUID
    name: str

    model_config = {"from_attributes": True}


class DistrictSummary(BaseModel):
    id: uuid.UUID
    name: str

    model_config = {"from_attributes": True}


class AssetSummary(BaseModel):
    id: uuid.UUID
    asset_tag: str
    status: str
    current_location_id: uuid.UUID | None

    model_config = {"from_attributes": True}


# --- Census activities ---

class CensusActivityCreate(BaseModel):
    name: str
    is_active: bool = True


class CensusActivityRead(BaseModel):
    id: uuid.UUID
    name: str
    is_active: bool

    model_config = {"from_attributes": True}


# --- Vehicles / Generators ---

class VehicleCreate(BaseModel):
    registration_number: str
    vehicle_type: str = Field(default="CAR", description=f"One of: {', '.join(VEHICLE_TYPES)}")
    make: str | None = None
    model: str | None = None
    fuel_type: str = "DIESEL"
    tank_capacity: float | None = None
    assigned_driver_name: str | None = None
    current_odometer: int = 0
    current_location_id: uuid.UUID | None = None
    condition: str = "NEW"


class VehicleRead(BaseModel):
    id: uuid.UUID
    asset: AssetSummary
    registration_number: str
    vehicle_type: str
    make: str | None
    model: str | None
    fuel_type: str
    tank_capacity: float | None
    assigned_driver_name: str | None
    current_odometer: int

    model_config = {"from_attributes": True}


class GeneratorCreate(BaseModel):
    asset_code: str | None = Field(default=None, description="Optional custom asset tag suffix; auto-generated if omitted")
    capacity_kva: float | None = None
    fuel_type: str = "DIESEL"
    current_hour_meter: float = 0
    current_location_id: uuid.UUID | None = None
    condition: str = "NEW"


class GeneratorRead(BaseModel):
    id: uuid.UUID
    asset: AssetSummary
    capacity_kva: float | None
    fuel_type: str
    current_hour_meter: float

    model_config = {"from_attributes": True}


# --- Fuel stations ---

class FuelStationCreate(BaseModel):
    supplier_id: uuid.UUID
    name: str
    location_id: uuid.UUID | None = None


class FuelStationRead(BaseModel):
    id: uuid.UUID
    supplier_id: uuid.UUID
    name: str
    location: LocationSummary | None
    is_active: bool

    model_config = {"from_attributes": True}


# --- Fuel allocations ---

class FuelAllocationCreate(BaseModel):
    region_id: uuid.UUID | None = None
    district_id: uuid.UUID | None = None
    activity_id: uuid.UUID | None = None
    fuel_type: str
    allocated_litres: float = Field(gt=0)
    allocated_budget: float | None = None
    start_date: date
    end_date: date


class FuelAllocationRead(BaseModel):
    id: uuid.UUID
    allocation_reference: str
    region: RegionSummary | None
    district: DistrictSummary | None
    activity: CensusActivityRead | None
    fuel_type: str
    allocated_litres: float
    allocated_budget: float | None
    start_date: date
    end_date: date
    status: str
    litres_requested: float = 0
    litres_approved: float = 0
    litres_issued: float = 0
    litres_remaining: float = 0
    created_at: datetime

    model_config = {"from_attributes": True}


# --- Fuel requests ---

class FuelRequestCreate(BaseModel):
    region_id: uuid.UUID | None = None
    district_id: uuid.UUID | None = None
    activity_id: uuid.UUID | None = None
    allocation_id: uuid.UUID | None = None
    asset_type: str = Field(description=f"One of: {', '.join(FUEL_REQUEST_ASSET_TYPES)}")
    vehicle_id: uuid.UUID | None = None
    generator_id: uuid.UUID | None = None
    starlink_kit_id: uuid.UUID | None = None
    fuel_type: str
    quantity_requested: float = Field(gt=0)
    purpose: str | None = None
    destination: str | None = None
    date_required: date | None = None
    current_odometer: int | None = None
    expected_distance: int | None = None
    operating_hours: float | None = None


class FuelRequestRead(BaseModel):
    id: uuid.UUID
    request_reference: str
    requester: UserSummary
    region: RegionSummary | None
    district: DistrictSummary | None
    activity: CensusActivityRead | None
    allocation_id: uuid.UUID | None
    asset_type: str
    vehicle: VehicleRead | None
    generator: GeneratorRead | None
    fuel_type: str
    quantity_requested: float
    purpose: str | None
    destination: str | None
    date_required: date | None
    current_odometer: int | None
    expected_distance: int | None
    operating_hours: float | None
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


class FuelApprovalDecision(BaseModel):
    approved_quantity: float | None = Field(default=None, ge=0, description="Required when decision=APPROVED")
    decision: str = Field(description="APPROVED or REJECTED")
    comments: str | None = None


class FuelApprovalRead(BaseModel):
    id: uuid.UUID
    approver: UserSummary
    approval_level: int
    requested_quantity: float
    approved_quantity: float | None
    decision: str
    comments: str | None
    approved_at: datetime

    model_config = {"from_attributes": True}


# --- Fuel issuance / receipt ---

class FuelIssueCreate(BaseModel):
    fuel_request_id: uuid.UUID
    supplier_id: uuid.UUID | None = None
    fuel_station_id: uuid.UUID | None = None
    quantity_issued: float = Field(gt=0)
    price_per_litre: float | None = None
    voucher_number: str | None = None
    witness_name: str | None = None
    issue_date: date
    odometer_reading: int | None = None
    comments: str | None = None
    depot_location_id: uuid.UUID = Field(description="Depot the fuel is drawn from, for the stock ledger")


class FuelIssueRead(BaseModel):
    id: uuid.UUID
    issue_reference: str
    fuel_request_id: uuid.UUID
    supplier_id: uuid.UUID | None
    fuel_station_id: uuid.UUID | None
    quantity_approved: float
    quantity_issued: float
    price_per_litre: float | None
    total_cost: float | None
    voucher_number: str | None
    issued_by: UserSummary
    received_by_name: str | None
    witness_name: str | None
    issue_date: date
    odometer_reading: int | None
    comments: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class FuelRequestDetailRead(FuelRequestRead):
    approvals: list[FuelApprovalRead]
    issue: FuelIssueRead | None = None


class FuelReceiptCreate(BaseModel):
    quantity_received: float = Field(gt=0)
    date_received: date
    receipt_number: str | None = None
    acknowledgement: bool = True
    attachment: str | None = None
    remarks: str | None = None


class FuelReceiptRead(BaseModel):
    id: uuid.UUID
    fuel_issue_id: uuid.UUID
    receiver: UserSummary
    quantity_received: float
    date_received: date
    receipt_number: str | None
    acknowledgement: bool
    attachment: str | None
    remarks: str | None

    model_config = {"from_attributes": True}


# --- Fuel vouchers ---

class FuelVoucherCreate(BaseModel):
    voucher_number: str
    value: float | None = None
    litres: float | None = None
    assigned_user_id: uuid.UUID | None = None
    assigned_asset_description: str | None = None
    date_issued: date | None = None
    remarks: str | None = None


class FuelVoucherStatusUpdate(BaseModel):
    status: str = Field(description="ISSUED / REDEEMED / CANCELLED / LOST / RECONCILED")
    date_redeemed: date | None = None
    remarks: str | None = None


class FuelVoucherRead(BaseModel):
    id: uuid.UUID
    voucher_number: str
    value: float | None
    litres: float | None
    assigned_user: UserSummary | None
    assigned_asset_description: str | None
    date_issued: date | None
    date_redeemed: date | None
    status: str
    remarks: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


# --- Fuel stock ---

class FuelStockReceiptCreate(BaseModel):
    depot_location_id: uuid.UUID
    fuel_type: str
    quantity: float = Field(gt=0)
    supplier_id: uuid.UUID | None = None
    remarks: str | None = None


class FuelStockAdjustmentCreate(BaseModel):
    depot_location_id: uuid.UUID
    fuel_type: str
    quantity_delta: float = Field(description="Signed correction — positive adds stock, negative removes it")
    reason: str = Field(min_length=1)


class FuelStockBalance(BaseModel):
    depot_location_id: uuid.UUID
    depot_name: str
    fuel_type: str
    quantity_on_hand: float


# --- Reconciliation ---

class FuelReconciliationCreate(BaseModel):
    quantity_used: float | None = Field(default=None, ge=0)
    distance_travelled: int | None = None
    hours_operated: float | None = None
    comments: str | None = None
    reconciliation_date: date


class FuelReconciliationRead(BaseModel):
    id: uuid.UUID
    fuel_issue_id: uuid.UUID
    reconciled_by: UserSummary
    quantity_issued: float
    quantity_used: float | None
    balance: float | None
    distance_travelled: int | None
    hours_operated: float | None
    comments: str | None
    reconciliation_date: date

    model_config = {"from_attributes": True}


# --- Dashboard ---

class FuelDashboardSummary(BaseModel):
    total_allocated_litres: float
    total_requested_litres: float
    total_approved_litres: float
    total_issued_litres: float
    total_received_litres: float
    total_consumed_litres: float
    remaining_balance_litres: float
    total_expenditure: float
    pending_requests: int
    pending_approvals: int
    unreconciled_transactions: int
    active_vehicles: int
    active_generators: int
    active_starlink_teams: int
    consumption_by_region: list[dict]
    allocation_vs_consumption: list[dict]
