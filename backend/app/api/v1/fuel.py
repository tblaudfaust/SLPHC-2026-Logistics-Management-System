import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.api.deps import client_ip, client_user_agent, get_db, require_permission
from app.models.fuel import (
    CensusActivity,
    FuelAllocation,
    FuelApproval,
    FuelIssue,
    FuelRequest,
    FuelStation,
    FuelVoucher,
    Generator,
    Vehicle,
)
from app.models.user import User
from app.schemas.common import Page, PaginationParams
from app.schemas.fuel import (
    CensusActivityCreate,
    CensusActivityRead,
    FuelAllocationCreate,
    FuelAllocationRead,
    FuelAllocationUpdate,
    FuelApprovalDecision,
    FuelDashboardSummary,
    FuelIssueCreate,
    FuelIssueRead,
    FuelReceiptCreate,
    FuelReceiptRead,
    FuelReconciliationCreate,
    FuelReconciliationRead,
    FuelRequestCreate,
    FuelRequestDetailRead,
    FuelStationCreate,
    FuelStationRead,
    FuelStationUpdate,
    FuelStockAdjustmentCreate,
    FuelStockBalance,
    FuelStockReceiptCreate,
    FuelVoucherCreate,
    FuelVoucherRead,
    FuelVoucherStatusUpdate,
    FuelVoucherUpdate,
    GeneratorCreate,
    GeneratorRead,
    GeneratorUpdate,
    VehicleCreate,
    VehicleRead,
    VehicleUpdate,
)
from app.services import audit_service, fuel_service
from app.services.pagination import paginate

router = APIRouter(prefix="/fuel", tags=["fuel"])


# ---------------------------------------------------------------- dashboard

@router.get("/dashboard", response_model=FuelDashboardSummary)
def get_fuel_dashboard(db: Session = Depends(get_db), _=Depends(require_permission("fuel.view"))):
    return fuel_service.dashboard_summary(db)


# ---------------------------------------------------------------- census activities

@router.get("/activities", response_model=list[CensusActivityRead])
def list_activities(db: Session = Depends(get_db), _=Depends(require_permission("fuel.view"))):
    return db.scalars(select(CensusActivity).where(CensusActivity.is_active.is_(True)).order_by(CensusActivity.name)).all()


@router.post("/activities", response_model=CensusActivityRead, status_code=status.HTTP_201_CREATED)
def create_activity(
    payload: CensusActivityCreate, db: Session = Depends(get_db), _=Depends(require_permission("fuel.manage"))
):
    if db.scalar(select(CensusActivity).where(CensusActivity.name == payload.name)):
        raise HTTPException(status.HTTP_409_CONFLICT, "An activity with this name already exists.")
    activity = CensusActivity(**payload.model_dump())
    db.add(activity)
    db.commit()
    db.refresh(activity)
    return activity


# ---------------------------------------------------------------- vehicles

@router.get("/vehicles", response_model=Page[VehicleRead])
def list_vehicles(
    params: PaginationParams = Depends(), db: Session = Depends(get_db), _=Depends(require_permission("fuel.view"))
):
    stmt = select(Vehicle).options(selectinload(Vehicle.asset))
    return paginate(db, stmt, Vehicle, params, VehicleRead)


@router.post("/vehicles", response_model=VehicleRead, status_code=status.HTTP_201_CREATED)
def create_vehicle_endpoint(
    payload: VehicleCreate, db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("fuel.manage")),
):
    if db.scalar(select(Vehicle).where(Vehicle.registration_number == payload.registration_number)):
        raise HTTPException(status.HTTP_409_CONFLICT, "A vehicle with this registration number already exists.")
    vehicle = fuel_service.create_vehicle(db, payload=payload, performed_by_id=current_user.id)
    db.commit()
    db.refresh(vehicle)
    return vehicle


