import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_permission
from app.models.location import District
from app.models.starlink import (
    FieldTeam,
    FundingSource,
    HardToReachArea,
    StarlinkCheckin,
    StarlinkFault,
    StarlinkInstallation,
    StarlinkKit,
    StarlinkMovement,
    StarlinkSubscription,
    StarlinkTeamAssignment,
)
from app.models.user import User
from app.schemas.common import Page, PaginationParams
from app.schemas.starlink import (
    FieldTeamCreate,
    FieldTeamRead,
    FieldTeamUpdate,
    FundingSourceCreate,
    FundingSourceRead,
    HardToReachAreaCreate,
    HardToReachAreaRead,
    HardToReachAreaUpdate,
    StarlinkCheckinCreate,
    StarlinkCheckinRead,
    StarlinkDashboardSummary,
    StarlinkFaultCreate,
    StarlinkFaultRead,
    StarlinkFaultUpdate,
    StarlinkInstallationCreate,
    StarlinkInstallationRead,
    StarlinkKitCreate,
    StarlinkKitRead,
    StarlinkKitUpdate,
    StarlinkMovementCreate,
    StarlinkMovementRead,
    StarlinkPaymentCreate,
    StarlinkPaymentRead,
    StarlinkReturnCreate,
    StarlinkReturnRead,
    StarlinkSubscriptionCreate,
    StarlinkSubscriptionRead,
    StarlinkTeamAssignmentCreate,
    StarlinkTeamAssignmentRead,
)
from app.services import audit_service, starlink_service
from app.services.pagination import paginate

router = APIRouter(prefix="/starlink", tags=["starlink"])


def _get_kit(db: Session, kit_id: uuid.UUID) -> StarlinkKit:
    kit = db.get(StarlinkKit, kit_id)
    if not kit:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Starlink kit not found.")
    return kit


# ---------------------------------------------------------------- dashboard

@router.get("/dashboard", response_model=StarlinkDashboardSummary)
def get_dashboard(db: Session = Depends(get_db), _=Depends(require_permission("starlink.view"))):
    return starlink_service.dashboard_summary(db)


# ---------------------------------------------------------------- field teams

@router.get("/field-teams", response_model=list[FieldTeamRead])
def list_field_teams(
    region_id: uuid.UUID | None = None,
    district_id: uuid.UUID | None = None,
    db: Session = Depends(get_db),
    _=Depends(require_permission("starlink.view")),
):
    stmt = select(FieldTeam).where(FieldTeam.is_active.is_(True))
    if region_id:
        stmt = stmt.where(FieldTeam.region_id == region_id)
    if district_id:
        stmt = stmt.where(FieldTeam.district_id == district_id)
    return db.scalars(stmt.order_by(FieldTeam.name)).all()


@router.post("/field-teams", response_model=FieldTeamRead, status_code=status.HTTP_201_CREATED)
def create_field_team(
    payload: FieldTeamCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("starlink.manage")),
):
    code = starlink_service.next_sequence_code(db, FieldTeam, FieldTeam.team_code, "FT")
    team = FieldTeam(team_code=code, **payload.model_dump())
    db.add(team)
    db.flush()

    audit_service.record(
        db, user_id=current_user.id, action="create", entity_type="field_team", entity_id=str(team.id),
        new_value={"team_code": code, "name": team.name},
    )
    db.commit()
    db.refresh(team)
    return team


@router.put("/field-teams/{team_id}", response_model=FieldTeamRead)
def update_field_team(
    team_id: uuid.UUID,
    payload: FieldTeamUpdate,
    db: Session = Depends(get_db),
    _=Depends(require_permission("starlink.manage")),
):
    team = db.get(FieldTeam, team_id)
    if not team:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Field team not found.")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(team, field, value)
    db.commit()
    db.refresh(team)
    return team


# ---------------------------------------------------------------- funding sources

@router.get("/funding-sources", response_model=list[FundingSourceRead])
def list_funding_sources(db: Session = Depends(get_db), _=Depends(require_permission("starlink.view"))):
    return db.scalars(select(FundingSource).where(FundingSource.is_active.is_(True)).order_by(FundingSource.name)).all()


@router.post("/funding-sources", response_model=FundingSourceRead, status_code=status.HTTP_201_CREATED)
def create_funding_source(
    payload: FundingSourceCreate,
    db: Session = Depends(get_db),
    _=Depends(require_permission("starlink.manage")),
):
    if db.scalar(select(FundingSource).where(FundingSource.name == payload.name)):
        raise HTTPException(status.HTTP_409_CONFLICT, "A funding source with this name already exists.")
    source = FundingSource(**payload.model_dump())
    db.add(source)
    db.commit()
    db.refresh(source)
    return source


# ---------------------------------------------------------------- hard-to-reach areas

@router.get("/hard-to-reach-areas", response_model=list[HardToReachAreaRead])
def list_hard_to_reach_areas(
    district_id: uuid.UUID | None = None,
    starlink_required: bool | None = None,
    db: Session = Depends(get_db),
    _=Depends(require_permission("starlink.view")),
):
    stmt = select(HardToReachArea)
    if district_id:
        stmt = stmt.where(HardToReachArea.district_id == district_id)
    if starlink_required is not None:
        stmt = stmt.where(HardToReachArea.starlink_required.is_(starlink_required))
    return db.scalars(stmt.order_by(HardToReachArea.name)).all()


