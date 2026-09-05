import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_permission
from app.models.supplier import Supplier
from app.schemas.common import Page, PaginationParams
from app.schemas.supplier import SupplierCreate, SupplierRead, SupplierUpdate
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
    db: Session = Depends(get_db),
    _=Depends(require_permission("suppliers.manage")),
):
    supplier = Supplier(**payload.model_dump())
    db.add(supplier)
    db.commit()
    db.refresh(supplier)
    return supplier


@router.put("/{supplier_id}", response_model=SupplierRead)
def update_supplier(
    supplier_id: uuid.UUID,
    payload: SupplierUpdate,
    db: Session = Depends(get_db),
    _=Depends(require_permission("suppliers.manage")),
):
    supplier = db.get(Supplier, supplier_id)
    if not supplier:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Supplier not found.")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(supplier, field, value)
    db.commit()
    db.refresh(supplier)
    return supplier