@router.put("/vehicles/{vehicle_id}", response_model=VehicleRead)
def update_vehicle_endpoint(
    vehicle_id: uuid.UUID, payload: VehicleUpdate, request: Request, db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("fuel.manage")),
):
    vehicle = db.execute(
        select(Vehicle).options(selectinload(Vehicle.asset)).where(Vehicle.id == vehicle_id)
    ).scalar_one_or_none()
    if not vehicle:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Vehicle not found.")
    if payload.registration_number and payload.registration_number != vehicle.registration_number:
        if db.scalar(select(Vehicle).where(Vehicle.registration_number == payload.registration_number)):
            raise HTTPException(status.HTTP_409_CONFLICT, "A vehicle with this registration number already exists.")
    fuel_service.update_vehicle(
        db, vehicle=vehicle, payload=payload, performed_by_id=current_user.id,
        ip_address=client_ip(request), user_agent=client_user_agent(request),
    )
    db.commit()
    db.refresh(vehicle)
    return vehicle


@router.delete("/vehicles/{vehicle_id}")
def delete_vehicle_endpoint(
    vehicle_id: uuid.UUID, request: Request, db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("fuel.manage")),
):
    vehicle = db.execute(
        select(Vehicle).options(selectinload(Vehicle.asset)).where(Vehicle.id == vehicle_id)
    ).scalar_one_or_none()
    if not vehicle:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Vehicle not found.")
    tag = vehicle.asset.asset_tag
    try:
        fuel_service.delete_vehicle_or_generator(
            db, extension=vehicle, entity_type="vehicle", performed_by_id=current_user.id,
            ip_address=client_ip(request), user_agent=client_user_agent(request),
        )
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "This vehicle has fuel requests or other history against it, so it can't be deleted — "
            "mark its asset Disposed instead to retire it.",
        )
    return {"detail": f"Vehicle {tag} deleted.", "hard_deleted": True}


# ---------------------------------------------------------------- generators

@router.get("/generators", response_model=Page[GeneratorRead])
def list_generators(
    params: PaginationParams = Depends(), db: Session = Depends(get_db), _=Depends(require_permission("fuel.view"))
):
    stmt = select(Generator).options(selectinload(Generator.asset))
    return paginate(db, stmt, Generator, params, GeneratorRead)


@router.post("/generators", response_model=GeneratorRead, status_code=status.HTTP_201_CREATED)
def create_generator_endpoint(
    payload: GeneratorCreate, db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("fuel.manage")),
):
    generator = fuel_service.create_generator(db, payload=payload, performed_by_id=current_user.id)
    db.commit()
    db.refresh(generator)
    return generator


@router.put("/generators/{generator_id}", response_model=GeneratorRead)
def update_generator_endpoint(
    generator_id: uuid.UUID, payload: GeneratorUpdate, request: Request, db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("fuel.manage")),
):
    generator = db.execute(
        select(Generator).options(selectinload(Generator.asset)).where(Generator.id == generator_id)
    ).scalar_one_or_none()
    if not generator:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Generator not found.")
    fuel_service.update_generator(
        db, generator=generator, payload=payload, performed_by_id=current_user.id,
        ip_address=client_ip(request), user_agent=client_user_agent(request),
    )
    db.commit()
    db.refresh(generator)
    return generator


@router.delete("/generators/{generator_id}")
def delete_generator_endpoint(
    generator_id: uuid.UUID, request: Request, db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("fuel.manage")),
):
    generator = db.execute(
        select(Generator).options(selectinload(Generator.asset)).where(Generator.id == generator_id)
    ).scalar_one_or_none()
    if not generator:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Generator not found.")
    tag = generator.asset.asset_tag
    try:
        fuel_service.delete_vehicle_or_generator(
            db, extension=generator, entity_type="generator", performed_by_id=current_user.id,
            ip_address=client_ip(request), user_agent=client_user_agent(request),
        )
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "This generator has fuel requests or other history against it, so it can't be deleted — "
            "mark its asset Disposed instead to retire it.",
        )
    return {"detail": f"Generator {tag} deleted.", "hard_deleted": True}


# ---------------------------------------------------------------- fuel stations

@router.get("/stations", response_model=list[FuelStationRead])
def list_stations(db: Session = Depends(get_db), _=Depends(require_permission("fuel.view"))):
    return db.scalars(
        select(FuelStation).options(selectinload(FuelStation.location)).where(FuelStation.is_active.is_(True))
    ).all()


@router.post("/stations", response_model=FuelStationRead, status_code=status.HTTP_201_CREATED)
def create_station(
    payload: FuelStationCreate, db: Session = Depends(get_db), _=Depends(require_permission("fuel.manage"))
):
    station = FuelStation(**payload.model_dump())
    db.add(station)
    db.commit()
    db.refresh(station)
    return station


