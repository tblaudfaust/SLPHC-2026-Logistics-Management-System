import uuid
from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, Numeric, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.mixins import TimestampMixin, UUIDPKMixin

# Fuel Management module — added on top of the existing Logistics platform
# rather than beside it: Vehicles and Generators extend Asset exactly the way
# StarlinkKit does (asset_tag, status, current_location, supplier/procurement
# link, condition all stay on Asset; this file only adds what's genuinely
# fuel/vehicle-specific), Starlink kits reference the existing StarlinkKit
# row directly (no separate "starlink_assets" table), Suppliers double as
# fuel vendors, and depots are existing Locations — see fuel_stations for the
# one genuinely new "place" concept (a specific pump site under a vendor).

VEHICLE_TYPES = ["CAR", "PICKUP", "SUV", "TRUCK", "BUS", "MOTORCYCLE", "OTHER"]
"""Motorcycles fold into Vehicle via this field rather than a near-duplicate
table, per the brief's own "use similar fields to vehicles" note."""

FUEL_TYPES = ["PETROL", "DIESEL"]

ALLOCATION_STATUSES = ["ACTIVE", "EXHAUSTED", "EXPIRED", "CLOSED"]

FUEL_REQUEST_STATUSES = [
    "DRAFT", "SUBMITTED", "UNDER_REVIEW", "APPROVED", "REJECTED", "ISSUED", "RECEIVED", "RECONCILED",
]

FUEL_REQUEST_ASSET_TYPES = ["VEHICLE", "GENERATOR", "STARLINK", "OTHER"]

APPROVAL_DECISIONS = ["APPROVED", "REJECTED"]

VOUCHER_STATUSES = ["AVAILABLE", "ISSUED", "REDEEMED", "CANCELLED", "LOST", "RECONCILED"]

FUEL_STOCK_TRANSACTION_TYPES = ["RECEIPT", "ISSUE", "ADJUSTMENT", "PHYSICAL_COUNT"]


class Vehicle(Base, UUIDPKMixin, TimestampMixin):
    """The Starlink-style extension of an Asset row for a vehicle or
    motorcycle (one-to-one). Region/district are deliberately not duplicated
    here — they're derived from `asset.current_location` the same way every
    other asset's geography already works."""

    __tablename__ = "vehicles"

    asset_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("assets.id"), unique=True, nullable=False
    )
    registration_number: Mapped[str] = mapped_column(String(30), unique=True, nullable=False)
    vehicle_type: Mapped[str] = mapped_column(String(20), nullable=False, default="CAR")
    make: Mapped[str | None] = mapped_column(String(80))
    model: Mapped[str | None] = mapped_column(String(80))
    fuel_type: Mapped[str] = mapped_column(String(10), nullable=False, default="DIESEL")
    tank_capacity: Mapped[float | None] = mapped_column(Numeric(8, 2))
    assigned_driver_name: Mapped[str | None] = mapped_column(String(150))
    current_odometer: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    """Updated on every fuel issue/reconciliation so
    fuel_service.vehicle_efficiency() always has a 'previous' reading to
    diff against."""

    asset: Mapped["Asset"] = relationship()


class Generator(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "generators"

    asset_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("assets.id"), unique=True, nullable=False
    )
    capacity_kva: Mapped[float | None] = mapped_column(Numeric(8, 2))
    fuel_type: Mapped[str] = mapped_column(String(10), nullable=False, default="DIESEL")
    current_hour_meter: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False, default=0)

    asset: Mapped["Asset"] = relationship()


class CensusActivity(Base, UUIDPKMixin, TimestampMixin):
    """Database-driven per the platform's established principle (asset
    categories, location types) — administrators can add activities without
    a code change."""

    __tablename__ = "census_activities"

    name: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class FuelSequenceCounter(Base):
    """Backs fuel_service.generate_fuel_reference() — one locked counter row
    per entity type, mirroring asset_service.generate_asset_tag's
    SELECT...FOR UPDATE pattern (not starlink_service.next_sequence_code,
    which is explicitly documented as non-collision-safe)."""

    __tablename__ = "fuel_sequence_counters"

    entity_type: Mapped[str] = mapped_column(String(30), primary_key=True)
    next_sequence: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class FuelStation(Base, UUIDPKMixin, TimestampMixin):
    """A specific pump site under a Supplier — the one genuinely new "place"
    concept, since Supplier alone models the vendor, not a physical site."""

    __tablename__ = "fuel_stations"

    supplier_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("suppliers.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    location_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("locations.id"))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    supplier: Mapped["Supplier"] = relationship()
    location: Mapped["Location | None"] = relationship()


class FuelAllocation(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "fuel_allocations"

    allocation_reference: Mapped[str] = mapped_column(String(40), unique=True, nullable=False)
    region_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("regions.id"))
    district_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("districts.id"))
    activity_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("census_activities.id"))
    fuel_type: Mapped[str] = mapped_column(String(10), nullable=False)
    allocated_litres: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    allocated_budget: Mapped[float | None] = mapped_column(Numeric(14, 2))
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="ACTIVE")
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    low_balance_notified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    """Set the first time the low-allocation alert fires, so the periodic
    check never re-sends it — same dedupe principle as
    StockTransfer.overdue_notified_at."""

    region: Mapped["Region | None"] = relationship()
    district: Mapped["District | None"] = relationship()
    activity: Mapped["CensusActivity | None"] = relationship()
    created_by: Mapped["User | None"] = relationship()
    requests: Mapped[list["FuelRequest"]] = relationship(back_populates="allocation")


