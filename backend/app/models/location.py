import uuid

from sqlalchemy import Boolean, ForeignKey, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.mixins import TimestampMixin, UUIDPKMixin


class Region(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "regions"

    name: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)

    districts: Mapped[list["District"]] = relationship(back_populates="region")


class District(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "districts"

    region_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("regions.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)

    region: Mapped["Region"] = relationship(back_populates="districts")
    chiefdoms: Mapped[list["Chiefdom"]] = relationship(back_populates="district")


class Chiefdom(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "chiefdoms"

    district_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("districts.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)

    district: Mapped["District"] = relationship(back_populates="chiefdoms")
    sections: Mapped[list["Section"]] = relationship(back_populates="chiefdom")


class Section(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "sections"

    chiefdom_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("chiefdoms.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)

    chiefdom: Mapped["Chiefdom"] = relationship(back_populates="sections")
    supervisory_areas: Mapped[list["SupervisoryArea"]] = relationship(back_populates="section")


class SupervisoryArea(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "supervisory_areas"

    section_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("sections.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)

    section: Mapped["Section"] = relationship(back_populates="supervisory_areas")
    enumeration_areas: Mapped[list["EnumerationArea"]] = relationship(back_populates="supervisory_area")


class EnumerationArea(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "enumeration_areas"

    supervisory_area_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("supervisory_areas.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)

    supervisory_area: Mapped["SupervisoryArea"] = relationship(back_populates="enumeration_areas")


class LocationType(Base, UUIDPKMixin, TimestampMixin):
    """Database-driven so admins can add new facility types without a code change
    (brief §3: 'Asset categories must be database-driven'; same principle applies here)."""

    __tablename__ = "location_types"

    name: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(String(255))

    locations: Mapped[list["Location"]] = relationship(back_populates="location_type")


class Location(Base, UUIDPKMixin, TimestampMixin):
    """A logistics facility: central store, district office, training centre, field office, etc."""

    __tablename__ = "locations"

    location_type_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("location_types.id"), nullable=False
    )
    region_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("regions.id"), nullable=True)
    """For a regional-level facility with no single district (e.g. a
    regional warehouse). A district-level facility sets district_id instead
    and derives its region via district.region_id — a location doesn't need
    both set."""
    district_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("districts.id"), nullable=True
    )
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    address: Mapped[str | None] = mapped_column(String(255))
    gps_latitude: Mapped[float | None] = mapped_column(Numeric(9, 6))
    gps_longitude: Mapped[float | None] = mapped_column(Numeric(9, 6))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    location_type: Mapped["LocationType"] = relationship(back_populates="locations")
    region: Mapped["Region | None"] = relationship()
    district: Mapped["District | None"] = relationship()
    warehouse: Mapped["Warehouse"] = relationship(back_populates="location", uselist=False)