@router.put("/stations/{station_id}", response_model=FuelStationRead)
def update_station(
    station_id: uuid.UUID, payload: FuelStationUpdate, request: Request, db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("fuel.manage")),
):
    station = db.get(FuelStation, station_id)
    if not station:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Fuel station not found.")

    changed = payload.model_dump(exclude_unset=True)
    old_value = {field: getattr(station, field) for field in changed}
    for field, value in changed.items():
        setattr(station, field, value)

    audit_service.record(
        db, user_id=current_user.id, action="update", entity_type="fuel_station", entity_id=str(station.id),
        old_value=audit_service.jsonable(old_value), new_value=audit_service.jsonable(changed),
        ip_address=client_ip(request), user_agent=client_user_agent(request),
    )
    db.commit()
    db.refresh(station)
    return station


@router.delete("/stations/{station_id}")
def delete_station(
    station_id: uuid.UUID, request: Request, db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("fuel.manage")),
):
    """Tries a real delete first; falls back to deactivating (is_active=False,
    already how list_stations filters) if fuel issues have been recorded
    against it — same delete-or-deactivate shape as delete_user."""
    station = db.get(FuelStation, station_id)
    if not station:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Fuel station not found.")
    name = station.name

    try:
        db.delete(station)
        db.flush()
        audit_service.record(
            db, user_id=current_user.id, action="delete", entity_type="fuel_station", entity_id=str(station_id),
            old_value={"name": name},
            ip_address=client_ip(request), user_agent=client_user_agent(request),
        )
        db.commit()
        return {"detail": f"Fuel station {name} deleted.", "hard_deleted": True}
    except IntegrityError:
        db.rollback()
        station = db.get(FuelStation, station_id)
        station.is_active = False
        audit_service.record(
            db, user_id=current_user.id, action="deactivate", entity_type="fuel_station", entity_id=str(station_id),
            old_value={"is_active": True}, new_value={"is_active": False},
            reason="Delete requested; station has fuel issuance history so it was deactivated instead.",
            ip_address=client_ip(request), user_agent=client_user_agent(request),
        )
        db.commit()
        return {
            "detail": f"Fuel station {name} has issuance history, so it was deactivated instead of deleted.",
            "hard_deleted": False,
        }


# ---------------------------------------------------------------- allocations

def _allocation_read(db: Session, allocation: FuelAllocation) -> dict:
    committed = fuel_service.allocation_committed_litres(db, allocation.id)
    data = FuelAllocationRead.model_validate(allocation).model_dump()
    data["litres_requested"] = committed["requested"]
    data["litres_approved"] = committed["approved"]
    data["litres_issued"] = committed["issued"]
    data["litres_remaining"] = float(allocation.allocated_litres) - committed["requested"]
    return data


@router.get("/allocations", response_model=list[FuelAllocationRead])
def list_allocations(db: Session = Depends(get_db), _=Depends(require_permission("fuel.view"))):
    allocations = db.scalars(
        select(FuelAllocation)
        .options(selectinload(FuelAllocation.region), selectinload(FuelAllocation.district), selectinload(FuelAllocation.activity))
        .order_by(FuelAllocation.created_at.desc())
    ).all()
    return [_allocation_read(db, a) for a in allocations]


@router.post("/allocations", response_model=FuelAllocationRead, status_code=status.HTTP_201_CREATED)
def create_allocation(
    payload: FuelAllocationCreate, db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("fuel.manage")),
):
    reference = fuel_service.generate_fuel_reference(db, "allocation")
    allocation = FuelAllocation(
        allocation_reference=reference, created_by_id=current_user.id, **payload.model_dump()
    )
    db.add(allocation)
    db.flush()
    audit_service.record(
        db, user_id=current_user.id, action="create", entity_type="fuel_allocation", entity_id=str(allocation.id),
        new_value={"reference": reference, "allocated_litres": payload.allocated_litres},
    )
    db.commit()
    db.refresh(allocation)
    return _allocation_read(db, allocation)


