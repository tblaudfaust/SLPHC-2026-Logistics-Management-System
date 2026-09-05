import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.api.deps import client_ip, client_user_agent, get_db, require_permission, require_role
from app.core.security import hash_password, verify_password
from app.models.rbac import Permission, Role, UserPermissionOverride
from app.models.user import User
from app.models.warehouse import UserWarehouseAccess, Warehouse
from app.schemas.common import Page, PaginationParams
from app.schemas.user import (
    EffectivePermission,
    PasswordChange,
    UserCreate,
    UserPermissionOverridesUpdate,
    UserRead,
    UserUpdate,
    WarehouseAccessRead,
    WarehouseAccessUpdate,
)
from app.services import audit_service
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

    if payload.email is not None and payload.email != user.email:
        existing = db.scalar(select(User).where(User.email == payload.email, User.id != user_id))
        if existing:
            raise HTTPException(status.HTTP_409_CONFLICT, "A user with this email already exists.")

    old_value = {"is_active": user.is_active, "roles": [r.name for r in user.roles]}
    data = payload.model_dump(exclude_unset=True, exclude={"role_ids"})
    for field, value in data.items():
        setattr(user, field, value)
    if payload.role_ids is not None:
        roles = db.scalars(select(Role).where(Role.id.in_(payload.role_ids))).all()
        user.roles = list(roles)

    audit_service.record(
        db, user_id=current_user.id, action="update", entity_type="user", entity_id=str(user.id),
        old_value=old_value,
        new_value={"is_active": user.is_active, "roles": [r.name for r in user.roles]},
        ip_address=client_ip(request), user_agent=client_user_agent(request),
    )
    db.commit()
    db.refresh(user)
    return user


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
