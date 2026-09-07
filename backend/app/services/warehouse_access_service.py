import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.location import District, Location
from app.models.user import User


def geography_location_ids(db: Session, user: User) -> set[uuid.UUID] | None:
    """Derives allowed locations from the user's own geography scope (brief
    §4: 'see only the functions and geography required') — a district-
    scoped user gets that district's locations, a region-scoped user gets
    every location in every district of that region, plus any location
    attached to the region directly (a Regional Store, which has
    region_id set and district_id null). Returns None for a national user
    (no region_id or district_id) — unrestricted, same as today."""
    if user.district_id:
        return set(db.scalars(select(Location.id).where(Location.district_id == user.district_id)).all())
    if user.region_id:
        district_ids = select(District.id).where(District.region_id == user.region_id)
        return set(
            db.scalars(
                select(Location.id).where(
                    (Location.region_id == user.region_id) | (Location.district_id.in_(district_ids))
                )
            ).all()
        )
    return None


def get_allowed_warehouse_ids(db: Session, user: User) -> set[uuid.UUID] | None:
    """None means unrestricted (national) access. Otherwise, the explicit
    per-warehouse assignment (UserWarehouseAccess) wins when present — it's
    a deliberately opt-in, more specific override (e.g. a national officer
    given access to one particular warehouse outside their usual scope).
    With no explicit assignment, falls back to the user's region/district
    geography scope. A non-None result is always non-empty by construction."""
    explicit = {a.warehouse_id for a in user.warehouse_access}
    if explicit:
        return explicit
    return geography_location_ids(db, user)


def check_warehouse_access(db: Session, user: User, warehouse_id: uuid.UUID) -> None:
    """Raises 403 if this user is scoped (explicitly or by geography) and
    `warehouse_id` isn't in their allowed set. Call before any inventory
    action that targets a single warehouse (receipt, adjustment, transfer
    dispatch/receive, stock count)."""
    allowed = get_allowed_warehouse_ids(db, user)
    if allowed is not None and warehouse_id not in allowed:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "You do not have access to this warehouse.")


def check_district_access(db: Session, user: User, district_id: uuid.UUID) -> None:
    """Raises 403 if this user's own geography scope doesn't cover
    `district_id` — used by the Dashboard's district switcher so a
    district- or region-scoped user can't page through districts outside
    their own assignment just by editing the query string."""
    if user.district_id:
        if user.district_id != district_id:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "You do not have access to this district.")
        return
    if user.region_id:
        district = db.get(District, district_id)
        if not district or district.region_id != user.region_id:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "You do not have access to this district.")