@router.put("/allocations/{allocation_id}", response_model=FuelAllocationRead)
def update_allocation_endpoint(
    allocation_id: uuid.UUID, payload: FuelAllocationUpdate, request: Request, db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("fuel.manage")),
):
    allocation = db.get(FuelAllocation, allocation_id)
    if not allocation:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Fuel allocation not found.")
    fuel_service.update_allocation(
        db, allocation=allocation, payload=payload, performed_by_id=current_user.id,
        ip_address=client_ip(request), user_agent=client_user_agent(request),
    )
    db.commit()
    db.refresh(allocation)
    return _allocation_read(db, allocation)


@router.delete("/allocations/{allocation_id}")
def delete_allocation(
    allocation_id: uuid.UUID, request: Request, db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("fuel.manage")),
):
    """Falls back to status=CLOSED instead of deleting if any fuel request
    has ever drawn against this allocation — checked explicitly rather than
    relying on IntegrityError, because FuelAllocation.requests is a
    bidirectional relationship (back_populates="allocation"): SQLAlchemy's
    default unit-of-work nulls out FuelRequest.allocation_id on delete
    *before* issuing the DELETE, specifically to avoid tripping the FK
    constraint, so the delete would otherwise silently succeed and erase
    the historical link instead of raising anything to catch."""
    allocation = db.get(FuelAllocation, allocation_id)
    if not allocation:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Fuel allocation not found.")
    reference = allocation.allocation_reference

    has_requests = db.scalar(select(FuelRequest.id).where(FuelRequest.allocation_id == allocation_id).limit(1))
    if has_requests:
        previous_status = allocation.status
        allocation.status = "CLOSED"
        audit_service.record(
            db, user_id=current_user.id, action="update", entity_type="fuel_allocation", entity_id=str(allocation_id),
            old_value={"status": previous_status}, new_value={"status": "CLOSED"},
            ip_address=client_ip(request), user_agent=client_user_agent(request),
            reason="Delete requested; allocation has requests against it so it was closed instead.",
        )
        db.commit()
        return {
            "detail": f"Allocation {reference} has requests against it, so it was closed instead of deleted.",
            "hard_deleted": False,
        }

    db.delete(allocation)
    audit_service.record(
        db, user_id=current_user.id, action="delete", entity_type="fuel_allocation", entity_id=str(allocation_id),
        old_value={"reference": reference},
        ip_address=client_ip(request), user_agent=client_user_agent(request),
    )
    db.commit()
    return {"detail": f"Allocation {reference} deleted.", "hard_deleted": True}


# ---------------------------------------------------------------- requests

def _request_read_query():
    return select(FuelRequest).options(
        selectinload(FuelRequest.requester), selectinload(FuelRequest.region), selectinload(FuelRequest.district),
        selectinload(FuelRequest.activity), selectinload(FuelRequest.vehicle).selectinload(Vehicle.asset),
        selectinload(FuelRequest.generator).selectinload(Generator.asset),
        selectinload(FuelRequest.approvals).selectinload(FuelApproval.approver),
        selectinload(FuelRequest.issue).selectinload(FuelIssue.issued_by),
    )


@router.get("/requests", response_model=Page[FuelRequestDetailRead])
def list_requests(
    params: PaginationParams = Depends(), status_filter: str | None = None,
    db: Session = Depends(get_db), _=Depends(require_permission("fuel.view")),
):
    stmt = _request_read_query()
    if status_filter:
        stmt = stmt.where(FuelRequest.status == status_filter)
    stmt = stmt.order_by(FuelRequest.created_at.desc())
    return paginate(db, stmt, FuelRequest, params, FuelRequestDetailRead)


@router.post("/requests", response_model=FuelRequestDetailRead, status_code=status.HTTP_201_CREATED)
def create_request_endpoint(
    payload: FuelRequestCreate, db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("fuel.request")),
):
    request = fuel_service.create_request(db, payload=payload, requester_id=current_user.id)
    db.commit()
    return db.execute(_request_read_query().where(FuelRequest.id == request.id)).scalar_one()


@router.get("/requests/{request_id}", response_model=FuelRequestDetailRead)
def get_request(request_id: uuid.UUID, db: Session = Depends(get_db), _=Depends(require_permission("fuel.view"))):
    request = db.execute(_request_read_query().where(FuelRequest.id == request_id)).scalar_one_or_none()
    if not request:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Fuel request not found.")
    return request


