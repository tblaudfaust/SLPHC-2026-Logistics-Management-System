import io
import uuid

import qrcode
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy import or_, select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import client_ip, client_user_agent, get_db, require_permission
from app.core.config import settings
from app.models.asset import Asset, AssetCategory, AssetModel, AssetStatusEvent
from app.models.procurement import Procurement
from app.models.supplier import Supplier
from app.models.user import User
from app.schemas.asset import (
    AssetCategoryCreate,
    AssetCategoryRead,
    AssetCreate,
    AssetListItem,
    AssetModelCreate,
    AssetModelRead,
    AssetRead,
    AssetStatusChange,
    AssetStatusEventRead,
    AssetUpdate,
    BulkImportRequest,
    BulkImportResponse,
)
from app.schemas.common import Page, PaginationParams
from app.services import asset_service, audit_service, notification_service
from app.services.pagination import paginate

router = APIRouter(tags=["assets"])


# --- Catalogue: categories & models ---------------------------------------

@router.get("/asset-categories", response_model=list[AssetCategoryRead])
def list_asset_categories(db: Session = Depends(get_db), _=Depends(require_permission("assets.view"))):
    return db.scalars(select(AssetCategory).order_by(AssetCategory.name)).all()


@router.post("/asset-categories", response_model=AssetCategoryRead, status_code=status.HTTP_201_CREATED)
def create_asset_category(
    payload: AssetCategoryCreate,
    db: Session = Depends(get_db),
    _=Depends(require_permission("assets.manage_catalogue")),
):
    if db.scalar(select(AssetCategory).where(AssetCategory.code_prefix == payload.code_prefix)):
        raise HTTPException(status.HTTP_409_CONFLICT, "A category with this code prefix already exists.")
    if db.scalar(select(AssetCategory).where(AssetCategory.name == payload.name)):
        raise HTTPException(status.HTTP_409_CONFLICT, "A category with this name already exists.")

    category = AssetCategory(**payload.model_dump())
    db.add(category)
    db.commit()
    db.refresh(category)
    return category


@router.get("/asset-models", response_model=list[AssetModelRead])
def list_asset_models(
    category_id: uuid.UUID | None = None,
    db: Session = Depends(get_db),
    _=Depends(require_permission("assets.view")),
):
    stmt = select(AssetModel).order_by(AssetModel.brand, AssetModel.model_name)
    if category_id:
        stmt = stmt.where(AssetModel.category_id == category_id)
    return db.scalars(stmt).all()


@router.post("/asset-models", response_model=AssetModelRead, status_code=status.HTTP_201_CREATED)
def create_asset_model(
    payload: AssetModelCreate,
    db: Session = Depends(get_db),
    _=Depends(require_permission("assets.manage_catalogue")),
):
    if not db.get(AssetCategory, payload.category_id):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Unknown category_id.")
    asset_model = AssetModel(**payload.model_dump())
    db.add(asset_model)
    db.commit()
    db.refresh(asset_model)
    return asset_model


# --- Asset register ---------------------------------------------------------

def _asset_read_query():
    return select(Asset).options(
        selectinload(Asset.category),
        selectinload(Asset.model),
        selectinload(Asset.current_location),
        selectinload(Asset.current_custodian),
    )


@router.get("/assets", response_model=Page[AssetListItem])
def list_assets(
    params: PaginationParams = Depends(),
    category_id: uuid.UUID | None = None,
    status_filter: str | None = None,
    db: Session = Depends(get_db),
    _=Depends(require_permission("assets.view")),
):
    stmt = select(Asset)
    if category_id:
        stmt = stmt.where(Asset.category_id == category_id)
    if status_filter:
        stmt = stmt.where(Asset.status == status_filter)
    if params.search:
        like = f"%{params.search}%"
        stmt = stmt.where(
            or_(Asset.asset_tag.ilike(like), Asset.serial_number.ilike(like), Asset.imei_1.ilike(like))
        )
    return paginate(db, stmt, Asset, params, AssetListItem)


