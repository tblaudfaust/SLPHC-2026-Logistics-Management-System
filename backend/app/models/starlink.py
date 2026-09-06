import uuid
from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.mixins import TimestampMixin, UUIDPKMixin

# ICT & Connectivity Assets > Starlink Management. A Starlink kit is always
# also a row in `assets` (category "Starlink Kits", already seeded) — this
# module never re-captures what Asset already owns (serial number, status,
# condition, current location/custodian, warranty, cost, supplier). This
# file only adds what's genuinely Starlink-specific: fixed/roaming
# classification, connectivity/installation/subscription state, and the
# field-team deployment machinery the generic Asset Register has no concept
# of. Movement/custody history for the underlying asset itself continues to
# live in `asset_status_events` (asset_service.record_event); the tables
# below add the Starlink-specific context (witness, field team, accessories)
# that a generic asset event doesn't carry.

KIT_TYPES = ["FIXED", "ROAMING"]

OPERATIONAL_STATUSES = [
    "NOT_DEPLOYED",
    "INSTALLED_OPERATIONAL",
    "INSTALLED_OFFLINE",
    "FIELD_OPERATIONAL",
    "FIELD_OFFLINE",
    "UNDER_MAINTENANCE",
    "RETIRED",
]

INSTALLATION_STATUSES = [
    "NOT_INSTALLED",
    "SCHEDULED",
    "IN_PROGRESS",
    "INSTALLED",
    "TESTED",
    "OPERATIONAL",
    "FAULTY",
    "RELOCATED",
    "DECOMMISSIONED",
]

SUBSCRIPTION_STATUSES = [
    "PENDING_ACTIVATION",
    "ACTIVE",
    "EXPIRING_SOON",
    "PAYMENT_DUE",
    "PAYMENT_OVERDUE",
    "SUSPENDED",
    "EXPIRED",
    "CANCELLED",
]

CONNECTIVITY_QUALITIES = ["EXCELLENT", "GOOD", "FAIR", "POOR", "OFFLINE"]

HARD_TO_REACH_CLASSIFICATIONS = [
    "GOOD_COVERAGE",
    "MODERATE_COVERAGE",
    "WEAK_COVERAGE",
    "INTERMITTENT_COVERAGE",
    "NO_COVERAGE",
    "HARD_TO_REACH",
    "STARLINK_RECOMMENDED",
    "STARLINK_REQUIRED",
]

TEAM_ASSIGNMENT_STATUSES = ["ACTIVE", "RETURNED", "OVERDUE"]

FAULT_STATUSES = [
    "REPORTED",
    "ASSIGNED",
    "UNDER_DIAGNOSIS",
    "UNDER_REPAIR",
    "AWAITING_PARTS",
    "RESOLVED",
    "CLOSED",
    "BEYOND_REPAIR",
]

STARLINK_COMPONENT_NAMES = [
    "Starlink Dish/Terminal",
    "Router",
    "Power Supply",
    "Power Cable",
    "Ethernet Adapter",
    "Mounting Kit",
    "Extension Cable",
    "Carrying Case",
    "UPS",
    "Portable Power Supply",
]


class FieldTeam(Base, UUIDPKMixin, TimestampMixin):
    """A census field team — not previously modeled anywhere in this system
    (only individual User accounts existed). Kept intentionally light: a
    team leader by name/phone rather than a full roster, since building
    team-roster management is out of scope for what Starlink assignment
    actually needs."""

    __tablename__ = "field_teams"

    team_code: Mapped[str] = mapped_column(String(30), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    team_type: Mapped[str | None] = mapped_column(String(100))
    """e.g. Field Monitoring, Data Quality Monitoring, GIS, ICT Support, Enumeration Support."""
    team_leader_name: Mapped[str | None] = mapped_column(String(150))
    team_leader_phone: Mapped[str | None] = mapped_column(String(30))
    members: Mapped[str | None] = mapped_column(Text)
    """Free-text roster (names, one per line) — see class docstring."""
    region_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("regions.id"))
    district_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("districts.id"))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    notes: Mapped[str | None] = mapped_column(String(500))

    region: Mapped["Region | None"] = relationship()
    district: Mapped["District | None"] = relationship()


