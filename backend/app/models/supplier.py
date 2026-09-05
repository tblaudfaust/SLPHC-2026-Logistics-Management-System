from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.mixins import TimestampMixin, UUIDPKMixin


class Supplier(Base, UUIDPKMixin, TimestampMixin):
    """A vendor or donor source (brief §5 'Procurement & Source', §6.2)."""

    __tablename__ = "suppliers"

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    supplier_type: Mapped[str] = mapped_column(String(20), nullable=False, default="supplier")
    """'supplier' (paid vendor) or 'donor' (in-kind/grant source)."""
    contact_person: Mapped[str | None] = mapped_column(String(150))
    phone: Mapped[str | None] = mapped_column(String(30))
    email: Mapped[str | None] = mapped_column(String(255))
    address: Mapped[str | None] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
