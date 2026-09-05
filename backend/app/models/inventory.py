import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.mixins import TimestampMixin, UUIDPKMixin

# brief §8.1 ledger event types. Phase 3 implements RECEIPT/TRANSFER_IN/
# TRANSFER_OUT/ADJUSTMENT/DISPOSAL directly; DISPATCH/ASSIGNMENT/RETURN/DAMAGE/
# LOSS are reserved here so later phases (shipment, field assignment) write to
# this same ledger instead of inventing a parallel one.
INVENTORY_TRANSACTION_TYPES = [
    "RECEIPT", "TRANSFER_IN", "TRANSFER_OUT", "DISPATCH", "ASSIGNMENT",
    "RETURN", "DAMAGE", "LOSS", "ADJUSTMENT", "DISPOSAL",
]


class InventoryTransaction(Base, UUIDPKMixin):
    """Immutable ledger row for quantity-tracked stock (brief §8 — 'Inventory
    must be ledger-driven. Users must not directly edit stock quantities
    without an approved adjustment transaction'). `quantity` is a signed delta;
    on-hand balance is always SUM(quantity) grouped by warehouse+category,
    never a stored/editable total (§17 Ledger principle)."""

    __tablename__ = "inventory_transactions"

    warehouse_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("locations.id"), nullable=False)
    category_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("asset_categories.id"), nullable=False
    )
    transaction_type: Mapped[str] = mapped_column(String(20), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    """Signed delta — positive adds to stock, negative removes."""
    related_warehouse_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("locations.id"))
    """The other side of a transfer."""
    batch_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), index=True)
    """Groups the rows created by one goods receipt / one transfer / one
    reconciliation together for audit purposes."""
    reference_type: Mapped[str | None] = mapped_column(String(40))
    """e.g. 'goods_receipt', 'stock_count'."""
    reference_id: Mapped[str | None] = mapped_column(String(80))
    reason: Mapped[str | None] = mapped_column(String(500))
    performed_by_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    category: Mapped["AssetCategory"] = relationship()
    warehouse: Mapped["Location"] = relationship(foreign_keys=[warehouse_id])
    related_warehouse: Mapped["Location | None"] = relationship(foreign_keys=[related_warehouse_id])
    performed_by: Mapped["User | None"] = relationship()


class GoodsReceipt(Base, UUIDPKMixin, TimestampMixin):
    """Header record for a goods-receiving event (brief §5 'Goods Receiving',
    §17 lists 'goods_receipts' as its own table — Phase 3 originally folded
    this straight into the ledger; split back out once named accountability
    per receipt was needed, matching brief §7.1's 'released by / received by'
    pattern). The actual stock-quantity effect stays in InventoryTransaction
    rows (reference_type='goods_receipt', reference_id=this row's id) — this
    table is the accountability wrapper around them, not a second ledger."""

    __tablename__ = "goods_receipts"

    warehouse_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("locations.id"), nullable=False)
    supplier_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("suppliers.id"))
    procurement_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("procurements.id"))
    received_by_name: Mapped[str] = mapped_column(String(150), nullable=False)
    """The store officer who received the goods. Always set server-side from
    the authenticated caller (created_by_id) at creation time, never taken
    from client input — a free-text name here would let anyone submitting a
    receipt claim a different person received it, undermining exactly the
    accountability this table exists for. Stored as a name snapshot (rather
    than resolved from created_by_id on read) so the record stays accurate
    even if that user's name later changes or the account is deactivated."""
    delivered_by_name: Mapped[str | None] = mapped_column(String(150))
    """Name of the courier/driver who delivered the goods, if known."""
    receipt_date: Mapped[date] = mapped_column(Date, nullable=False)
    remarks: Mapped[str | None] = mapped_column(String(1000))
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))

    warehouse: Mapped["Location"] = relationship()
    supplier: Mapped["Supplier | None"] = relationship()
    procurement: Mapped["Procurement | None"] = relationship()


STOCK_TRANSFER_STATUSES = ["IN_TRANSIT", "RECEIVED"]


class StockTransfer(Base, UUIDPKMixin, TimestampMixin):
    """Header for a warehouse-to-warehouse movement — two-phase, matching how
    the brief already treats serialized assets and shipments (an IN_TRANSIT
    state between dispatch and receipt, brief §9.2), rather than the earlier
    Phase 3 shortcut of moving stock atomically in one step. Dispatch creates
    the TRANSFER_OUT ledger row immediately (stock leaves the source's on-hand
    count); TRANSFER_IN is only created when receive_transfer() confirms
    arrival, so in-transit stock is never double-counted as on-hand anywhere."""

    __tablename__ = "stock_transfers"

    category_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("asset_categories.id"), nullable=False
    )
    from_warehouse_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("locations.id"), nullable=False)
    to_warehouse_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("locations.id"), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="IN_TRANSIT")
    expected_delivery_date: Mapped[date] = mapped_column(Date, nullable=False)
    actual_delivery_date: Mapped[date | None] = mapped_column(Date)
    released_by_name: Mapped[str] = mapped_column(String(150), nullable=False)
    """Always the authenticated user who dispatched it, not client-supplied —
    see GoodsReceipt.received_by_name's docstring for why."""
    received_by_name: Mapped[str | None] = mapped_column(String(150))
    """Always the authenticated user who confirmed receipt, not client-supplied."""
    reason: Mapped[str | None] = mapped_column(String(500))
    dispatched_by_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    received_by_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    overdue_notified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    """Set the first time the overdue-transfer notification fires, so the
    periodic check (app/services/notification_tasks.py) never re-sends it."""

    category: Mapped["AssetCategory"] = relationship()
    from_warehouse: Mapped["Location"] = relationship(foreign_keys=[from_warehouse_id])
    to_warehouse: Mapped["Location"] = relationship(foreign_keys=[to_warehouse_id])
    dispatched_by: Mapped["User | None"] = relationship(foreign_keys=[dispatched_by_id])
    received_by: Mapped["User | None"] = relationship(foreign_keys=[received_by_id])

    @property
    def is_overdue(self) -> bool:
        return self.status == "IN_TRANSIT" and self.expected_delivery_date < date.today()


class StockCount(Base, UUIDPKMixin, TimestampMixin):
    """A physical stock-count session for one warehouse (brief §8.2 reconciliation)."""

    __tablename__ = "stock_counts"

    warehouse_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("locations.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="DRAFT")
    """DRAFT (counting in progress) or COMPLETED (adjustments posted, locked)."""
    count_date: Mapped[date] = mapped_column(Date, nullable=False)
    counted_by_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    notes: Mapped[str | None] = mapped_column(String(1000))

    items: Mapped[list["StockCountItem"]] = relationship(back_populates="stock_count", cascade="all, delete-orphan")


class StockCountItem(Base, UUIDPKMixin):
    """expected_quantity is a snapshot of the ledger balance taken when the
    line was counted — never recomputed later, so the variance stays
    meaningful even as new transactions land after the count."""

    __tablename__ = "stock_count_items"

    stock_count_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("stock_counts.id"), nullable=False)
    category_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("asset_categories.id"), nullable=False
    )
    expected_quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    physical_quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    variance_reason: Mapped[str | None] = mapped_column(String(500))

    stock_count: Mapped["StockCount"] = relationship(back_populates="items")
    category: Mapped["AssetCategory"] = relationship()

    @property
    def variance(self) -> int:
        return self.physical_quantity - self.expected_quantity
