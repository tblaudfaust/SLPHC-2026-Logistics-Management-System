import uuid
from datetime import date

from sqlalchemy import Date, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.mixins import TimestampMixin, UUIDPKMixin

PROCUREMENT_STATUSES = ["DRAFT", "ORDERED", "PARTIALLY_RECEIVED", "RECEIVED", "CANCELLED"]


class Procurement(Base, UUIDPKMixin, TimestampMixin):
    """A procurement batch / purchase order (brief §5, §17 combines
    'procurements' and 'purchase_orders' into one record for Phase 3 — a
    formal PO-vs-batch split can be added later if a real need shows up)."""

    __tablename__ = "procurements"

    supplier_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("suppliers.id"))
    reference: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    """Purchase order number or donor batch reference."""
    description: Mapped[str | None] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="DRAFT")
    order_date: Mapped[date | None] = mapped_column(Date)
    expected_delivery_date: Mapped[date | None] = mapped_column(Date)
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))

    supplier: Mapped["Supplier | None"] = relationship()
