import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import client_ip, client_user_agent, get_db, require_permission
from app.models.supplier import Supplier
from app.models.user import User
from app.schemas.common import Page, PaginationParams
from app.schemas.supplier import SupplierCreate, SupplierRead, SupplierUpdate
from app.services import audit_service
from app.services.pagination import paginate

router = APIRouter(prefix="/suppliers", tags=["suppliers"])


@router.get("", response_model=Page[SupplierRead])
def list_suppliers(
    params: PaginationParams = Depends(),
    db: Session = Depends(get_db),
    _=Depends(require_permission("suppliers.view")),
):
    stmt = select(Supplier)
    if params.search:
        stmt = stmt.where(Supplier.name.ilike(f"%{params.search}%"))
    return paginate(db, stmt, Supplier, params, SupplierRead)


@router.post("", response_model=SupplierRead, status_code=status.HTTP_201_CREATED)
def create_supplier(
    payload: SupplierCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("suppliers.manage")),
):
    supplier = Supplier(**payload.model_dump())
    db.add(supplier)
    db.flush()
    audit_service.record(
        db, user_id=current_user.id, action="create", entity_type="supplier", entity_id=str(supplier.id),
        new_value={"name": supplier.name, "supplier_type": supplier.supplier_type},
        ip_address=client_ip(request), user_agent=client_user_agent(request),
    )
    db.commit()
    db.refresh(supplier)
    return supplier


@router.put("/{supplier_id}", response_model=SupplierRead)
def update_supplier(
    supplier_id: uuid.UUID,
    payload: SupplierUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("suppliers.manage")),
):
    supplier = db.get(Supplier, supplier_id)
    if not supplier:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Supplier not found.")

    old_value = {"name": supplier.name, "is_active": supplier.is_active}
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(supplier, field, value)

    audit_service.record(
        db, user_id=current_user.id, action="update", entity_type="supplier", entity_id=str(supplier.id),
        old_value=old_value, new_value={"name": supplier.name, "is_active": supplier.is_active},
        ip_address=client_ip(request), user_agent=client_user_agent(request),
    )
    db.commit()
    db.refresh(supplier)
    return supplier
