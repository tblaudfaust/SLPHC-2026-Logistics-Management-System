import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import client_ip, client_user_agent, get_db, require_permission
from app.models.location import Location
from app.models.user import User
from app.models.warehouse import Warehouse
from app.schemas.common import Page, PaginationParams
from app.schemas.warehouse import WarehouseCreate, WarehouseRead, WarehouseUpdate
from app.services import audit_service
from app.services.pagination import paginate
from app.services.warehouse_access_service import get_allowed_warehouse_ids

router = APIRouter(prefix="/warehouses", tags=["warehouses"])


@router.get("", response_model=Page[WarehouseRead])
def list_warehouses(
    params: PaginationParams = Depends(),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("warehouses.view")),
):
    stmt = select(Warehouse)
    if params.search:
        stmt = stmt.where(Warehouse.code.ilike(f"%{params.search}%"))
    allowed = get_allowed_warehouse_ids(current_user)
    if allowed is not None:
        stmt = stmt.where(Warehouse.location_id.in_(allowed))
    return paginate(db, stmt, Warehouse, params, WarehouseRead)


@router.post("", response_model=WarehouseRead, status_code=status.HTTP_201_CREATED)
def create_warehouse(
    payload: WarehouseCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("warehouses.manage")),
):
    if not db.get(Location, payload.location_id):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Unknown location_id.")
    if db.scalar(select(Warehouse).where(Warehouse.code == payload.code)):
        raise HTTPException(status.HTTP_409_CONFLICT, "A warehouse with this code already exists.")

    warehouse = Warehouse(**payload.model_dump())
    db.add(warehouse)
    db.flush()
    audit_service.record(
        db, user_id=current_user.id, action="create", entity_type="warehouse", entity_id=str(warehouse.id),
        new_value={"code": warehouse.code},
        ip_address=client_ip(request), user_agent=client_user_agent(request),
    )
    db.commit()
    db.refresh(warehouse)
    return warehouse


@router.put("/{warehouse_id}", response_model=WarehouseRead)
def update_warehouse(
    warehouse_id: uuid.UUID,
    payload: WarehouseUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("warehouses.manage")),
):
    warehouse = db.get(Warehouse, warehouse_id)
    if not warehouse:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Warehouse not found.")

    old_value = {"code": warehouse.code, "is_active": warehouse.is_active}
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(warehouse, field, value)

    audit_service.record(
        db, user_id=current_user.id, action="update", entity_type="warehouse", entity_id=str(warehouse.id),
        old_value=old_value, new_value={"code": warehouse.code, "is_active": warehouse.is_active},
        ip_address=client_ip(request), user_agent=client_user_agent(request),
    )
    db.commit()
    db.refresh(warehouse)
    return warehouse
