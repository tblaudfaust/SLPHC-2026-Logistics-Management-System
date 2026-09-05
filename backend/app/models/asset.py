import uuid
from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, Numeric, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.mixins import TimestampMixin, UUIDPKMixin

# Fixed operational workflow states (brief §18 business rules branch on these,
# similar to how shipment statuses are a fixed state machine in §9.2) — unlike
# asset *categories*, which are database-driven per §3.
ASSET_STATUSES = [
    "AVAILABLE",
    "ALLOCATED",
    "IN_TRANSIT",
    "ASSIGNED",
    "RETURNED",
    "UNDER_MAINTENANCE",
    "DAMAGED",
    "LOST",
    "DISPOSED",
]
ASSET_CONDITIONS = ["NEW", "GOOD", "FAIR", "POOR", "DAMAGED", "UNUSABLE"]


class AssetCategory(Base, UUIDPKMixin, TimestampMixin):
    """Database-driven per brief §3 ('administrators can add new categories
    without code changes'). `code_prefix` feeds the SLPHC26-<PREFIX>-000001
    Asset ID convention (brief §6.1); `next_sequence` backs that per-category
    counter (locked with SELECT ... FOR UPDATE on issue, see asset_service)."""

    __tablename__ = "asset_categories"

    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    code_prefix: Mapped[str] = mapped_column(String(10), unique=True, nullable=False)
    tracking_type: Mapped[str] = mapped_column(String(20), nullable=False, default="serialized")
    """'serialized' (individually tracked, brief §3.1) or 'quantity' (stock-movement
    tracked, §3.2). Phase 2 only builds the serialized register; quantity-tracked
    categories get their inventory ledger in Phase 3."""
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    next_sequence: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    models: Mapped[list["AssetModel"]] = relationship(back_populates="category")


class AssetModel(Base, UUIDPKMixin, TimestampMixin):
    """A specific brand/model spec (e.g. 'Samsung Galaxy Tab A8, 64GB'), so
    per-unit technical specs (brief §6.2) aren't duplicated on every asset row."""

    __tablename__ = "asset_models"

    category_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("asset_categories.id"), nullable=False
    )
    brand: Mapped[str] = mapped_column(String(100), nullable=False)
    model_name: Mapped[str] = mapped_column(String(150), nullable=False)
    storage: Mapped[str | None] = mapped_column(String(50))
    ram: Mapped[str | None] = mapped_column(String(50))
    operating_system: Mapped[str | None] = mapped_column(String(100))
    specifications: Mapped[str | None] = mapped_column(String(1000))

    category: Mapped["AssetCategory"] = relationship(back_populates="models")


class Asset(Base, UUIDPKMixin, TimestampMixin):
    """The master serialized asset register (brief §5, §6). Current
    status/location/custodian live here for fast reads (brief §7.3 'Critical
    Asset Snapshot'); every change to them must also append an AssetStatusEvent
    — never edit history, only add to it (brief §7 non-negotiable rule)."""

    __tablename__ = "assets"

    asset_tag: Mapped[str] = mapped_column(String(40), unique=True, nullable=False, index=True)
    category_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("asset_categories.id"), nullable=False
    )
    model_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("asset_models.id"))

    serial_number: Mapped[str | None] = mapped_column(String(150), index=True)
    imei_1: Mapped[str | None] = mapped_column(String(20))
    imei_2: Mapped[str | None] = mapped_column(String(20))
    mac_address: Mapped[str | None] = mapped_column(String(30))
    sim_or_phone_number: Mapped[str | None] = mapped_column(String(30))

    # Procurement/source (brief §6.2). supplier_id/procurement_id (Phase 3)
    # link to the formal registry when the source is known there; the free-text
    # fields stay for ad hoc donations or historical records with no formal
    # procurement entry — both are optional, neither supersedes the other.
    supplier_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("suppliers.id"))
    procurement_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("procurements.id"))
    supplier_or_donor: Mapped[str | None] = mapped_column(String(200))
    procurement_batch: Mapped[str | None] = mapped_column(String(100))
    purchase_order_ref: Mapped[str | None] = mapped_column(String(100))
    date_acquired: Mapped[date | None] = mapped_column(Date)
    date_received: Mapped[date | None] = mapped_column(Date)
    unit_cost: Mapped[float | None] = mapped_column(Numeric(12, 2))
    currency: Mapped[str | None] = mapped_column(String(10))
    warranty_start: Mapped[date | None] = mapped_column(Date)
    warranty_end: Mapped[date | None] = mapped_column(Date)

    status: Mapped[str] = mapped_column(String(30), nullable=False, default="AVAILABLE")
    condition: Mapped[str] = mapped_column(String(20), nullable=False, default="NEW")
    current_location_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("locations.id"))
    current_custodian_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))

    created_by_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    remarks: Mapped[str | None] = mapped_column(String(1000))

    category: Mapped["AssetCategory"] = relationship()
    model: Mapped["AssetModel | None"] = relationship()
    supplier: Mapped["Supplier | None"] = relationship()
    procurement: Mapped["Procurement | None"] = relationship()
    current_location: Mapped["Location | None"] = relationship(foreign_keys=[current_location_id])
    current_custodian: Mapped["User | None"] = relationship(foreign_keys=[current_custodian_id])
    events: Mapped[list["AssetStatusEvent"]] = relationship(
        back_populates="asset", order_by="AssetStatusEvent.created_at.desc()"
    )


class AssetStatusEvent(Base, UUIDPKMixin):
    """Append-only journey log (brief §7.2 'Asset Journey' / §17
    'asset_status_history'). Later phases (dispatch, assignment, maintenance,
    incidents) each add their own specialized tables AND write an event here,
    so the Journey page always has one place to read a unified timeline from."""

    __tablename__ = "asset_status_events"

    asset_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("assets.id"), nullable=False)
    event_type: Mapped[str] = mapped_column(String(40), nullable=False)
    """e.g. 'registered', 'status_change', 'location_change', 'custodian_change'."""
    previous_status: Mapped[str | None] = mapped_column(String(30))
    new_status: Mapped[str | None] = mapped_column(String(30))
    previous_location_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("locations.id"))
    new_location_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("locations.id"))
    previous_custodian_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    new_custodian_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    condition: Mapped[str | None] = mapped_column(String(20))
    reason: Mapped[str | None] = mapped_column(String(500))
    performed_by_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    asset: Mapped["Asset"] = relationship(back_populates="events")
    performed_by: Mapped["User | None"] = relationship(foreign_keys=[performed_by_id])
