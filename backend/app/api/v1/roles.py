import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import client_ip, client_user_agent, get_db, require_permission, require_role
from app.models.rbac import Permission, Role
from app.models.user import User
from app.schemas.role import PermissionRead, RoleCreate, RoleRead, RoleUpdate
from app.services import audit_service

router = APIRouter(tags=["roles"])


@router.get("/permissions", response_model=list[PermissionRead])
def list_permissions(db: Session = Depends(get_db), _=Depends(require_permission("roles.view"))):
    return db.scalars(select(Permission).order_by(Permission.module, Permission.code)).all()


@router.get("/roles", response_model=list[RoleRead])
def list_roles(db: Session = Depends(get_db), _=Depends(require_permission("roles.view"))):
    return db.scalars(select(Role).order_by(Role.name)).all()


@router.post("/roles", response_model=RoleRead, status_code=status.HTTP_201_CREATED)
def create_role(
    payload: RoleCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("System Administrator")),
):
    if db.scalar(select(Role).where(Role.name == payload.name)):
        raise HTTPException(status.HTTP_409_CONFLICT, "A role with this name already exists.")

    permissions = (
        db.scalars(select(Permission).where(Permission.id.in_(payload.permission_ids))).all()
        if payload.permission_ids
        else []
    )
    role = Role(name=payload.name, description=payload.description, permissions=list(permissions))
    db.add(role)
    db.flush()
    audit_service.record(
        db, user_id=current_user.id, action="create", entity_type="role", entity_id=str(role.id),
        new_value={"name": role.name, "permissions": [p.code for p in permissions]},
        ip_address=client_ip(request), user_agent=client_user_agent(request),
    )
    db.commit()
    db.refresh(role)
    return role


@router.put("/roles/{role_id}", response_model=RoleRead)
def update_role(
    role_id: uuid.UUID,
    payload: RoleUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("System Administrator")),
):
    role = db.get(Role, role_id)
    if not role:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Role not found.")

    old_value = {"name": role.name, "permissions": [p.code for p in role.permissions]}
    if payload.name is not None:
        role.name = payload.name
    if payload.description is not None:
        role.description = payload.description
    if payload.permission_ids is not None:
        permissions = db.scalars(select(Permission).where(Permission.id.in_(payload.permission_ids))).all()
        role.permissions = list(permissions)

    audit_service.record(
        db, user_id=current_user.id, action="update", entity_type="role", entity_id=str(role.id),
        old_value=old_value,
        new_value={"name": role.name, "permissions": [p.code for p in role.permissions]},
        ip_address=client_ip(request), user_agent=client_user_agent(request),
    )
    db.commit()
    db.refresh(role)
    return role


@router.delete("/roles/{role_id}")
def delete_role(
    role_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("System Administrator")),
):
    role = db.get(Role, role_id)
    if not role:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Role not found.")
    if role.is_system:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "System-seeded roles cannot be deleted.")

    audit_service.record(
        db, user_id=current_user.id, action="delete", entity_type="role", entity_id=str(role.id),
        old_value={"name": role.name},
        ip_address=client_ip(request), user_agent=client_user_agent(request),
    )
    db.delete(role)
    db.commit()
    return {"detail": "Role deleted."}
