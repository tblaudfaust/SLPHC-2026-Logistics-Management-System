import uuid

from sqlalchemy import Column, ForeignKey, String, Table, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.mixins import TimestampMixin, UUIDPKMixin

role_permissions = Table(
    "role_permissions",
    Base.metadata,
    Column("role_id", UUID(as_uuid=True), ForeignKey("roles.id"), primary_key=True),
    Column("permission_id", UUID(as_uuid=True), ForeignKey("permissions.id"), primary_key=True),
)

user_roles = Table(
    "user_roles",
    Base.metadata,
    Column("user_id", UUID(as_uuid=True), ForeignKey("users.id"), primary_key=True),
    Column("role_id", UUID(as_uuid=True), ForeignKey("roles.id"), primary_key=True),
)


class Role(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "roles"

    name: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(String(255))
    is_system: Mapped[bool] = mapped_column(default=False, nullable=False)
    """System-seeded roles (brief §4's 14 roles) can be renamed but not deleted."""

    permissions: Mapped[list["Permission"]] = relationship(
        secondary=role_permissions, back_populates="roles"
    )
    users: Mapped[list["User"]] = relationship(secondary=user_roles, back_populates="roles")


class Permission(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "permissions"

    code: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    """Dotted form, e.g. 'users.create', 'assets.dispatch'."""
    module: Mapped[str] = mapped_column(String(50), nullable=False)
    description: Mapped[str | None] = mapped_column(String(255))

    roles: Mapped[list["Role"]] = relationship(secondary=role_permissions, back_populates="permissions")


OVERRIDE_EFFECTS = ["GRANT", "REVOKE"]


class UserPermissionOverride(Base, UUIDPKMixin, TimestampMixin):
    """A single user's exception to their role-derived permissions (brief-driven
    request: "allow to add or remove rights" per user, not just per role).
    GRANT adds a permission the user's roles don't carry; REVOKE removes one
    they otherwise would have. See app.services.permission_service for how
    these combine with role permissions into the effective set."""

    __tablename__ = "user_permission_overrides"
    __table_args__ = (UniqueConstraint("user_id", "permission_id", name="uq_user_permission_override"),)

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    permission_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("permissions.id"), nullable=False)
    effect: Mapped[str] = mapped_column(String(6), nullable=False)

    user: Mapped["User"] = relationship(foreign_keys=[user_id])
    permission: Mapped["Permission"] = relationship()