class FundingSource(Base, UUIDPKMixin, TimestampMixin):
    """Database-driven, same principle as AssetCategory/LocationType — admins
    add a new donor/funding line without a code change."""

    __tablename__ = "funding_sources"

    name: Mapped[str] = mapped_column(String(150), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class HardToReachArea(Base, UUIDPKMixin, TimestampMixin):
    """A named operational area with a connectivity-risk classification.
    `starlink_required=True` areas drive the "gap" flag: a field team
    deployed here with no Starlink assigned is a reportable exception."""

    __tablename__ = "hard_to_reach_areas"

    name: Mapped[str] = mapped_column(String(150), nullable=False)
    district_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("districts.id"), nullable=False)
    chiefdom: Mapped[str | None] = mapped_column(String(150))
    classification: Mapped[str] = mapped_column(String(30), nullable=False, default="HARD_TO_REACH")
    starlink_required: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    notes: Mapped[str | None] = mapped_column(String(500))

    district: Mapped["District"] = relationship()


class StarlinkKit(Base, UUIDPKMixin, TimestampMixin):
    """The Starlink-specific extension of an Asset row (one-to-one). Every
    field already on Asset (serial number, status, condition, current
    location/custodian, warranty, unit cost, supplier) is read from there —
    this table only adds what Asset has no concept of."""

    __tablename__ = "starlink_kits"

    asset_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("assets.id"), unique=True, nullable=False)
    kit_type: Mapped[str] = mapped_column(String(10), nullable=False)
    """FIXED or ROAMING."""
    terminal_id: Mapped[str | None] = mapped_column(String(100))
    router_serial_number: Mapped[str | None] = mapped_column(String(150))
    funding_source_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("funding_sources.id"))

    current_field_team_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("field_teams.id"))
    """Set only while a ROAMING kit is on an ACTIVE team assignment."""
    current_hard_to_reach_area_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("hard_to_reach_areas.id")
    )

    operational_status: Mapped[str] = mapped_column(String(30), nullable=False, default="NOT_DEPLOYED")
    installation_status: Mapped[str] = mapped_column(String(30), nullable=False, default="NOT_INSTALLED")
    subscription_status: Mapped[str] = mapped_column(String(30), nullable=False, default="PENDING_ACTIVATION")
    """Denormalized copy of the current StarlinkSubscription's status, kept in
    sync on write — the same "current state lives on the parent row for fast
    reads" pattern Asset itself uses for status/location/custodian."""

    last_connectivity_quality: Mapped[str | None] = mapped_column(String(20))
    last_checkin_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    asset: Mapped["Asset"] = relationship()
    funding_source: Mapped["FundingSource | None"] = relationship()
    current_field_team: Mapped["FieldTeam | None"] = relationship()
    current_hard_to_reach_area: Mapped["HardToReachArea | None"] = relationship()
    components: Mapped[list["StarlinkComponent"]] = relationship(
        back_populates="kit", cascade="all, delete-orphan"
    )


class StarlinkComponent(Base, UUIDPKMixin, TimestampMixin):
    """Per-kit accessory checklist (brief: dish, router, power supply, cables,
    mounting kit, carrying case, UPS, ...) with condition and quantity, so an
    issue/return comparison can flag missing or damaged items."""

    __tablename__ = "starlink_components"

    kit_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("starlink_kits.id"), nullable=False)
    component_name: Mapped[str] = mapped_column(String(100), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    condition: Mapped[str] = mapped_column(String(20), nullable=False, default="NEW")
    notes: Mapped[str | None] = mapped_column(String(255))

    kit: Mapped["StarlinkKit"] = relationship(back_populates="components")


class StarlinkInstallation(Base, UUIDPKMixin, TimestampMixin):
    """One row per installation event (a kit can be installed, relocated and
    reinstalled over its life — this is an append-only log, most recent
    row = current installation)."""

    __tablename__ = "starlink_installations"

    kit_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("starlink_kits.id"), nullable=False)
    installation_type: Mapped[str] = mapped_column(String(20), nullable=False)
    """PERMANENT, TEMPORARY or MOBILE."""
    location_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("locations.id"))
    gps_latitude: Mapped[float | None] = mapped_column(Numeric(9, 6))
    gps_longitude: Mapped[float | None] = mapped_column(Numeric(9, 6))
    installation_date: Mapped[date] = mapped_column(Date, nullable=False)
    technician_name: Mapped[str | None] = mapped_column(String(150))
    installation_company: Mapped[str | None] = mapped_column(String(150))
    mounting_method: Mapped[str | None] = mapped_column(String(100))
    power_source: Mapped[str | None] = mapped_column(String(100))
    backup_power_available: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    installation_cost: Mapped[float | None] = mapped_column(Numeric(12, 2))
    router_installed: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    connectivity_tested: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    download_speed_mbps: Mapped[float | None] = mapped_column(Numeric(8, 2))
    upload_speed_mbps: Mapped[float | None] = mapped_column(Numeric(8, 2))
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    installed_by_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    verified_by_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    acceptance_status: Mapped[str | None] = mapped_column(String(30))
    remarks: Mapped[str | None] = mapped_column(String(1000))

    kit: Mapped["StarlinkKit"] = relationship()
    location: Mapped["Location | None"] = relationship()
    installed_by: Mapped["User | None"] = relationship(foreign_keys=[installed_by_id])
    verified_by: Mapped["User | None"] = relationship(foreign_keys=[verified_by_id])