@router.post("/requests/{request_id}/review", response_model=FuelRequestDetailRead)
def review_request(
    request_id: uuid.UUID, payload: FuelApprovalDecision, db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("fuel.approve_review")),
):
    """Approval level 1 — the Director. Every request comes here first."""
    request = db.get(FuelRequest, request_id)
    if not request:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Fuel request not found.")
    fuel_service.decide_approval(db, request=request, approver_id=current_user.id, approval_level=1, payload=payload)
    db.commit()
    return db.execute(_request_read_query().where(FuelRequest.id == request_id)).scalar_one()


@router.post("/requests/{request_id}/approve", response_model=FuelRequestDetailRead)
def approve_request(
    request_id: uuid.UUID, payload: FuelApprovalDecision, db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("fuel.approve_final")),
):
    """Approval level 2 — final authorization by the Statistician General,
    or the Deputy Statistician General in their absence (both hold
    fuel.approve_final; whoever acts first is the recorded approver)."""
    request = db.get(FuelRequest, request_id)
    if not request:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Fuel request not found.")
    fuel_service.decide_approval(db, request=request, approver_id=current_user.id, approval_level=2, payload=payload)
    db.commit()
    return db.execute(_request_read_query().where(FuelRequest.id == request_id)).scalar_one()


# ---------------------------------------------------------------- issuance / receipt

def _issue_read_query():
    return select(FuelIssue).options(selectinload(FuelIssue.issued_by))


@router.get("/issues", response_model=Page[FuelIssueRead])
def list_issues(
    params: PaginationParams = Depends(), db: Session = Depends(get_db), _=Depends(require_permission("fuel.view"))
):
    stmt = _issue_read_query().order_by(FuelIssue.created_at.desc())
    return paginate(db, stmt, FuelIssue, params, FuelIssueRead)


@router.post("/requests/{request_id}/issue", response_model=FuelIssueRead, status_code=status.HTTP_201_CREATED)
def create_issue(
    request_id: uuid.UUID, payload: FuelIssueCreate, db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("fuel.issue")),
):
    request = db.get(FuelRequest, request_id)
    if not request:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Fuel request not found.")
    if payload.fuel_request_id != request_id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "fuel_request_id in body must match the URL.")
    issue = fuel_service.issue_fuel(db, request=request, payload=payload, issued_by_id=current_user.id)
    db.commit()
    return db.execute(_issue_read_query().where(FuelIssue.id == issue.id)).scalar_one()


@router.post("/issues/{issue_id}/receive", response_model=FuelReceiptRead, status_code=status.HTTP_201_CREATED)
def receive_issue(
    issue_id: uuid.UUID, payload: FuelReceiptCreate, db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("fuel.receive")),
):
    issue = db.get(FuelIssue, issue_id)
    if not issue:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Fuel issue not found.")
    receipt = fuel_service.acknowledge_receipt(db, issue=issue, payload=payload, receiver_id=current_user.id)
    db.commit()
    db.refresh(receipt)
    return receipt


@router.post("/issues/{issue_id}/reconcile", response_model=FuelReconciliationRead, status_code=status.HTTP_201_CREATED)
def reconcile_issue_endpoint(
    issue_id: uuid.UUID, payload: FuelReconciliationCreate, db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("fuel.reconcile")),
):
    issue = db.get(FuelIssue, issue_id)
    if not issue:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Fuel issue not found.")
    reconciliation = fuel_service.reconcile_issue(db, issue=issue, payload=payload, reconciled_by_id=current_user.id)
    db.commit()
    db.refresh(reconciliation)
    return reconciliation


# ---------------------------------------------------------------- vouchers

@router.get("/vouchers", response_model=list[FuelVoucherRead])
def list_vouchers(db: Session = Depends(get_db), _=Depends(require_permission("fuel.view"))):
    return db.scalars(
        select(FuelVoucher).options(selectinload(FuelVoucher.assigned_user)).order_by(FuelVoucher.created_at.desc())
    ).all()


