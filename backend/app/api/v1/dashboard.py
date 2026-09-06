from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_permission
from app.models.asset import Asset, AssetCategory
from app.models.inventory import InventoryTransaction, StockTransfer
from app.models.location import District, Region
from app.models.user import User

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


@router.get("/summary")
def dashboard_summary(db: Session = Depends(get_db), _=Depends(require_permission("dashboard.view"))):
    """Real asset counts as of Phase 2 (register + status workflow). Shipment/
    Starlink-specific KPIs (delivered, pending_receipt, active_alerts) stay 0
    until those modules land in later phases (brief §13.1).

    "in_transit" combines two different subsystems that both mean "physically
    moving right now": individually serialized Asset rows with
    status=IN_TRANSIT, plus the quantity on any StockTransfer (bulk,
    quantity-tracked categories) that hasn't been confirmed received yet.
    Different tracking models, same real-world meaning — a district office
    waiting on a delivery doesn't care which subsystem is moving it."""
    status_counts = dict(
        db.execute(select(Asset.status, func.count()).group_by(Asset.status)).all()
    )
    in_transit_transfer_qty = db.scalar(
        select(func.coalesce(func.sum(StockTransfer.quantity), 0)).where(
            StockTransfer.status == "IN_TRANSIT"
        )
    ) or 0

    return {
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
def office_items_summary(db: Session = Depends(get_db), _=Depends(require_permission("dashboard.view"))):
    """National at-a-glance stock of office/administrative supplies — a
    quick-insight companion to the census-fleet KPIs above, not a
    replacement for the full detail already available by drilling into
    Inventory (per-warehouse balances) or the Asset register (per-unit
    status). For a quantity-tracked category, "available" is the same as
    "total": all on-hand quantity in a warehouse is available by definition,
    there's no separate allocation sub-state for consumables the way there
    is for serialized equipment."""
    categories = db.scalars(
        select(AssetCategory).where(AssetCategory.name.in_(OFFICE_ITEM_CATEGORY_NAMES))
    ).all()
    categories_by_name = {c.name: c for c in categories}

    quantity_category_ids = [c.id for c in categories if c.tracking_type == "quantity"]
    on_hand_by_category: dict = {}
    if quantity_category_ids:
        rows = db.execute(
            select(InventoryTransaction.category_id, func.sum(InventoryTransaction.quantity))
            .where(InventoryTransaction.category_id.in_(quantity_category_ids))
            .group_by(InventoryTransaction.category_id)
        ).all()
        on_hand_by_category = dict(rows)

    serialized_category_ids = [c.id for c in categories if c.tracking_type == "serialized"]
    total_by_category: dict = {}
    available_by_category: dict = {}
    if serialized_category_ids:
        total_rows = db.execute(
            select(Asset.category_id, func.count())
            .where(Asset.category_id.in_(serialized_category_ids))
            .group_by(Asset.category_id)
        ).all()
        total_by_category = dict(total_rows)
        available_rows = db.execute(
            select(Asset.category_id, func.count())
            .where(Asset.category_id.in_(serialized_category_ids), Asset.status == "AVAILABLE")
            .group_by(Asset.category_id)
        ).all()
        available_by_category = dict(available_rows)

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
