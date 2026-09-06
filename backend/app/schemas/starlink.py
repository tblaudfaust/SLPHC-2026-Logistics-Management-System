import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field


# ---- Field teams / funding sources / hard-to-reach areas ----

class FieldTeamCreate(BaseModel):
    name: str
    team_type: str | None = None
    team_leader_name: str | None = None
    team_leader_phone: str | None = None
    members: str | None = None
    region_id: uuid.UUID | None = None
    district_id: uuid.UUID | None = None
    notes: str | None = None


class FieldTeamUpdate(BaseModel):
    name: str | None = None
    team_type: str | None = None
    team_leader_name: str | None = None
    team_leader_phone: str | None = None
    members: str | None = None
    region_id: uuid.UUID | None = None
    district_id: uuid.UUID | None = None
    is_active: bool | None = None
    notes: str | None = None


class FieldTeamRead(BaseModel):
    id: uuid.UUID
    team_code: str
    name: str
    team_type: str | None
    team_leader_name: str | None
    team_leader_phone: str | None
    region_id: uuid.UUID | None
    district_id: uuid.UUID | None
    is_active: bool

    model_config = {"from_attributes": True}


class FundingSourceCreate(BaseModel):
    name: str
    description: str | None = None


class FundingSourceRead(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None
    is_active: bool

    model_config = {"from_attributes": True}


class HardToReachAreaCreate(BaseModel):
    name: str
    district_id: uuid.UUID
    chiefdom: str | None = None
    classification: str = "HARD_TO_REACH"
    starlink_required: bool = False
    notes: str | None = None


class HardToReachAreaUpdate(BaseModel):
    name: str | None = None
    chiefdom: str | None = None
    classification: str | None = None
    starlink_required: bool | None = None
    notes: str | None = None


class HardToReachAreaRead(BaseModel):
    id: uuid.UUID
    name: str
    district_id: uuid.UUID
    chiefdom: str | None
    classification: str
    starlink_required: bool
    notes: str | None

    model_config = {"from_attributes": True}


# ---- Starlink kit (asset + extension, created together) ----

class StarlinkComponentInput(BaseModel):
    component_name: str
    quantity: int = Field(default=1, gt=0)
    condition: str = "NEW"
    notes: str | None = None


class StarlinkKitCreate(BaseModel):
    # Physical-asset side (becomes the underlying Asset row).
    model_id: uuid.UUID | None = None
    serial_number: str | None = None
    supplier_id: uuid.UUID | None = None
    procurement_id: uuid.UUID | None = None
    supplier_or_donor: str | None = None
    purchase_order_ref: str | None = None
    invoice_number: str | None = None
    date_acquired: date | None = None
    date_received: date | None = None
    unit_cost: float | None = None
    currency: str | None = None
    warranty_start: date | None = None
    warranty_end: date | None = None
    current_location_id: uuid.UUID | None = None
    condition: str = "NEW"
    remarks: str | None = None

    # Starlink-specific side.
    kit_type: str = Field(description="FIXED or ROAMING")
    terminal_id: str | None = None
    router_serial_number: str | None = None
    funding_source_id: uuid.UUID | None = None
    components: list[StarlinkComponentInput] = Field(default_factory=list)


class StarlinkKitUpdate(BaseModel):
    terminal_id: str | None = None
    router_serial_number: str | None = None
    funding_source_id: uuid.UUID | None = None
    remarks: str | None = None


class StarlinkComponentRead(BaseModel):
    id: uuid.UUID
    component_name: str
    quantity: int
    condition: str
    notes: str | None

    model_config = {"from_attributes": True}


class AssetSummary(BaseModel):
    id: uuid.UUID
    asset_tag: str
    serial_number: str | None
    status: str
    condition: str
    current_location_id: uuid.UUID | None
    current_custodian_id: uuid.UUID | None
    unit_cost: float | None
    currency: str | None
    warranty_start: date | None
    warranty_end: date | None
    date_acquired: date | None

    model_config = {"from_attributes": True}


class StarlinkKitRead(BaseModel):
    id: uuid.UUID
    asset_id: uuid.UUID
    kit_type: str
    terminal_id: str | None
    router_serial_number: str | None
    funding_source_id: uuid.UUID | None
    current_field_team_id: uuid.UUID | None
    current_hard_to_reach_area_id: uuid.UUID | None
    operational_status: str
    installation_status: str
    subscription_status: str
    last_connectivity_quality: str | None
    last_checkin_at: datetime | None
    asset: AssetSummary
    components: list[StarlinkComponentRead]

    model_config = {"from_attributes": True}


# ---- Installations ----

class StarlinkInstallationCreate(BaseModel):
    installation_type: str = Field(description="PERMANENT, TEMPORARY or MOBILE")
    location_id: uuid.UUID | None = None
    gps_latitude: float | None = None
    gps_longitude: float | None = None
    installation_date: date
    technician_name: str | None = None
    installation_company: str | None = None
    mounting_method: str | None = None
    power_source: str | None = None
    backup_power_available: bool = False
    installation_cost: float | None = None
    router_installed: bool = True
    connectivity_tested: bool = False
    download_speed_mbps: float | None = None
    upload_speed_mbps: float | None = None
    latency_ms: int | None = None
    verified_by_id: uuid.UUID | None = None
    acceptance_status: str | None = None
    remarks: str | None = None


class StarlinkInstallationRead(BaseModel):
    id: uuid.UUID
    kit_id: uuid.UUID
    installation_type: str
    location_id: uuid.UUID | None
    installation_date: date
    technician_name: str | None
    connectivity_tested: bool
    download_speed_mbps: float | None
    upload_speed_mbps: float | None
    latency_ms: int | None
    acceptance_status: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


# ---- Subscriptions ----

class StarlinkSubscriptionCreate(BaseModel):
    account_reference: str | None = None
    plan_name: str | None = None
    subscription_type: str | None = None
    activation_date: date | None = None
    subscription_start_date: date | None = None
    billing_cycle: str | None = None
    monthly_cost: float | None = None
    annual_estimated_cost: float | None = None
    currency: str | None = None
    next_payment_date: date | None = None
    renewal_date: date | None = None
    expiry_date: date | None = None
    status: str = "PENDING_ACTIVATION"
    responsible_officer_id: uuid.UUID | None = None
    remarks: str | None = None


class StarlinkSubscriptionRead(BaseModel):
    id: uuid.UUID
    kit_id: uuid.UUID
    account_reference: str | None
    plan_name: str | None
    monthly_cost: float | None
    currency: str | None
    next_payment_date: date | None
    renewal_date: date | None
    expiry_date: date | None
    status: str
    is_current: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class StarlinkPaymentCreate(BaseModel):
    payment_date: date
    amount: float
    currency: str | None = None
    payment_reference: str | None = None
    payment_status: str = "PAID"
    remarks: str | None = None


class StarlinkPaymentRead(BaseModel):
    id: uuid.UUID
    subscription_id: uuid.UUID
    payment_date: date
    amount: float
    currency: str | None
    payment_status: str

    model_config = {"from_attributes": True}


# ---- Field team assignment ----

class StarlinkTeamAssignmentCreate(BaseModel):
    field_team_id: uuid.UUID
    region_id: uuid.UUID | None = None
    district_id: uuid.UUID | None = None
    chiefdom: str | None = None
    section: str | None = None
    locality: str | None = None
    enumeration_area: str | None = None
    field_location: str | None = None
    hard_to_reach_area_id: uuid.UUID | None = None
    assignment_purpose: str | None = None
    deployment_start_date: date
    expected_return_date: date
    witnessed_by_name: str | None = None
    equipment_condition_at_release: str = "GOOD"
    remarks: str | None = None


class StarlinkTeamAssignmentRead(BaseModel):
    id: uuid.UUID
    kit_id: uuid.UUID
    field_team_id: uuid.UUID
    region_id: uuid.UUID | None
    district_id: uuid.UUID | None
    hard_to_reach_area_id: uuid.UUID | None
    deployment_start_date: date
    expected_return_date: date
    actual_return_date: date | None
    released_by_name: str
    received_by_name: str | None
    witnessed_by_name: str | None
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


class StarlinkReturnCreate(BaseModel):
    witnessed_by_name: str | None = None
    return_date: date
    dish_condition: str = "GOOD"
    router_condition: str = "GOOD"
    power_supply_condition: str = "GOOD"
    missing_accessories: str | None = None
    damaged_accessories: str | None = None
    reassignment_required: bool = False
    maintenance_required: bool = False
    remarks: str | None = None


class StarlinkReturnRead(BaseModel):
    id: uuid.UUID
    assignment_id: uuid.UUID
    kit_id: uuid.UUID
    return_date: date
    final_condition: str | None
    missing_accessories: str | None
    damaged_accessories: str | None
    reassignment_required: bool
    maintenance_required: bool

    model_config = {"from_attributes": True}


# ---- Movements ----

class StarlinkMovementCreate(BaseModel):
    destination_location_id: uuid.UUID | None = None
    to_custodian_id: uuid.UUID | None = None
    field_team_id: uuid.UUID | None = None
    transfer_date: date
    purpose: str | None = None
    witnessed_by_name: str | None = None
    condition_at_release: str = "GOOD"
    condition_at_receipt: str | None = None
    accessories_issued: str | None = None
    accessories_received: str | None = None
    remarks: str | None = None


class StarlinkMovementRead(BaseModel):
    id: uuid.UUID
    kit_id: uuid.UUID
    origin_location_id: uuid.UUID | None
    destination_location_id: uuid.UUID | None
    transfer_date: date
    released_by_name: str | None
    received_by_name: str | None
    witnessed_by_name: str | None
    purpose: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


# ---- Check-ins ----

class StarlinkCheckinCreate(BaseModel):
    kit_id: uuid.UUID
    checkin_at: datetime | None = None
    region_id: uuid.UUID | None = None
    district_id: uuid.UUID | None = None
    chiefdom_section: str | None = None
    current_location: str | None = None
    gps_latitude: float | None = None
    gps_longitude: float | None = None
    starlink_available: bool = True
    starlink_operational: bool = True
    internet_available: bool = True
    power_available: bool = True
    equipment_condition: str | None = None
    connectivity_quality: str = "GOOD"
    technical_problem: str | None = None
    technical_support_required: bool = False
    comment: str | None = None


class StarlinkCheckinRead(BaseModel):
    id: uuid.UUID
    kit_id: uuid.UUID
    field_team_id: uuid.UUID | None
    checkin_at: datetime
    connectivity_quality: str
    starlink_operational: bool
    internet_available: bool
    power_available: bool
    technical_support_required: bool
    comment: str | None

    model_config = {"from_attributes": True}


# ---- Faults ----

class StarlinkFaultCreate(BaseModel):
    date_reported: date
    fault_description: str
    fault_category: str | None = None
    priority: str = "MEDIUM"


class StarlinkFaultUpdate(BaseModel):
    technician_assigned: str | None = None
    diagnosis: str | None = None
    repair_action: str | None = None
    replacement_parts: str | None = None
    repair_cost: float | None = None
    date_resolved: date | None = None
    verified_by_id: uuid.UUID | None = None
    downtime_hours: float | None = None
    status: str | None = None


class StarlinkFaultRead(BaseModel):
    id: uuid.UUID
    ticket_number: str
    kit_id: uuid.UUID
    date_reported: date
    fault_description: str
    priority: str
    status: str
    date_resolved: date | None
    created_at: datetime

    model_config = {"from_attributes": True}


# ---- Dashboard ----

class StarlinkDashboardSummary(BaseModel):
    total_kits: int
    fixed_kits: int
    roaming_kits: int
    available_kits: int
    deployed_kits: int
    under_maintenance_kits: int
    damaged_or_lost_kits: int

    installed: int
    awaiting_installation: int
    installed_and_operational: int
    installed_but_offline: int

    subscriptions_active: int
    subscriptions_expiring_30d: int
    subscriptions_expiring_14d: int
    subscriptions_expiring_7d: int
    subscriptions_expired: int
    payments_overdue: int

    roaming_assigned_to_teams: int
    teams_in_hard_to_reach_areas: int
    hard_to_reach_with_connectivity: int
    hard_to_reach_without_connectivity: int
    kits_overdue_for_return: int
    hard_to_reach_gap: int
    """Field teams deployed to a Starlink-required area with no active
    Starlink assignment — the core exception this whole module exists to
    surface."""

    online_kits: int
    offline_kits: int
    support_requested: int
