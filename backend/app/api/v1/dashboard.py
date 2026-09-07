import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_permission
from app.models.asset import Asset, AssetCategory
from app.models.inventory import InventoryTransaction, StockTransfer
from app.models.location import District, Location, Region
from app.models.user import User
from app.services.warehouse_access_service import check_district_access, get_allowed_warehouse_ids

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

# Curated, not "every category" — the national KPI cards above already cover
# the census-specific fleet (tablets, power banks, SIM cards, etc.); this is
# a separate, deliberately short "office/administrative supplies" glance for
# what keeps a district office running day to day. Matched by name so it
# degrades gracefully (just omits a row) if a deployment doesn't have one of
# these categories seeded.
OFFICE_ITEM_CATEGORY_NAMES = [
    "Laptops",
    "Desktop Computers",
    "Printers and Scanners",
    "Printer Ink & Toner",
    "UPS Devices",
    "Stationery",
    "Furniture",
    "Chargers and USB Cables",
]


def _district_location_ids(db: Session, district_id: uuid.UUID) -> list[uuid.UUID]:
    return list(db.scalars(select(Location.id).where(Location.district_id == district_id)).all())


@router.get("/accessible-districts")
def accessible_districts(
    db: Session = Depends(get_db), current_user: User = Depends(require_permission("dashboard.view"))
):
    """Which districts the current user may pick in the Dashboard's district
    switcher: their own single district, every district in their region, or
    — for a national user with neither set — every district in the country.
    Deliberately a separate, narrow endpoint rather than scoping the general
    /districts list, since that endpoint already serves several admin/
    authoring screens (Locations, Starlink field teams and hard-to-reach
    areas, asset registration) that need the full national list regardless
    of the viewer's own operational scope."""
    stmt = select(District).order_by(District.name)
    if current_user.district_id:
        stmt = stmt.where(District.id == current_user.district_id)
    elif current_user.region_id:
        stmt = stmt.where(District.region_id == current_user.region_id)
    districts = db.scalars(stmt).all()
    return [{"id": d.id, "name": d.name, "code": d.code, "region_id": d.region_id} for d in districts]


@router.get("/summary")
def dashboard_summary(
    district_id: uuid.UUID | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("dashboard.view")),
):
    """Real asset counts as of Phase 2 (register + status workflow). Shipment/
    Starlink-specific KPIs (delivered, pending_receipt, active_alerts) stay 0
    until those modules land in later phases (brief §13.1).

    "in_transit" combines two different subsystems that both mean "physically
    moving right now": individually serialized Asset rows with
    status=IN_TRANSIT, plus the quantity on any StockTransfer (bulk,
    quantity-tracked categories) that hasn't been confirmed received yet.
    Different tracking models, same real-world meaning — a district office
    waiting on a delivery doesn't care which subsystem is moving it.

    `district_id`, when given, scopes every asset/transfer count to that
    district's locations only — this is the "District Operations Overview"
    the national Dashboard's district switcher renders. A region- or
    district-scoped user can only request a district within their own
    assignment (checked below); a national user can request any district.

    With no `district_id`, the *default* view is still automatically scoped
    to the caller's own geography — a district-scoped user's plain
    "dashboard" already means their district, not the whole country; a
    region-scoped user's plain dashboard means their whole region. Only a
    genuinely national user (no region_id/district_id, and no explicit
    per-warehouse UserWarehouseAccess restriction) sees the true national
    total by default."""
    asset_stmt = select(Asset.status, func.count())
    transfer_stmt = select(func.coalesce(func.sum(StockTransfer.quantity), 0)).where(
        StockTransfer.status == "IN_TRANSIT"
    )
    district_name = None
    scope = "national"
    location_ids: list[uuid.UUID] | set[uuid.UUID] | None = None

    if district_id:
        check_district_access(db, current_user, district_id)
        district = db.get(District, district_id)
        district_name = district.name if district else None
        location_ids = _district_location_ids(db, district_id)
        explicit = {a.warehouse_id for a in current_user.warehouse_access}
        if explicit:
            location_ids = [loc_id for loc_id in location_ids if loc_id in explicit]
        scope = "district"
    else:
        location_ids = get_allowed_warehouse_ids(db, current_user)
        if location_ids is not None:
            scope = "district" if current_user.district_id else "region" if current_user.region_id else "restricted"
            if current_user.district_id:
                own_district = db.get(District, current_user.district_id)
                district_name = own_district.name if own_district else None
                district_id = current_user.district_id

    if location_ids is not None:
        asset_stmt = asset_stmt.where(Asset.current_location_id.in_(location_ids))
        transfer_stmt = transfer_stmt.where(
            (StockTransfer.from_warehouse_id.in_(location_ids)) | (StockTransfer.to_warehouse_id.in_(location_ids))
        )

    status_counts = dict(db.execute(asset_stmt.group_by(Asset.status)).all())
    in_transit_transfer_qty = db.scalar(transfer_stmt) or 0

    return {
        "scope": scope,
        "district_id": district_id,
        "district_name": district_name,
        "total_assets": sum(status_counts.values()),
        "available": status_counts.get("AVAILABLE", 0),
        "allocated": status_counts.get("ALLOCATED", 0),
        "in_transit": status_counts.get("IN_TRANSIT", 0) + in_transit_transfer_qty,
        "delivered": 0,
        "assigned": status_counts.get("ASSIGNED", 0),
        "pending_receipt": 0,
        "returned": status_counts.get("RETURNED", 0),
        "damaged": status_counts.get("DAMAGED", 0),
        "lost": status_counts.get("LOST", 0),
        "unaccounted": 0,
        "active_alerts": 0,
        "regions_count": db.scalar(select(func.count()).select_from(Region)) or 0,
        "districts_count": db.scalar(select(func.count()).select_from(District)) or 0,
        "users_count": db.scalar(select(func.count()).select_from(User)) or 0,
    }


