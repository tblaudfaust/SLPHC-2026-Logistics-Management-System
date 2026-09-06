import secrets
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import delete, func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import client_ip, client_user_agent, get_db, require_permission, require_role
from app.core.security import hash_password, verify_password
from app.models.rbac import Permission, Role, UserPermissionOverride, user_roles
from app.models.user import RefreshToken, User
from app.models.warehouse import UserWarehouseAccess, Warehouse
from app.schemas.common import Page, PaginationParams
from app.schemas.user import (
    EffectivePermission,
    PasswordChange,
    PasswordResetResult,
    UserCreate,
    UserDeleteResult,
    UserPermissionOverridesUpdate,
    UserRead,
    UserUpdate,
    WarehouseAccessRead,
    WarehouseAccessUpdate,
)
from app.services import audit_service, notification_service
from app.services.pagination import paginate
from app.services.permission_service import effective_permission_codes

router = APIRouter(prefix="/users", tags=["users"])


@router.get("", response_model=Page[UserRead])
def list_users(
    params: PaginationParams = Depends(),
    db: Session = Depends(get_db),
    _=Depends(require_permission("users.view")),
):
    stmt = select(User)
    if params.search:
        like = f"%{params.search}%"
        stmt = stmt.where(
            (User.email.ilike(like)) | (User.first_name.ilike(like)) | (User.last_name.ilike(like))
        )
    return paginate(db, stmt, User, params, UserRead)


@router.post("", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def create_user(
    payload: UserCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("users.create")),
):
    if db.scalar(select(User).where(User.email == payload.email)):
        raise HTTPException(status.HTTP_409_CONFLICT, "A user with this email already exists.")

    roles = db.scalars(select(Role).where(Role.id.in_(payload.role_ids))).all() if payload.role_ids else []

    user = User(
        email=payload.email,
        hashed_password=hash_password(payload.password),
        first_name=payload.first_name,
        last_name=payload.last_name,
        phone=payload.phone,
        region_id=payload.region_id,
        district_id=payload.district_id,
        roles=list(roles),
    )
    db.add(user)
    db.flush()
    audit_service.record(
        db, user_id=current_user.id, action="create", entity_type="user", entity_id=str(user.id),
        new_value={"email": user.email, "roles": [r.name for r in roles]},
        ip_address=client_ip(request), user_agent=client_user_agent(request),
    )
    db.commit()
    db.refresh(user)
    return user


@router.get("/{user_id}", response_model=UserRead)
def get_user(
    user_id: uuid.UUID,
    db: Session = Depends(get_db),
    _=Depends(require_permission("users.view")),
):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found.")
    return user


@router.put("/{user_id}", response_model=UserRead)
def update_user(
    user_id: uuid.UUID,
    payload: UserUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("users.update")),
):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found.")

    if payload.role_ids is not None and "System Administrator" not in {r.name for r in current_user.roles}:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only a System Administrator can change a user's roles.")

    if payload.is_active is False and user_id == current_user.id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "You cannot disable your own account.")

    if payload.email is not None and payload.email != user.email:
        existing = db.scalar(select(User).where(User.email == payload.email, User.id != user_id))
        if existing:
            raise HTTPException(status.HTTP_409_CONFLICT, "A user with this email already exists.")

    old_value = {"is_active": user.is_active, "roles": [r.name for r in user.roles]}
    was_active = user.is_active
    data = payload.model_dump(exclude_unset=True, exclude={"role_ids"})
    for field, value in data.items():
        setattr(user, field, value)
    if payload.role_ids is not None:
        roles = db.scalars(select(Role).where(Role.id.in_(payload.role_ids))).all()
        user.roles = list(roles)

    if was_active and not user.is_active:
        _revoke_active_refresh_tokens(db, user_id)

    audit_service.record(
        db, user_id=current_user.id, action="update", entity_type="user", entity_id=str(user.id),
        old_value=old_value,
        new_value={"is_active": user.is_active, "roles": [r.name for r in user.roles]},
        ip_address=client_ip(request), user_agent=client_user_agent(request),
    )
    db.commit()
    db.refresh(user)
    return user