@router.post("/assets", response_model=AssetRead, status_code=status.HTTP_201_CREATED)
def register_asset(
    payload: AssetCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("assets.create")),
):
    category = db.get(AssetCategory, payload.category_id)
    if not category:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Unknown category_id.")
    if category.tracking_type != "serialized":
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "This category is quantity-tracked, not individually registered. "
            "Use inventory receipt for consumable stock (available from Phase 3).",
        )
    if payload.serial_number and db.scalar(select(Asset).where(Asset.serial_number == payload.serial_number)):
        raise HTTPException(status.HTTP_409_CONFLICT, "An asset with this serial number is already registered.")
    if payload.supplier_id and not db.get(Supplier, payload.supplier_id):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Unknown supplier_id.")
    if payload.procurement_id and not db.get(Procurement, payload.procurement_id):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Unknown procurement_id.")

    asset_tag = asset_service.generate_asset_tag(db, category)
    asset = Asset(
        asset_tag=asset_tag,
        created_by_id=current_user.id,
        **payload.model_dump(),
    )
    db.add(asset)
    db.flush()

    asset_service.record_event(
        db, asset, event_type="registered", performed_by_id=current_user.id,
        new_status=asset.status, new_location_id=asset.current_location_id,
        condition=asset.condition, reason="Asset registered",
    )
    audit_service.record(
        db, user_id=current_user.id, action="create", entity_type="asset", entity_id=str(asset.id),
        new_value={"asset_tag": asset.asset_tag, "category": category.name},
        ip_address=client_ip(request), user_agent=client_user_agent(request),
    )

    location_name = asset.current_location.name if asset.current_location else "Unassigned"
    notifications = notification_service.notify(
        db, event_type="asset.registered",
        context={
            "asset_tag": asset.asset_tag, "category_name": category.name,
            "registered_by": current_user.full_name, "location_name": location_name,
        },
        recipients=notification_service.get_users_with_permission(db, "assets.manage_catalogue"),
        related_entity_type="asset", related_entity_id=str(asset.id),
    )

    db.commit()
    notification_service.dispatch(notifications)

    return db.execute(_asset_read_query().where(Asset.id == asset.id)).scalar_one()


@router.post("/assets/bulk-import", response_model=BulkImportResponse)
def bulk_import_assets(
    payload: BulkImportRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("assets.create")),
):
    """Brief §19.1/§19.2: Excel bulk import. The frontend parses the workbook
    and sends structured rows — call with commit=false first to preview
    (no DB writes), then again with commit=true once the user has reviewed
    the report, per §19.1's 'show ... before committing an import'."""
    category = db.get(AssetCategory, payload.category_id)
    if not category:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Unknown category_id.")
    if category.tracking_type != "serialized":
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"{category.name} is quantity-tracked — bulk import is for serialized assets. "
            "Use a goods receipt for consumable stock.",
        )
    if payload.supplier_id and not db.get(Supplier, payload.supplier_id):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Unknown supplier_id.")
    if payload.procurement_id and not db.get(Procurement, payload.procurement_id):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Unknown procurement_id.")

    valid_rows, errors = asset_service.validate_bulk_rows(db, rows=payload.rows)

    if not payload.commit:
        return BulkImportResponse(
            total_rows=len(payload.rows), valid_count=len(valid_rows), invalid_count=len(errors),
            errors=errors[: asset_service.MAX_REPORTED_ERRORS], committed=False,
        )

    created = asset_service.bulk_register_assets(
        db, category=category, model_id=payload.model_id, current_location_id=payload.current_location_id,
        supplier_id=payload.supplier_id, procurement_id=payload.procurement_id, rows=valid_rows,
        performed_by_id=current_user.id,
    )

    audit_service.record(
        db, user_id=current_user.id, action="bulk_import", entity_type="asset", entity_id=str(category.id),
        new_value={
            "category": category.name, "created_count": len(created),
            "first_asset_tag": created[0].asset_tag if created else None,
            "last_asset_tag": created[-1].asset_tag if created else None,
        },
        reason=f"{len(errors)} row(s) skipped — see bulk import report.",
        ip_address=client_ip(request), user_agent=client_user_agent(request),
    )

    notifications = []
    if created:
        notifications = notification_service.notify(
            db, event_type="asset.bulk_imported",
            context={
                "count": len(created), "category_name": category.name,
                "imported_by": current_user.full_name,
                "first_asset_tag": created[0].asset_tag, "last_asset_tag": created[-1].asset_tag,
                "skipped_count": len(errors),
            },
            recipients=notification_service.get_users_with_permission(db, "assets.manage_catalogue"),
            related_entity_type="asset_category", related_entity_id=str(category.id),
        )

    db.commit()
    notification_service.dispatch(notifications)

    return BulkImportResponse(
        total_rows=len(payload.rows), valid_count=len(valid_rows), invalid_count=len(errors),
        errors=errors[: asset_service.MAX_REPORTED_ERRORS], committed=True, created_count=len(created),
        first_asset_tag=created[0].asset_tag if created else None,
        last_asset_tag=created[-1].asset_tag if created else None,
    )


