import uuid

from fastapi import HTTPException, status

from app.models.user import User


def get_allowed_warehouse_ids(user: User) -> set[uuid.UUID] | None:
    """None means unrestricted (national) access — the common case today,
    since this is an opt-in scope. A non-None result is always non-empty by
    construction (a row only exists if a warehouse was actually assigned)."""
    ids = {a.warehouse_id for a in user.warehouse_access}
    return ids or None


def check_warehouse_access(user: User, warehouse_id: uuid.UUID) -> None:
    """Raises 403 if this user is scoped to specific warehouse(s) and
    `warehouse_id` isn't one of them. Call before any inventory action that
    targets a single warehouse (receipt, adjustment, transfer dispatch/
    receive, stock count)."""
    allowed = get_allowed_warehouse_ids(user)
    if allowed is not None and warehouse_id not in allowed:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "You do not have access to this warehouse.")