class FuelRequest(Base, UUIDPKMixin, TimestampMixin):
    """Status lifecycle exactly as specified: DRAFT -> SUBMITTED ->
    UNDER_REVIEW -> APPROVED/REJECTED -> ISSUED -> RECEIVED -> RECONCILED.
    UNDER_REVIEW means the level-1 (Director) approval has landed; APPROVED
    means the level-2 (Statistician General, or the Deputy Statistician
    General as their designated backup) final approval has landed."""

    __tablename__ = "fuel_requests"

    request_reference: Mapped[str] = mapped_column(String(40), unique=True, nullable=False)
    requester_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    region_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("regions.id"))
    district_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("districts.id"))
    activity_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("census_activities.id"))
    allocation_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("fuel_allocations.id"))

    asset_type: Mapped[str] = mapped_column(String(20), nullable=False)
    """VEHICLE / GENERATOR / STARLINK / OTHER — exactly one of the typed FKs
    below is set, matching asset_type (enforced in fuel_service, not a DB
    CHECK constraint, consistent with how the rest of this codebase
    validates in the service layer)."""
    vehicle_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("vehicles.id"))
    generator_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("generators.id"))
    starlink_kit_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("starlink_kits.id"))

    fuel_type: Mapped[str] = mapped_column(String(10), nullable=False)
    quantity_requested: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    purpose: Mapped[str | None] = mapped_column(String(500))
    destination: Mapped[str | None] = mapped_column(String(255))
    date_required: Mapped[date | None] = mapped_column(Date)
    current_odometer: Mapped[int | None] = mapped_column(Integer)
    expected_distance: Mapped[int | None] = mapped_column(Integer)
    operating_hours: Mapped[float | None] = mapped_column(Numeric(8, 2))
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="DRAFT")

    requester: Mapped["User"] = relationship(foreign_keys=[requester_id])
    region: Mapped["Region | None"] = relationship()
    district: Mapped["District | None"] = relationship()
    activity: Mapped["CensusActivity | None"] = relationship()
    allocation: Mapped["FuelAllocation | None"] = relationship(back_populates="requests")
    vehicle: Mapped["Vehicle | None"] = relationship()
    generator: Mapped["Generator | None"] = relationship()
    starlink_kit: Mapped["StarlinkKit | None"] = relationship()
    approvals: Mapped[list["FuelApproval"]] = relationship(
        back_populates="request", order_by="FuelApproval.approval_level"
    )
    issue: Mapped["FuelIssue | None"] = relationship(back_populates="request", uselist=False)


class FuelApproval(Base, UUIDPKMixin):
    """approval_level 1 = Director review; 2 = final authorization by the
    Statistician General or, in their absence, the Deputy Statistician
    General — whichever of them acts is simply whoever holds
    fuel.approve_final and gets there first; there's no separate delegation
    mechanism to build since the permission is granted to both roles."""

    __tablename__ = "fuel_approvals"

    fuel_request_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("fuel_requests.id"), nullable=False)
    approver_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    approval_level: Mapped[int] = mapped_column(Integer, nullable=False)
    requested_quantity: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    approved_quantity: Mapped[float | None] = mapped_column(Numeric(10, 2))
    decision: Mapped[str] = mapped_column(String(10), nullable=False)
    comments: Mapped[str | None] = mapped_column(String(500))
    approved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    request: Mapped["FuelRequest"] = relationship(back_populates="approvals")
    approver: Mapped["User"] = relationship()