@router.post("/hard-to-reach-areas", response_model=HardToReachAreaRead, status_code=status.HTTP_201_CREATED)
def create_hard_to_reach_area(
    payload: HardToReachAreaCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("starlink.manage")),
):
    if not db.get(District, payload.district_id):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Unknown district_id.")
    area = HardToReachArea(**payload.model_dump())
    db.add(area)
    db.flush()

    audit_service.record(
        db, user_id=current_user.id, action="create", entity_type="hard_to_reach_area", entity_id=str(area.id),
        new_value={"name": area.name, "classification": area.classification},
    )
    db.commit()
    db.refresh(area)
    return area


@router.put("/hard-to-reach-areas/{area_id}", response_model=HardToReachAreaRead)
def update_hard_to_reach_area(
    area_id: uuid.UUID,
    payload: HardToReachAreaUpdate,
    db: Session = Depends(get_db),
    _=Depends(require_permission("starlink.manage")),
):
    area = db.get(HardToReachArea, area_id)
    if not area:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Hard-to-reach area not found.")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(area, field, value)
    db.commit()
    db.refresh(area)
    return area


# ---------------------------------------------------------------- kits

@router.get("", response_model=Page[StarlinkKitRead])
def list_kits(
    params: PaginationParams = Depends(),
    kit_type: str | None = None,
    operational_status: str | None = None,
    subscription_status: str | None = None,
    db: Session = Depends(get_db),
    _=Depends(require_permission("starlink.view")),
):
    stmt = select(StarlinkKit).join(StarlinkKit.asset)
    if kit_type:
        stmt = stmt.where(StarlinkKit.kit_type == kit_type)
    if operational_status:
        stmt = stmt.where(StarlinkKit.operational_status == operational_status)
    if subscription_status:
        stmt = stmt.where(StarlinkKit.subscription_status == subscription_status)
    if params.search:
        from app.models.asset import Asset

        like = f"%{params.search}%"
        stmt = stmt.where((Asset.asset_tag.ilike(like)) | (Asset.serial_number.ilike(like)) | (StarlinkKit.terminal_id.ilike(like)))
    return paginate(db, stmt, StarlinkKit, params, StarlinkKitRead)


@router.post("", response_model=StarlinkKitRead, status_code=status.HTTP_201_CREATED)
def create_kit(
    payload: StarlinkKitCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("starlink.manage")),
):
    if payload.kit_type not in ("FIXED", "ROAMING"):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "kit_type must be FIXED or ROAMING.")
    kit = starlink_service.create_kit(db, payload=payload, performed_by_id=current_user.id)
    db.commit()
    db.refresh(kit)
    return kit


@router.get("/{kit_id}", response_model=StarlinkKitRead)
def get_kit(kit_id: uuid.UUID, db: Session = Depends(get_db), _=Depends(require_permission("starlink.view"))):
    return _get_kit(db, kit_id)


@router.put("/{kit_id}", response_model=StarlinkKitRead)
def update_kit(
    kit_id: uuid.UUID,
    payload: StarlinkKitUpdate,
    db: Session = Depends(get_db),
    _=Depends(require_permission("starlink.manage")),
):
    kit = _get_kit(db, kit_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(kit, field, value)
    db.commit()
    db.refresh(kit)
    return kit


# ---------------------------------------------------------------- installations

@router.get("/{kit_id}/installations", response_model=list[StarlinkInstallationRead])
def list_installations(kit_id: uuid.UUID, db: Session = Depends(get_db), _=Depends(require_permission("starlink.view"))):
    return db.scalars(
        select(StarlinkInstallation).where(StarlinkInstallation.kit_id == kit_id).order_by(StarlinkInstallation.installation_date.desc())
    ).all()


@router.post("/{kit_id}/installations", response_model=StarlinkInstallationRead, status_code=status.HTTP_201_CREATED)
def create_installation(
    kit_id: uuid.UUID,
    payload: StarlinkInstallationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("starlink.install")),
):
    kit = _get_kit(db, kit_id)
    installation = starlink_service.record_installation(db, kit, payload, current_user.id)
    db.commit()
    db.refresh(installation)
    return installation


# ---------------------------------------------------------------- subscriptions

@router.get("/{kit_id}/subscriptions", response_model=list[StarlinkSubscriptionRead])
def list_subscriptions(kit_id: uuid.UUID, db: Session = Depends(get_db), _=Depends(require_permission("starlink.view"))):
    return db.scalars(
        select(StarlinkSubscription).where(StarlinkSubscription.kit_id == kit_id).order_by(StarlinkSubscription.created_at.desc())
    ).all()


@router.post("/{kit_id}/subscriptions", response_model=StarlinkSubscriptionRead, status_code=status.HTTP_201_CREATED)
def create_subscription(
    kit_id: uuid.UUID,
    payload: StarlinkSubscriptionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("starlink.subscription")),
):
    kit = _get_kit(db, kit_id)
    subscription = starlink_service.create_subscription(db, kit, payload, current_user.id)
    db.commit()
    db.refresh(subscription)
    return subscription


