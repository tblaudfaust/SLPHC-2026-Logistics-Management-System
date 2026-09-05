import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import get_db, require_permission
from app.models.procurement import Procurement
from app.models.supplier import Supplier
from app.models.user import User
from app.schemas.common import Page, PaginationParams
from app.schemas.procurement import ProcurementCreate, ProcurementRead, ProcurementUpdate
from app.services.pagination import paginate

router = APIRouter(prefix="/procurements", tags=["procurements"])


def _read_query():
    return select(Procurement).options(selectinload(Procurement.supplier))


@router.get("", response_model=Page[ProcurementRead])
def list_procurements(
    params: PaginationParams = Depends(),
    db: Session = Depends(get_db),
    _=Depends(require_permission("procurements.view")),
):
    stmt = _read_query()
    if params.search:
        stmt = stmt.where(Procurement.reference.ilike(f"%{params.search}%"))
    return paginate(db, stmt, Procurement, params, ProcurementRead)


@router.post("", response_model=ProcurementRead, status_code=status.HTTP_201_CREATED)
def create_procurement(
    payload: ProcurementCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("procurements.manage")),
):
    if payload.supplier_id and not db.get(Supplier, payload.supplier_id):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Unknown supplier_id.")
    if db.scalar(select(Procurement).where(Procurement.reference == payload.reference)):
        raise HTTPException(status.HTTP_409_CONFLICT, "A procurement with this reference already exists.")

    procurement = Procurement(created_by_id=current_user.id, **payload.model_dump())
    db.add(procurement)
    db.commit()
    return db.execute(_read_query().where(Procurement.id == procurement.id)).scalar_one()


@router.put("/{procurement_id}", response_model=ProcurementRead)
def update_procurement(
    procurement_id: uuid.UUID,
    payload: ProcurementUpdate,
    db: Session = Depends(get_db),
    _=Depends(require_permission("procurements.manage")),
):
    procurement = db.get(Procurement, procurement_id)
    if not procurement:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Procurement not found.")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(procurement, field, value)
    db.commit()
    return db.execute(_read_query().where(Procurement.id == procurement.id)).scalar_one()