@router.get("/assets/by-tag/{asset_tag}", response_model=AssetRead)
def get_asset_by_tag(
    asset_tag: str,
    db: Session = Depends(get_db),
    _=Depends(require_permission("assets.view")),
):
    """Resolves a scanned QR code (brief §6.3 — the QR encodes the human
    Asset ID, e.g. SLPHC26-TAB-000001, not the internal UUID) to the full
    asset profile. Distinct path shape from /assets/{asset_id} below (two
    segments vs. one) so routing between them is unambiguous."""
    asset = db.execute(_asset_read_query().where(Asset.asset_tag == asset_tag)).scalar_one_or_none()
    if not asset:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Asset not found.")
    return asset


@router.get("/assets/{asset_id}", response_model=AssetRead)
def get_asset(
    asset_id: uuid.UUID,
    db: Session = Depends(get_db),
    _=Depends(require_permission("assets.view")),
):
    asset = db.execute(_asset_read_query().where(Asset.id == asset_id)).scalar_one_or_none()
    if not asset:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Asset not found.")
    return asset


@router.put("/assets/{asset_id}", response_model=AssetRead)
def update_asset(
    asset_id: uuid.UUID,
    payload: AssetUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("assets.update")),
):
    asset = db.get(Asset, asset_id)
    if not asset:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Asset not found.")

    old_value = {"remarks": asset.remarks}
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(asset, field, value)

    audit_service.record(
        db, user_id=current_user.id, action="update", entity_type="asset", entity_id=str(asset.id),
        old_value=old_value, new_value={"remarks": asset.remarks},
        ip_address=client_ip(request), user_agent=client_user_agent(request),
    )
    db.commit()
    return db.execute(_asset_read_query().where(Asset.id == asset.id)).scalar_one()


@router.post("/assets/{asset_id}/status", response_model=AssetRead)
def change_asset_status(
    asset_id: uuid.UUID,
    payload: AssetStatusChange,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("assets.update")),
):
    asset = db.get(Asset, asset_id)
    if not asset:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Asset not found.")

    previous_status = asset.status
    asset_service.change_status(
        db, asset, new_status=payload.new_status, performed_by_id=current_user.id, reason=payload.reason,
        ip_address=client_ip(request), user_agent=client_user_agent(request),
    )

    notifications = []
    if payload.new_status in ("DAMAGED", "LOST", "DISPOSED"):
        notifications = notification_service.notify(
            db, event_type="asset.status_critical",
            context={
                "asset_tag": asset.asset_tag, "category_name": asset.category.name,
                "previous_status": previous_status, "new_status": payload.new_status,
                "reason": payload.reason or "No reason given", "changed_by": current_user.full_name,
            },
            recipients=notification_service.get_users_with_permission(db, "assets.manage_catalogue"),
            related_entity_type="asset", related_entity_id=str(asset.id),
        )

    db.commit()
    notification_service.dispatch(notifications)
    return db.execute(_asset_read_query().where(Asset.id == asset.id)).scalar_one()


@router.get("/assets/{asset_id}/journey", response_model=list[AssetStatusEventRead])
def get_asset_journey(
    asset_id: uuid.UUID,
    db: Session = Depends(get_db),
    _=Depends(require_permission("assets.view")),
):
    if not db.get(Asset, asset_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Asset not found.")
    stmt = (
        select(AssetStatusEvent)
        .where(AssetStatusEvent.asset_id == asset_id)
        .options(selectinload(AssetStatusEvent.performed_by))
        .order_by(AssetStatusEvent.created_at.desc())
    )
    return db.scalars(stmt).all()


@router.get("/assets/{asset_id}/qr-code")
def get_asset_qr_code(
    asset_id: uuid.UUID,
    db: Session = Depends(get_db),
    _=Depends(require_permission("assets.view")),
):
    """Encodes only the internal Asset ID (brief §6.3: 'should identify the
    internal Asset ID rather than exposing sensitive credentials')."""
    asset = db.get(Asset, asset_id)
    if not asset:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Asset not found.")

    payload = f"{settings.QR_CODE_BASE_URL.rstrip('/')}/assets/tag/{asset.asset_tag}"
    img = qrcode.make(payload)
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)
    return StreamingResponse(buffer, media_type="image/png")