@router.get("/office-items")
def office_items_summary(
    district_id: uuid.UUID | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("dashboard.view")),
):
    """National (or, with `district_id`, district-scoped) at-a-glance stock
    of office/administrative supplies — a quick-insight companion to the
    fleet KPIs above, not a replacement for the full detail already
    available by drilling into Inventory (per-warehouse balances) or the
    Asset register (per-unit status). For a quantity-tracked category,
    "available" is the same as "total": all on-hand quantity in a warehouse
    is available by definition, there's no separate allocation sub-state
    for consumables the way there is for serialized equipment."""
    location_ids: list[uuid.UUID] | set[uuid.UUID] | None = None
    if district_id:
        check_district_access(db, current_user, district_id)
        location_ids = _district_location_ids(db, district_id)
        explicit = {a.warehouse_id for a in current_user.warehouse_access}
        if explicit:
            location_ids = [loc_id for loc_id in location_ids if loc_id in explicit]
    else:
        location_ids = get_allowed_warehouse_ids(db, current_user)

    categories = db.scalars(
        select(AssetCategory).where(AssetCategory.name.in_(OFFICE_ITEM_CATEGORY_NAMES))
    ).all()
    categories_by_name = {c.name: c for c in categories}

    quantity_category_ids = [c.id for c in categories if c.tracking_type == "quantity"]
    on_hand_by_category: dict = {}
    if quantity_category_ids:
        stmt = (
            select(InventoryTransaction.category_id, func.sum(InventoryTransaction.quantity))
            .where(InventoryTransaction.category_id.in_(quantity_category_ids))
            .group_by(InventoryTransaction.category_id)
        )
        if location_ids is not None:
            stmt = stmt.where(InventoryTransaction.warehouse_id.in_(location_ids))
        on_hand_by_category = dict(db.execute(stmt).all())

    serialized_category_ids = [c.id for c in categories if c.tracking_type == "serialized"]
    total_by_category: dict = {}
    available_by_category: dict = {}
    if serialized_category_ids:
        total_stmt = select(Asset.category_id, func.count()).where(Asset.category_id.in_(serialized_category_ids))
        available_stmt = total_stmt.where(Asset.status == "AVAILABLE")
        if location_ids is not None:
            total_stmt = total_stmt.where(Asset.current_location_id.in_(location_ids))
            available_stmt = available_stmt.where(Asset.current_location_id.in_(location_ids))
        total_by_category = dict(db.execute(total_stmt.group_by(Asset.category_id)).all())
        available_by_category = dict(db.execute(available_stmt.group_by(Asset.category_id)).all())

    results = []
    for name in OFFICE_ITEM_CATEGORY_NAMES:
        category = categories_by_name.get(name)
        if not category:
            continue
        if category.tracking_type == "quantity":
            on_hand = on_hand_by_category.get(category.id, 0) or 0
            results.append({"category_name": name, "tracking_type": "quantity", "total": on_hand, "available": on_hand})
        else:
            total = total_by_category.get(category.id, 0) or 0
            available = available_by_category.get(category.id, 0) or 0
            results.append(
                {"category_name": name, "tracking_type": "serialized", "total": total, "available": available}
            )
    return results