class StarlinkSubscription(Base, UUIDPKMixin, TimestampMixin):
    """One row per subscription term for a kit (renewals create a new row
    rather than overwriting — `is_current` marks the one StarlinkKit.subscription_status
    is mirrored from)."""

    __tablename__ = "starlink_subscriptions"

    kit_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("starlink_kits.id"), nullable=False)
    account_reference: Mapped[str | None] = mapped_column(String(100))
    plan_name: Mapped[str | None] = mapped_column(String(100))
    subscription_type: Mapped[str | None] = mapped_column(String(50))
    activation_date: Mapped[date | None] = mapped_column(Date)
    subscription_start_date: Mapped[date | None] = mapped_column(Date)
    billing_cycle: Mapped[str | None] = mapped_column(String(30))
    monthly_cost: Mapped[float | None] = mapped_column(Numeric(12, 2))
    annual_estimated_cost: Mapped[float | None] = mapped_column(Numeric(12, 2))
    currency: Mapped[str | None] = mapped_column(String(10))
    last_payment_date: Mapped[date | None] = mapped_column(Date)
    next_payment_date: Mapped[date | None] = mapped_column(Date)
    renewal_date: Mapped[date | None] = mapped_column(Date)
    expiry_date: Mapped[date | None] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="PENDING_ACTIVATION")
    responsible_officer_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    is_current: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    expiry_alert_sent_at: Mapped[str | None] = mapped_column(String(20))
    """Comma-separated thresholds already alerted on (e.g. '30,14,7'), so the
    daily scan never pages the same milestone twice."""
    remarks: Mapped[str | None] = mapped_column(String(1000))

    kit: Mapped["StarlinkKit"] = relationship()
    responsible_officer: Mapped["User | None"] = relationship()
    payments: Mapped[list["StarlinkSubscriptionPayment"]] = relationship(
        back_populates="subscription", order_by="StarlinkSubscriptionPayment.payment_date.desc()"
    )


class StarlinkSubscriptionPayment(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "starlink_subscription_payments"

    subscription_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("starlink_subscriptions.id"), nullable=False
    )
    payment_date: Mapped[date] = mapped_column(Date, nullable=False)
    amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[str | None] = mapped_column(String(10))
    payment_reference: Mapped[str | None] = mapped_column(String(100))
    payment_status: Mapped[str] = mapped_column(String(30), nullable=False, default="PAID")
    recorded_by_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    remarks: Mapped[str | None] = mapped_column(String(500))

    subscription: Mapped["StarlinkSubscription"] = relationship(back_populates="payments")
    recorded_by: Mapped["User | None"] = relationship()