@router.post("/vouchers", response_model=FuelVoucherRead, status_code=status.HTTP_201_CREATED)
def create_voucher(
    payload: FuelVoucherCreate, db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("fuel.manage")),
):
    if db.scalar(select(FuelVoucher).where(FuelVoucher.voucher_number == payload.voucher_number)):
        raise HTTPException(status.HTTP_409_CONFLICT, "A voucher with this number already exists.")
    voucher = FuelVoucher(
        created_by_id=current_user.id,
        status="ISSUED" if payload.assigned_user_id else "AVAILABLE",
        **payload.model_dump(),
    )
    db.add(voucher)
    db.flush()
    audit_service.record(
        db, user_id=current_user.id, action="create", entity_type="fuel_voucher", entity_id=str(voucher.id),
        new_value={"voucher_number": payload.voucher_number},
    )
    db.commit()
    db.refresh(voucher)
    return voucher


@router.put("/vouchers/{voucher_id}", response_model=FuelVoucherRead)
def update_voucher(
    voucher_id: uuid.UUID, payload: FuelVoucherUpdate, request: Request, db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("fuel.manage")),
):
    """Edits the voucher's own descriptive fields; status transitions stay on
    the dedicated /status endpoint below rather than being folded in here."""
    voucher = db.get(FuelVoucher, voucher_id)
    if not voucher:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Voucher not found.")
    if payload.voucher_number and payload.voucher_number != voucher.voucher_number:
        if db.scalar(select(FuelVoucher).where(FuelVoucher.voucher_number == payload.voucher_number)):
            raise HTTPException(status.HTTP_409_CONFLICT, "A voucher with this number already exists.")

    changed = payload.model_dump(exclude_unset=True)
    old_value = {field: getattr(voucher, field) for field in changed}
    for field, value in changed.items():
        setattr(voucher, field, value)

    audit_service.record(
        db, user_id=current_user.id, action="update", entity_type="fuel_voucher", entity_id=str(voucher.id),
        old_value=audit_service.jsonable(old_value), new_value=audit_service.jsonable(changed),
        ip_address=client_ip(request), user_agent=client_user_agent(request),
    )
    db.commit()
    db.refresh(voucher)
    return voucher


@router.delete("/vouchers/{voucher_id}")
def delete_voucher(
    voucher_id: uuid.UUID, request: Request, db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("fuel.manage")),
):
    voucher = db.get(FuelVoucher, voucher_id)
    if not voucher:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Voucher not found.")
    number = voucher.voucher_number
    db.delete(voucher)
    audit_service.record(
        db, user_id=current_user.id, action="delete", entity_type="fuel_voucher", entity_id=str(voucher_id),
        old_value={"voucher_number": number},
        ip_address=client_ip(request), user_agent=client_user_agent(request),
    )
    db.commit()
    return {"detail": f"Voucher {number} deleted.", "hard_deleted": True}


@router.put("/vouchers/{voucher_id}/status", response_model=FuelVoucherRead)
def update_voucher_status(
    voucher_id: uuid.UUID, payload: FuelVoucherStatusUpdate, db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("fuel.manage")),
):
    voucher = db.get(FuelVoucher, voucher_id)
    if not voucher:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Voucher not found.")
    previous_status = voucher.status
    voucher.status = payload.status
    if payload.date_redeemed:
        voucher.date_redeemed = payload.date_redeemed
    if payload.remarks:
        voucher.remarks = payload.remarks
    audit_service.record(
        db, user_id=current_user.id, action="update_status", entity_type="fuel_voucher", entity_id=str(voucher.id),
        old_value={"status": previous_status}, new_value={"status": payload.status},
    )
    db.commit()
    db.refresh(voucher)
    return voucher


# ---------------------------------------------------------------- stock

@router.get("/stock", response_model=list[FuelStockBalance])
def get_stock_balances(db: Session = Depends(get_db), _=Depends(require_permission("fuel.view"))):
    return fuel_service.get_fuel_stock_balances(db)


@router.post("/stock/receipts", status_code=status.HTTP_201_CREATED)
def create_stock_receipt(
    payload: FuelStockReceiptCreate, db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("fuel.manage")),
):
    fuel_service.record_stock_receipt(db, payload=payload, performed_by_id=current_user.id)
    db.commit()
    return {"detail": "Stock receipt recorded."}


@router.post("/stock/adjustments", status_code=status.HTTP_201_CREATED)
def create_stock_adjustment(
    payload: FuelStockAdjustmentCreate, db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("fuel.manage")),
):
    fuel_service.record_stock_adjustment(db, payload=payload, performed_by_id=current_user.id)
    db.commit()
    return {"detail": "Stock adjustment recorded."}
