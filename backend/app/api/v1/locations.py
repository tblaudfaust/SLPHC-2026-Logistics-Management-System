import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import client_ip, client_user_agent, get_db, require_permission
from app.models.location import District, Location, LocationType, Region
from app.models.user import User
from app.schemas.common import Page, PaginationParams
from app.schemas.location import (
    DistrictCreate,
    DistrictRead,
    LocationCreate,
    LocationRead,
    LocationTypeCreate,
    LocationTypeRead,
    LocationUpdate,
    RegionCreate,
    RegionRead,
)
from app.services import audit_service
from app.services.pagination import paginate

router = APIRouter(tags=["locations"])


@router.get("/regions", response_model=list[RegionRead])
def list_regions(db: Session = Depends(get_db), _=Depends(require_permission("locations.view"))):
    return db.scalars(select(Region).order_by(Region.name)).all()


@router.post("/regions", response_model=RegionRead, status_code=status.HTTP_201_CREATED)
def create_region(
    payload: RegionCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("locations.manage")),
):
    if db.scalar(select(Region).where(Region.code == payload.code)):
        raise HTTPException(status.HTTP_409_CONFLICT, "A region with this code already exists.")
    region = Region(name=payload.name, code=payload.code)
    db.add(region)
    db.flush()
    audit_service.record(
        db, user_id=current_user.id, action="create", entity_type="region", entity_id=str(region.id),
        new_value={"name": region.name, "code": region.code},
        ip_address=client_ip(request), user_agent=client_user_agent(request),
    )
    db.commit()
    db.refresh(region)
    return region


@router.get("/districts", response_model=list[DistrictRead])
def list_districts(
    region_id: uuid.UUID | None = None,
    db: Session = Depends(get_db),
    _=Depends(require_permission("locations.view")),
):
    stmt = select(District).order_by(District.name)
    if region_id:
        stmt = stmt.where(District.region_id == region_id)
    return db.scalars(stmt).all()


@router.post("/districts", response_model=DistrictRead, status_code=status.HTTP_201_CREATED)
def create_district(
    payload: DistrictCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("locations.manage")),
):
    if not db.get(Region, payload.region_id):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Unknown region_id.")
    if db.scalar(select(District).where(District.code == payload.code)):
        raise HTTPException(status.HTTP_409_CONFLICT, "A district with this code already exists.")
    district = District(name=payload.name, code=payload.code, region_id=payload.region_id)
    db.add(district)
    db.flush()
    audit_service.record(
        db, user_id=current_user.id, action="create", entity_type="district", entity_id=str(district.id),
        new_value={"name": district.name, "code": district.code},
        ip_address=client_ip(request), user_agent=client_user_agent(request),
    )
    db.commit()
    db.refresh(district)
    return district


@router.get("/location-types", response_model=list[LocationTypeRead])
def list_location_types(db: Session = Depends(get_db), _=Depends(require_permission("locations.view"))):
    return db.scalars(select(LocationType).order_by(LocationType.name)).all()


@router.post("/location-types", response_model=LocationTypeRead, status_code=status.HTTP_201_CREATED)
def create_location_type(
    payload: LocationTypeCreate,
    db: Session = Depends(get_db),
    _=Depends(require_permission("locations.manage")),
):
    if db.scalar(select(LocationType).where(LocationType.name == payload.name)):
        raise HTTPException(status.HTTP_409_CONFLICT, "A location type with this name already exists.")
    location_type = LocationType(name=payload.name, description=payload.description)
    db.add(location_type)
    db.commit()
    db.refresh(location_type)
    return location_type


@router.get("/locations", response_model=Page[LocationRead])
def list_locations(
    params: PaginationParams = Depends(),
    region_id: uuid.UUID | None = None,
    district_id: uuid.UUID | None = None,
    db: Session = Depends(get_db),
    _=Depends(require_permission("locations.view")),
):
    stmt = select(Location)
    if region_id:
        stmt = stmt.where(Location.region_id == region_id)
    if district_id:
        stmt = stmt.where(Location.district_id == district_id)
    if params.search:
        stmt = stmt.where(Location.name.ilike(f"%{params.search}%"))
    return paginate(db, stmt, Location, params, LocationRead)


@router.post("/locations", response_model=LocationRead, status_code=status.HTTP_201_CREATED)
def create_location(
    payload: LocationCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("locations.manage")),
):
    if not db.get(LocationType, payload.location_type_id):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Unknown location_type_id.")
    if payload.region_id and not db.get(Region, payload.region_id):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Unknown region_id.")
    if payload.district_id and not db.get(District, payload.district_id):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Unknown district_id.")
    location = Location(**payload.model_dump())
    db.add(location)
    db.flush()
    audit_service.record(
        db, user_id=current_user.id, action="create", entity_type="location", entity_id=str(location.id),
        new_value={"name": location.name},
        ip_address=client_ip(request), user_agent=client_user_agent(request),
    )
    db.commit()
    db.refresh(location)
    return location


@router.put("/locations/{location_id}", response_model=LocationRead)
def update_location(
    location_id: uuid.UUID,
    payload: LocationUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("locations.manage")),
):
    location = db.get(Location, location_id)
    if not location:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Location not found.")

    old_value = {"name": location.name, "is_active": location.is_active}
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(location, field, value)

    audit_service.record(
        db, user_id=current_user.id, action="update", entity_type="location", entity_id=str(location.id),
        old_value=old_value, new_value={"name": location.name, "is_active": location.is_active},
        ip_address=client_ip(request), user_agent=client_user_agent(request),
    )
    db.commit()
    db.refresh(location)
    return location
