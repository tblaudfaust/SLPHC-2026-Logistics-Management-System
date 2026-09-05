import uuid

from sqlalchemy import Boolean, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.mixins import TimestampMixin, UUIDPKMixin


class Warehouse(Base, UUIDPKMixin, TimestampMixin):
    """A Location that also functions as a storage/dispatch point (brief §5, §8)."""

    __tablename__ = "warehouses"

    location_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("locations.id"), unique=True, nullable=False
    )
    code: Mapped[str] = mapped_column(String(30), unique=True, nullable=False)
    is_central: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    notes: Mapped[str | None] = mapped_column(String(500))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    location: Mapped["Location"] = relationship(back_populates="warehouse")


class UserWarehouseAccess(Base, UUIDPKMixin, TimestampMixin):
    """Restricts a user to specific warehouse(s) — an opt-in geography scope
    on top of RBAC permissions (brief §4: 'see only the functions and
    geography required'). A user with zero rows here is unrestricted
    (national access, subject to their permissions as normal); a user with
    one or more rows can only view and act on inventory at those warehouses,
    regardless of what their permissions would otherwise allow nationally.
    `warehouse_id` references locations.id, matching how every other
    "warehouse_id" column in this codebase (InventoryTransaction,
    GoodsReceipt, StockTransfer) actually points at the Location row, not
    the Warehouse row's own id."""

    __tablename__ = "user_warehouse_access"
    __table_args__ = (UniqueConstraint("user_id", "warehouse_id", name="uq_user_warehouse_access"),)

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    warehouse_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("locations.id"), nullable=False)

    user: Mapped["User"] = relationship(foreign_keys=[user_id])
    warehouse: Mapped["Location"] = relationship()