def _revoke_active_refresh_tokens(db: Session, user_id: uuid.UUID) -> None:
    db.execute(
        update(RefreshToken)
        .where(RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=datetime.now(timezone.utc))
    )


@router.post("/{user_id}/reset-password", response_model=PasswordResetResult)
def reset_user_password(
    user_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("System Administrator")),
):
    """Admin-initiated reset for a user who's locked out — as opposed to
    POST /users/me/change-password, which is self-service and requires
    knowing the current password. Deliberately blocked against targeting
    yourself: an admin resetting their own password would bypass that
    current-password check, so self-service stays the only path for your
    own account."""
    if user_id == current_user.id:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "Use Settings to change your own password."
        )
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found.")

    temporary_password = secrets.token_urlsafe(9)
    user.hashed_password = hash_password(temporary_password)
    user.failed_login_attempts = 0
    user.locked_until = None
    _revoke_active_refresh_tokens(db, user_id)

    audit_service.record(
        db, user_id=current_user.id, action="password_reset", entity_type="user", entity_id=str(user.id),
        reason="Password reset by administrator.",
        ip_address=client_ip(request), user_agent=client_user_agent(request),
    )
    notifications = notification_service.notify(
        db,
        event_type="user.password_reset",
        context={"first_name": user.first_name, "temporary_password": temporary_password},
        recipients=[user],
        related_entity_type="user",
        related_entity_id=str(user.id),
    )
    db.commit()
    notification_service.dispatch(notifications)
    return PasswordResetResult(
        temporary_password=temporary_password,
        detail=f"Password reset. A copy was emailed to {user.email}.",
    )


@router.delete("/{user_id}", response_model=UserDeleteResult)
def delete_user(
    user_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("System Administrator")),
):
    """Tries a real delete first; falls back to deactivation if the account
    has any historical activity (asset custody, inventory actions, audit
    trail, ...) since those foreign keys must never silently disappear or
    be nulled out — accountability records outlive the account that made
    them. Either way the account can no longer sign in."""
    if user_id == current_user.id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "You cannot delete your own account.")
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found.")

    if any(r.name == "System Administrator" for r in user.roles):
        remaining = db.scalar(
            select(func.count())
            .select_from(User)
            .join(user_roles, user_roles.c.user_id == User.id)
            .join(Role, Role.id == user_roles.c.role_id)
            .where(Role.name == "System Administrator", User.is_active.is_(True), User.id != user_id)
        )
        if not remaining:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST, "Cannot remove the last active System Administrator."
            )

    old_value = {"email": user.email, "roles": [r.name for r in user.roles]}
    entity_id = str(user.id)

    try:
        db.delete(user)
        db.flush()
    except IntegrityError:
        db.rollback()
        user = db.get(User, user_id)
        user.is_active = False
        _revoke_active_refresh_tokens(db, user_id)
        audit_service.record(
            db, user_id=current_user.id, action="deactivate", entity_type="user", entity_id=entity_id,
            old_value=old_value, new_value={"is_active": False},
            reason="Delete requested; account has historical activity so it was deactivated instead.",
            ip_address=client_ip(request), user_agent=client_user_agent(request),
        )
        db.commit()
        return UserDeleteResult(
            detail=(
                "This account has history (assets, transactions, or audit trail) tied to it, "
                "so it was deactivated instead of deleted — those records must stay intact."
            ),
            hard_deleted=False,
        )

    audit_service.record(
        db, user_id=current_user.id, action="delete", entity_type="user", entity_id=entity_id,
        old_value=old_value,
        ip_address=client_ip(request), user_agent=client_user_agent(request),
    )
    db.commit()
    return UserDeleteResult(detail="User account deleted.", hard_deleted=True)


def _build_effective_permissions(db: Session, user: User) -> list[EffectivePermission]:
    role_codes = {p.code for role in user.roles for p in role.permissions}
    overrides_by_permission_id = {o.permission_id: o.effect for o in user.permission_overrides}
    effective_codes = effective_permission_codes(user)

    all_permissions = db.scalars(select(Permission).order_by(Permission.module, Permission.code)).all()
    return [
        EffectivePermission(
            id=perm.id,
            code=perm.code,
            module=perm.module,
            description=perm.description,
            from_role=perm.code in role_codes,
            override=overrides_by_permission_id.get(perm.id),
            effective=perm.code in effective_codes,
        )
        for perm in all_permissions
    ]