class StarlinkTeamAssignment(Base, UUIDPKMixin, TimestampMixin):
    """A roaming kit's deployment to one field team. Only one row per kit may
    be ACTIVE at a time — enforced in starlink_service, not just the UI."""

    __tablename__ = "starlink_team_assignments"

    kit_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("starlink_kits.id"), nullable=False)
    field_team_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("field_teams.id"), nullable=False)

    region_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("regions.id"))
    district_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("districts.id"))
    chiefdom: Mapped[str | None] = mapped_column(String(150))
    section: Mapped[str | None] = mapped_column(String(150))
    locality: Mapped[str | None] = mapped_column(String(150))
    enumeration_area: Mapped[str | None] = mapped_column(String(100))
    field_location: Mapped[str | None] = mapped_column(String(255))
    hard_to_reach_area_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("hard_to_reach_areas.id"))

    assignment_purpose: Mapped[str | None] = mapped_column(String(255))
    deployment_start_date: Mapped[date] = mapped_column(Date, nullable=False)
    expected_return_date: Mapped[date] = mapped_column(Date, nullable=False)
    actual_return_date: Mapped[date | None] = mapped_column(Date)

    released_by_name: Mapped[str] = mapped_column(String(150), nullable=False)
    received_by_name: Mapped[str | None] = mapped_column(String(150))
    """Always the authenticated user who released/confirmed it — never
    client-supplied, same accountability rule as GoodsReceipt/StockTransfer."""
    witnessed_by_name: Mapped[str | None] = mapped_column(String(150))
    equipment_condition_at_release: Mapped[str | None] = mapped_column(String(20))

    status: Mapped[str] = mapped_column(String(20), nullable=False, default="ACTIVE")
    remarks: Mapped[str | None] = mapped_column(String(1000))
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    overdue_notified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    """Set the first time the overdue-return scan alerts on this assignment,
    so the hourly scan never pages the same overdue kit twice."""

    kit: Mapped["StarlinkKit"] = relationship()
    field_team: Mapped["FieldTeam"] = relationship()
    region: Mapped["Region | None"] = relationship()
    district: Mapped["District | None"] = relationship()
    hard_to_reach_area: Mapped["HardToReachArea | None"] = relationship()
    return_record: Mapped["StarlinkReturn | None"] = relationship(back_populates="assignment", uselist=False)


class StarlinkMovement(Base, UUIDPKMixin, TimestampMixin):
    """Starlink-specific movement context (witness, accessories, field team)
    layered on top of the generic AssetStatusEvent this same action also
    writes — never a substitute for it, an accompaniment."""

    __tablename__ = "starlink_movements"

    kit_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("starlink_kits.id"), nullable=False)
    origin_location_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("locations.id"))
    destination_location_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("locations.id"))
    from_custodian_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    to_custodian_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    field_team_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("field_teams.id"))

    transfer_date: Mapped[date] = mapped_column(Date, nullable=False)
    purpose: Mapped[str | None] = mapped_column(String(255))
    released_by_name: Mapped[str | None] = mapped_column(String(150))
    received_by_name: Mapped[str | None] = mapped_column(String(150))
    witnessed_by_name: Mapped[str | None] = mapped_column(String(150))
    condition_at_release: Mapped[str | None] = mapped_column(String(20))
    condition_at_receipt: Mapped[str | None] = mapped_column(String(20))
    accessories_issued: Mapped[str | None] = mapped_column(String(500))
    accessories_received: Mapped[str | None] = mapped_column(String(500))
    remarks: Mapped[str | None] = mapped_column(String(1000))
    performed_by_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))

    kit: Mapped["StarlinkKit"] = relationship()
    origin_location: Mapped["Location | None"] = relationship(foreign_keys=[origin_location_id])
    destination_location: Mapped["Location | None"] = relationship(foreign_keys=[destination_location_id])
    field_team: Mapped["FieldTeam | None"] = relationship()


class StarlinkCheckin(Base, UUIDPKMixin):
    """A field team's daily connectivity check-in for a roaming kit —
    append-only, no edit/delete, same as AssetStatusEvent/AuditLog."""

    __tablename__ = "starlink_checkins"

    kit_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("starlink_kits.id"), nullable=False)
    field_team_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("field_teams.id"))
    checkin_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    region_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("regions.id"))
    district_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("districts.id"))
    chiefdom_section: Mapped[str | None] = mapped_column(String(150))
    current_location: Mapped[str | None] = mapped_column(String(255))
    gps_latitude: Mapped[float | None] = mapped_column(Numeric(9, 6))
    gps_longitude: Mapped[float | None] = mapped_column(Numeric(9, 6))

    starlink_available: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    starlink_operational: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    internet_available: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    power_available: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    equipment_condition: Mapped[str | None] = mapped_column(String(20))
    connectivity_quality: Mapped[str] = mapped_column(String(20), nullable=False, default="GOOD")
    technical_problem: Mapped[str | None] = mapped_column(String(500))
    technical_support_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    comment: Mapped[str | None] = mapped_column(String(500))
    submitted_by_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))

    kit: Mapped["StarlinkKit"] = relationship()
    field_team: Mapped["FieldTeam | None"] = relationship()
    region: Mapped["Region | None"] = relationship()
    district: Mapped["District | None"] = relationship()
    submitted_by: Mapped["User | None"] = relationship()