class FuelIssue(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "fuel_issues"

    issue_reference: Mapped[str] = mapped_column(String(40), unique=True, nullable=False)
    fuel_request_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("fuel_requests.id"), unique=True, nullable=False
    )
    supplier_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("suppliers.id"))
    fuel_station_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("fuel_stations.id"))
    quantity_approved: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    quantity_issued: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    price_per_litre: Mapped[float | None] = mapped_column(Numeric(8, 2))
    total_cost: Mapped[float | None] = mapped_column(Numeric(12, 2))
    voucher_number: Mapped[str | None] = mapped_column(String(40))
    issued_by_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    """Always the authenticated user who issued it, not client-supplied —
    same accountability rule as GoodsReceipt/StockTransfer elsewhere."""
    received_by_name: Mapped[str | None] = mapped_column(String(150))
    witness_name: Mapped[str | None] = mapped_column(String(150))
    issue_date: Mapped[date] = mapped_column(Date, nullable=False)
    odometer_reading: Mapped[int | None] = mapped_column(Integer)
    comments: Mapped[str | None] = mapped_column(String(500))
    reconciliation_overdue_notified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    """Dedupe for the "reconciliation overdue" alert, same principle as
    StockTransfer.overdue_notified_at."""

    request: Mapped["FuelRequest"] = relationship(back_populates="issue")
    supplier: Mapped["Supplier | None"] = relationship()
    fuel_station: Mapped["FuelStation | None"] = relationship()
    issued_by: Mapped["User"] = relationship()
    receipt: Mapped["FuelReceipt | None"] = relationship(back_populates="issue", uselist=False)
    reconciliation: Mapped["FuelReconciliation | None"] = relationship(back_populates="issue", uselist=False)


class FuelReceipt(Base, UUIDPKMixin, TimestampMixin):
    """The recipient-confirms step (brief rule: 'recipient must acknowledge
    fuel received'). One-to-one with FuelIssue."""

    __tablename__ = "fuel_receipts"

    fuel_issue_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("fuel_issues.id"), unique=True, nullable=False
    )
    receiver_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    quantity_received: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    date_received: Mapped[date] = mapped_column(Date, nullable=False)
    receipt_number: Mapped[str | None] = mapped_column(String(40))
    acknowledgement: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    attachment: Mapped[str | None] = mapped_column(String(500))
    remarks: Mapped[str | None] = mapped_column(String(500))

    issue: Mapped["FuelIssue"] = relationship(back_populates="receipt")
    receiver: Mapped["User"] = relationship()


class FuelVoucher(Base, UUIDPKMixin, TimestampMixin):
    """Pre-issued voucher redeemable independent of a specific request — a
    separate distribution mechanism from the allocation->request->approval
    chain above. Basic create/list/status this pass, not yet integrated into
    reconciliation."""

    __tablename__ = "fuel_vouchers"

    voucher_number: Mapped[str] = mapped_column(String(40), unique=True, nullable=False)
    value: Mapped[float | None] = mapped_column(Numeric(12, 2))
    litres: Mapped[float | None] = mapped_column(Numeric(10, 2))
    assigned_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    assigned_asset_description: Mapped[str | None] = mapped_column(String(255))
    """Free text (e.g. "Vehicle SLG-1234" or "Generator GEN-002") — vouchers
    aren't necessarily tied to a registered asset the way a fuel_request is."""
    date_issued: Mapped[date | None] = mapped_column(Date)
    date_redeemed: Mapped[date | None] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="AVAILABLE")
    remarks: Mapped[str | None] = mapped_column(String(500))
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))

    assigned_user: Mapped["User | None"] = relationship(foreign_keys=[assigned_user_id])
    created_by: Mapped["User | None"] = relationship(foreign_keys=[created_by_id])


class FuelStockTransaction(Base, UUIDPKMixin):
    """Ledger row for bulk fuel stock at a depot — mirrors InventoryTransaction
    exactly (brief's own 'Inventory must be ledger-driven' principle applied
    to fuel): quantity is a signed delta, on-hand balance is always
    SUM(quantity) grouped by depot+fuel_type, never a stored/editable total.
    depot_location_id points at locations.id (a depot is just a Location,
    same as every "warehouse_id" elsewhere in this codebase)."""

    __tablename__ = "fuel_stock_transactions"

    depot_location_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("locations.id"), nullable=False)
    fuel_type: Mapped[str] = mapped_column(String(10), nullable=False)
    transaction_type: Mapped[str] = mapped_column(String(20), nullable=False)
    quantity: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    """Signed delta — positive adds to stock, negative removes."""
    reference_type: Mapped[str | None] = mapped_column(String(40))
    reference_id: Mapped[str | None] = mapped_column(String(80))
    remarks: Mapped[str | None] = mapped_column(String(500))
    performed_by_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    depot_location: Mapped["Location"] = relationship()
    performed_by: Mapped["User | None"] = relationship()


class FuelReconciliation(Base, UUIDPKMixin):
    __tablename__ = "fuel_reconciliations"

    fuel_issue_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("fuel_issues.id"), unique=True, nullable=False
    )
    reconciled_by_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    quantity_issued: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    quantity_used: Mapped[float | None] = mapped_column(Numeric(10, 2))
    balance: Mapped[float | None] = mapped_column(Numeric(10, 2))
    distance_travelled: Mapped[int | None] = mapped_column(Integer)
    hours_operated: Mapped[float | None] = mapped_column(Numeric(8, 2))
    comments: Mapped[str | None] = mapped_column(String(500))
    reconciliation_date: Mapped[date] = mapped_column(Date, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    issue: Mapped["FuelIssue"] = relationship(back_populates="reconciliation")
    reconciled_by: Mapped["User"] = relationship()