@router.get("/{user_id}/permissions", response_model=list[EffectivePermission])
def get_user_permissions(
    user_id: uuid.UUID,
    db: Session = Depends(get_db),
    _=Depends(require_permission("users.view")),
):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found.")
    return _build_effective_permissions(db, user)


@router.put("/{user_id}/permissions", response_model=list[EffectivePermission])
def update_user_permissions(
    user_id: uuid.UUID,
    payload: UserPermissionOverridesUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("System Administrator")),
):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found.")

    permission_ids = {entry.permission_id for entry in payload.overrides}
    known_ids = set(db.scalars(select(Permission.id).where(Permission.id.in_(permission_ids))).all())
    unknown_ids = permission_ids - known_ids
    if unknown_ids:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Unknown permission id(s): {unknown_ids}")

    old_overrides = {str(o.permission_id): o.effect for o in user.permission_overrides}

    db.execute(delete(UserPermissionOverride).where(UserPermissionOverride.user_id == user_id))
    for entry in payload.overrides:
        db.add(UserPermissionOverride(user_id=user_id, permission_id=entry.permission_id, effect=entry.effect))
    db.flush()
    db.refresh(user)

    new_overrides = {str(entry.permission_id): entry.effect for entry in payload.overrides}
    audit_service.record(
        db, user_id=current_user.id, action="update_permissions", entity_type="user", entity_id=str(user.id),
        old_value={"overrides": old_overrides}, new_value={"overrides": new_overrides},
        ip_address=client_ip(request), user_agent=client_user_agent(request),
    )
    db.commit()
    db.refresh(user)
    return _build_effective_permissions(db, user)


def _warehouse_access_read(user: User) -> list[WarehouseAccessRead]:
    return [WarehouseAccessRead(id=a.warehouse_id, name=a.warehouse.name) for a in user.warehouse_access]


@router.get("/{user_id}/warehouses", response_model=list[WarehouseAccessRead])
def get_user_warehouse_access(
    user_id: uuid.UUID,
    db: Session = Depends(get_db),
    _=Depends(require_permission("users.view")),
):
    """Empty list means unrestricted (national) access — the common case."""
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found.")
    return _warehouse_access_read(user)


@router.put("/{user_id}/warehouses", response_model=list[WarehouseAccessRead])
def update_user_warehouse_access(
    user_id: uuid.UUID,
    payload: WarehouseAccessUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("System Administrator")),
):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found.")

    if payload.warehouse_ids:
        valid_ids = set(
            db.scalars(select(Warehouse.location_id).where(Warehouse.location_id.in_(payload.warehouse_ids))).all()
        )
        unknown_ids = set(payload.warehouse_ids) - valid_ids
        if unknown_ids:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Unknown warehouse id(s): {unknown_ids}")

    old_ids = [str(a.warehouse_id) for a in user.warehouse_access]

    db.execute(delete(UserWarehouseAccess).where(UserWarehouseAccess.user_id == user_id))
    for warehouse_id in payload.warehouse_ids:
        db.add(UserWarehouseAccess(user_id=user_id, warehouse_id=warehouse_id))
    db.flush()
    db.refresh(user)

    audit_service.record(
        db, user_id=current_user.id, action="update_warehouse_access", entity_type="user", entity_id=str(user.id),
        old_value={"warehouse_ids": old_ids}, new_value={"warehouse_ids": [str(w) for w in payload.warehouse_ids]},
        ip_address=client_ip(request), user_agent=client_user_agent(request),
    )
    db.commit()
    db.refresh(user)
    return _warehouse_access_read(user)


@router.post("/me/change-password")
def change_my_password(
    payload: PasswordChange,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("users.view")),
):
    if not verify_password(payload.current_password, current_user.hashed_password):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Current password is incorrect.")

    current_user.hashed_password = hash_password(payload.new_password)
    audit_service.record(
        db, user_id=current_user.id, action="password_change", entity_type="user",
        entity_id=str(current_user.id),
        ip_address=client_ip(request), user_agent=client_user_agent(request),
    )
    db.commit()
    return {"detail": "Password updated."}