class StarlinkFault(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "starlink_faults"

    ticket_number: Mapped[str] = mapped_column(String(30), unique=True, nullable=False)
    kit_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("starlink_kits.id"), nullable=False)
    date_reported: Mapped[date] = mapped_column(Date, nullable=False)
    reported_by_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    current_location_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("locations.id"))
    fault_description: Mapped[str] = mapped_column(String(1000), nullable=False)
    fault_category: Mapped[str | None] = mapped_column(String(100))
    priority: Mapped[str] = mapped_column(String(20), nullable=False, default="MEDIUM")
    technician_assigned: Mapped[str | None] = mapped_column(String(150))
    diagnosis: Mapped[str | None] = mapped_column(String(1000))
    repair_action: Mapped[str | None] = mapped_column(String(1000))
    replacement_parts: Mapped[str | None] = mapped_column(String(500))
    repair_cost: Mapped[float | None] = mapped_column(Numeric(12, 2))
    date_resolved: Mapped[date | None] = mapped_column(Date)
    resolved_by_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    verified_by_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    downtime_hours: Mapped[float | None] = mapped_column(Numeric(8, 2))
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="REPORTED")

    kit: Mapped["StarlinkKit"] = relationship()
    reported_by: Mapped["User | None"] = relationship(foreign_keys=[reported_by_id])
    resolved_by: Mapped["User | None"] = relationship(foreign_keys=[resolved_by_id])
    verified_by: Mapped["User | None"] = relationship(foreign_keys=[verified_by_id])


class StarlinkReturn(Base, UUIDPKMixin, TimestampMixin):
    """Closes out a StarlinkTeamAssignment: itemized issued-vs-returned
    component comparison, discrepancies flagged automatically in
    starlink_service."""

    __tablename__ = "starlink_returns"

    assignment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("starlink_team_assignments.id"), unique=True, nullable=False
    )
    kit_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("starlink_kits.id"), nullable=False)
    returned_by_name: Mapped[str | None] = mapped_column(String(150))
    received_by_name: Mapped[str] = mapped_column(String(150), nullable=False)
    witnessed_by_name: Mapped[str | None] = mapped_column(String(150))
    return_date: Mapped[date] = mapped_column(Date, nullable=False)
    dish_condition: Mapped[str | None] = mapped_column(String(20))
    router_condition: Mapped[str | None] = mapped_column(String(20))
    power_supply_condition: Mapped[str | None] = mapped_column(String(20))
    missing_accessories: Mapped[str | None] = mapped_column(String(500))
    damaged_accessories: Mapped[str | None] = mapped_column(String(500))
    subscription_status_at_return: Mapped[str | None] = mapped_column(String(30))
    final_condition: Mapped[str | None] = mapped_column(String(20))
    reassignment_required: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    maintenance_required: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    remarks: Mapped[str | None] = mapped_column(String(1000))

    assignment: Mapped["StarlinkTeamAssignment"] = relationship(back_populates="return_record")
    kit: Mapped["StarlinkKit"] = relationship()


class StarlinkDocument(Base, UUIDPKMixin):
    """Supporting documents (invoice, PO, delivery note, warranty,
    subscription contract, installation report, photographs). Stored the
    same way NotificationAttachment stores small files — base64 in the row —
    since no object-storage backend is actually wired up in this deployment
    yet (S3_* settings exist but nothing writes to them)."""

    __tablename__ = "starlink_documents"

    kit_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("starlink_kits.id"), nullable=False)
    document_type: Mapped[str] = mapped_column(String(50), nullable=False)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    content_b64: Mapped[str] = mapped_column(Text, nullable=False)
    mime_type: Mapped[str | None] = mapped_column(String(100))
    uploaded_by_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default="now()")
    notes: Mapped[str | None] = mapped_column(String(255))

    kit: Mapped["StarlinkKit"] = relationship()
    uploaded_by: Mapped["User | None"] = relationship()