@router.post("/subscriptions/{subscription_id}/payments", response_model=StarlinkPaymentRead, status_code=status.HTTP_201_CREATED)
def create_payment(
    subscription_id: uuid.UUID,
    payload: StarlinkPaymentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("starlink.subscription")),
):
    subscription = db.get(StarlinkSubscription, subscription_id)
    if not subscription:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Subscription not found.")
    payment = starlink_service.record_payment(db, subscription, payload, current_user.id)
    db.commit()
    db.refresh(payment)
    return payment


# ---------------------------------------------------------------- field team assignment

@router.get("/{kit_id}/assignments", response_model=list[StarlinkTeamAssignmentRead])
def list_assignments(kit_id: uuid.UUID, db: Session = Depends(get_db), _=Depends(require_permission("starlink.view"))):
    return db.scalars(
        select(StarlinkTeamAssignment).where(StarlinkTeamAssignment.kit_id == kit_id).order_by(StarlinkTeamAssignment.created_at.desc())
    ).all()


@router.post("/{kit_id}/assignments", response_model=StarlinkTeamAssignmentRead, status_code=status.HTTP_201_CREATED)
def create_assignment(
    kit_id: uuid.UUID,
    payload: StarlinkTeamAssignmentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("starlink.assign")),
):
    kit = _get_kit(db, kit_id)
    assignment = starlink_service.assign_to_team(db, kit, payload, current_user)
    db.commit()
    db.refresh(assignment)
    return assignment


@router.post("/assignments/{assignment_id}/return", response_model=StarlinkReturnRead)
def return_assignment(
    assignment_id: uuid.UUID,
    payload: StarlinkReturnCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("starlink.assign")),
):
    assignment = db.get(StarlinkTeamAssignment, assignment_id)
    if not assignment:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Assignment not found.")
    ret = starlink_service.return_from_team(db, assignment, payload, current_user)
    db.commit()
    db.refresh(ret)
    return ret


# ---------------------------------------------------------------- movements

@router.get("/{kit_id}/movements", response_model=list[StarlinkMovementRead])
def list_movements(kit_id: uuid.UUID, db: Session = Depends(get_db), _=Depends(require_permission("starlink.view"))):
    return db.scalars(
        select(StarlinkMovement).where(StarlinkMovement.kit_id == kit_id).order_by(StarlinkMovement.created_at.desc())
    ).all()


@router.post("/{kit_id}/movements", response_model=StarlinkMovementRead, status_code=status.HTTP_201_CREATED)
def create_movement(
    kit_id: uuid.UUID,
    payload: StarlinkMovementCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("starlink.assign")),
):
    kit = _get_kit(db, kit_id)
    movement = starlink_service.record_movement(db, kit, payload, current_user)
    db.commit()
    db.refresh(movement)
    return movement


# ---------------------------------------------------------------- check-ins

@router.get("/{kit_id}/checkins", response_model=list[StarlinkCheckinRead])
def list_checkins(kit_id: uuid.UUID, db: Session = Depends(get_db), _=Depends(require_permission("starlink.view"))):
    return db.scalars(
        select(StarlinkCheckin).where(StarlinkCheckin.kit_id == kit_id).order_by(StarlinkCheckin.checkin_at.desc())
    ).all()


@router.post("/checkins", response_model=StarlinkCheckinRead, status_code=status.HTTP_201_CREATED)
def create_checkin(
    payload: StarlinkCheckinCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("starlink.checkin")),
):
    from app.services import notification_service

    checkin, notifications = starlink_service.record_checkin(db, payload, current_user)
    db.commit()
    db.refresh(checkin)
    notification_service.dispatch(notifications)
    return checkin


# ---------------------------------------------------------------- faults / maintenance

@router.get("/faults", response_model=list[StarlinkFaultRead])
def list_faults(
    status_filter: str | None = None,
    db: Session = Depends(get_db),
    _=Depends(require_permission("starlink.view")),
):
    stmt = select(StarlinkFault).order_by(StarlinkFault.created_at.desc())
    if status_filter:
        stmt = stmt.where(StarlinkFault.status == status_filter)
    return db.scalars(stmt).all()


@router.post("/{kit_id}/faults", response_model=StarlinkFaultRead, status_code=status.HTTP_201_CREATED)
def create_fault(
    kit_id: uuid.UUID,
    payload: StarlinkFaultCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("starlink.maintenance")),
):
    kit = _get_kit(db, kit_id)
    fault = starlink_service.create_fault(db, kit, payload, current_user)
    db.commit()
    db.refresh(fault)
    return fault


@router.put("/faults/{fault_id}", response_model=StarlinkFaultRead)
def update_fault(
    fault_id: uuid.UUID,
    payload: StarlinkFaultUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("starlink.maintenance")),
):
    fault = db.get(StarlinkFault, fault_id)
    if not fault:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Fault ticket not found.")
    fault = starlink_service.update_fault(db, fault, payload, current_user)
    db.commit()
    db.refresh(fault)
    return fault
