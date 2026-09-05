import uuid
from datetime import date as date_type
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.asset import AssetCategory
from app.models.inventory import GoodsReceipt, InventoryTransaction, StockCount, StockCountItem, StockTransfer
from app.models.location import Location
from app.models.procurement import Procurement
from app.models.supplier import Supplier


def get_balance(db: Session, warehouse_id: uuid.UUID, category_id: uuid.UUID) -> int:
    return db.scalar(
        select(func.coalesce(func.sum(InventoryTransaction.quantity), 0)).where(
            InventoryTransaction.warehouse_id == warehouse_id,
            InventoryTransaction.category_id == category_id,
        )
    )


def _require_quantity_tracked_category(db: Session, category_id: uuid.UUID) -> AssetCategory:
    category = db.get(AssetCategory, category_id)
    if not category:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Unknown category_id.")
    if category.tracking_type != "quantity":
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"{category.name} is a serialized category — register individual units via the "
            "asset register instead of the inventory ledger.",
        )
    return category


def _require_warehouse(db: Session, location_id: uuid.UUID) -> Location:
    location = db.get(Location, location_id)
    if not location or not location.warehouse:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Unknown or non-warehouse location_id.")
    return location


def _generate_code_prefix(db: Session, name: str) -> str:
    letters = "".join(ch for ch in name.upper() if ch.isalnum()) or "CAT"
    base = letters[:4]
    candidate = base
    suffix = 1
    while db.scalar(select(AssetCategory).where(AssetCategory.code_prefix == candidate)):
        suffix += 1
        candidate = f"{base[:3]}{suffix}"
    return candidate


def get_or_create_quantity_category(
    db: Session, *, category_id: uuid.UUID | None, new_category_name: str | None
) -> AssetCategory:
    """Lets whoever holds `inventory.receive` add a new quantity-tracked
    material on the spot while receiving stock, rather than being blocked
    until someone with the separate `assets.manage_catalogue` permission
    creates it first — the brief's own scale requirement (§3: 'administrators
    can add new categories without code changes') extends naturally to store
    staff for this one narrow case. Only ever creates 'quantity' categories —
    a new *serialized* category still requires assets.manage_catalogue via
    the dedicated /asset-categories endpoint, since that affects the Asset ID
    convention (§6.1), not just a stock count."""
    if category_id:
        return _require_quantity_tracked_category(db, category_id)

    name = (new_category_name or "").strip()
    if not name:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Provide either category_id or new_category_name.")

    existing = db.scalar(select(AssetCategory).where(func.lower(AssetCategory.name) == name.lower()))
    if existing:
        if existing.tracking_type != "quantity":
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                f"'{name}' already exists as a serialized asset category — use the asset register for it.",
            )
        return existing

    category = AssetCategory(name=name, code_prefix=_generate_code_prefix(db, name), tracking_type="quantity")
    db.add(category)
    db.flush()
    return category


def record_receipt(
    db: Session,
    *,
    warehouse_id: uuid.UUID,
    items: list[tuple[uuid.UUID, int]],
    performed_by_id: uuid.UUID | None,
    reference_type: str | None = None,
    reference_id: str | None = None,
) -> list[InventoryTransaction]:
    _require_warehouse(db, warehouse_id)
    batch_id = uuid.uuid4()
    rows = []
    for category_id, quantity in items:
        _require_quantity_tracked_category(db, category_id)
        row = InventoryTransaction(
            warehouse_id=warehouse_id,
            category_id=category_id,
            transaction_type="RECEIPT",
            quantity=quantity,
            batch_id=batch_id,
            reference_type=reference_type,
            reference_id=reference_id,
            performed_by_id=performed_by_id,
        )
        db.add(row)
        rows.append(row)
    # Flush so callers can immediately read relationships (row.category,
    # row.warehouse) — SQLAlchemy's lazy loader returns None rather than
    # autoflushing-then-querying for an object that has never been flushed,
    # regardless of the session's autoflush setting (confirmed the hard way:
    # this bit the notification code, which reads exactly those fields right
    # after calling this function).
    db.flush()
    return rows


def create_goods_receipt(
    db: Session,
    *,
    warehouse_id: uuid.UUID,
    supplier_id: uuid.UUID | None,
    procurement_id: uuid.UUID | None,
    received_by_name: str,
    delivered_by_name: str | None,
    receipt_date: date_type | None,
    remarks: str | None,
    items: list[tuple[uuid.UUID | None, str | None, int]],
    performed_by_id: uuid.UUID | None,
) -> tuple[GoodsReceipt, list[InventoryTransaction], list[AssetCategory]]:
    """The accountability wrapper brief §5/§7.1 call for — who received it, who
    delivered it, which supplier — around the actual stock-quantity effect,
    which stays in record_receipt()'s InventoryTransaction rows. `items` is
    (category_id, new_category_name, quantity) — exactly one of the first two
    per line; see get_or_create_quantity_category for the new-category path."""
    _require_warehouse(db, warehouse_id)
    if supplier_id and not db.get(Supplier, supplier_id):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Unknown supplier_id.")
    if procurement_id and not db.get(Procurement, procurement_id):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Unknown procurement_id.")

    created_categories: list[AssetCategory] = []
    resolved_items: list[tuple[uuid.UUID, int]] = []
    for category_id, new_category_name, quantity in items:
        was_new = category_id is None
        category = get_or_create_quantity_category(db, category_id=category_id, new_category_name=new_category_name)
        if was_new:
            created_categories.append(category)
        resolved_items.append((category.id, quantity))

    receipt = GoodsReceipt(
        warehouse_id=warehouse_id,
        supplier_id=supplier_id,
        procurement_id=procurement_id,
        received_by_name=received_by_name,
        delivered_by_name=delivered_by_name,
        receipt_date=receipt_date or date_type.today(),
        remarks=remarks,
        created_by_id=performed_by_id,
    )
    db.add(receipt)
    db.flush()

    rows = record_receipt(
        db, warehouse_id=warehouse_id, items=resolved_items, performed_by_id=performed_by_id,
        reference_type="goods_receipt", reference_id=str(receipt.id),
    )
    return receipt, rows, created_categories


def dispatch_transfer(
    db: Session,
    *,
    category_id: uuid.UUID,
    from_warehouse_id: uuid.UUID,
    to_warehouse_id: uuid.UUID,
    quantity: int,
    expected_delivery_date: date_type,
    released_by_name: str,
    reason: str | None,
    performed_by_id: uuid.UUID | None,
) -> tuple[StockTransfer, InventoryTransaction]:
    """Phase 1 of 2. Removes `quantity` from the source's on-hand balance
    immediately (brief §8's ledger principle — the stock has genuinely left)
    but does NOT add it to the destination yet; it only lands there once
    receive_transfer() confirms arrival, matching how the brief already
    treats an IN_TRANSIT asset as neither at its old nor new location."""
    if from_warehouse_id == to_warehouse_id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Source and destination warehouses must differ.")
    _require_warehouse(db, from_warehouse_id)
    _require_warehouse(db, to_warehouse_id)
    _require_quantity_tracked_category(db, category_id)

    current_balance = get_balance(db, from_warehouse_id, category_id)
    if current_balance < quantity:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"Insufficient stock at source warehouse: {current_balance} on hand, {quantity} requested.",
        )

    transfer = StockTransfer(
        category_id=category_id, from_warehouse_id=from_warehouse_id, to_warehouse_id=to_warehouse_id,
        quantity=quantity, status="IN_TRANSIT", expected_delivery_date=expected_delivery_date,
        released_by_name=released_by_name, reason=reason, dispatched_by_id=performed_by_id,
    )
    db.add(transfer)
    db.flush()

    out_row = InventoryTransaction(
        warehouse_id=from_warehouse_id, category_id=category_id, transaction_type="TRANSFER_OUT",
        quantity=-quantity, related_warehouse_id=to_warehouse_id, reason=reason,
        reference_type="stock_transfer", reference_id=str(transfer.id), performed_by_id=performed_by_id,
    )
    db.add(out_row)
    db.flush()  # see comment in record_receipt — needed before relationship access
    return transfer, out_row


def receive_transfer(
    db: Session,
    *,
    transfer: StockTransfer,
    received_by_name: str,
    performed_by_id: uuid.UUID | None,
) -> InventoryTransaction:
    """Phase 2 — creates the TRANSFER_IN row (only now does the stock become
    on-hand at the destination) and closes out the transfer's accountability."""
    if transfer.status == "RECEIVED":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "This transfer has already been received.")

    in_row = InventoryTransaction(
        warehouse_id=transfer.to_warehouse_id, category_id=transfer.category_id, transaction_type="TRANSFER_IN",
        quantity=transfer.quantity, related_warehouse_id=transfer.from_warehouse_id, reason=transfer.reason,
        reference_type="stock_transfer", reference_id=str(transfer.id), performed_by_id=performed_by_id,
    )
    db.add(in_row)

    transfer.status = "RECEIVED"
    transfer.received_by_name = received_by_name
    transfer.received_by_id = performed_by_id
    transfer.actual_delivery_date = date_type.today()
    db.flush()  # see comment in record_receipt — needed before relationship access
    return in_row


def find_newly_overdue_transfers(db: Session) -> list[StockTransfer]:
    """Called by the periodic Celery task (app/services/notification_tasks.py)
    — transfers still IN_TRANSIT past their expected date that haven't been
    flagged yet. Marking overdue_notified_at happens in the same call site
    right after a notification is actually queued, so a task failure between
    'found' and 'notified' just means it's picked up again next run rather
    than silently lost."""
    return db.scalars(
        select(StockTransfer).where(
            StockTransfer.status == "IN_TRANSIT",
            StockTransfer.expected_delivery_date < date_type.today(),
            StockTransfer.overdue_notified_at.is_(None),
        )
    ).all()


def record_adjustment(
    db: Session,
    *,
    warehouse_id: uuid.UUID,
    category_id: uuid.UUID,
    quantity_delta: int,
    reason: str,
    performed_by_id: uuid.UUID | None,
) -> InventoryTransaction:
    _require_warehouse(db, warehouse_id)
    _require_quantity_tracked_category(db, category_id)

    if quantity_delta < 0:
        current_balance = get_balance(db, warehouse_id, category_id)
        if current_balance + quantity_delta < 0:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                f"Adjustment would take stock negative: {current_balance} on hand, {quantity_delta} requested.",
            )

    row = InventoryTransaction(
        warehouse_id=warehouse_id, category_id=category_id, transaction_type="ADJUSTMENT",
        quantity=quantity_delta, reason=reason, performed_by_id=performed_by_id,
    )
    db.add(row)
    db.flush()  # see comment in record_receipt — needed before relationship access
    return row


def finalize_stock_count(db: Session, stock_count: StockCount, *, performed_by_id: uuid.UUID | None) -> None:
    if stock_count.status == "COMPLETED":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "This stock count is already completed.")

    for item in stock_count.items:
        variance = item.physical_quantity - item.expected_quantity
        if variance == 0:
            continue
        if not item.variance_reason:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                f"A variance reason is required for {item.category.name} (variance: {variance:+d}).",
            )
        row = InventoryTransaction(
            warehouse_id=stock_count.warehouse_id, category_id=item.category_id, transaction_type="ADJUSTMENT",
            quantity=variance, reason=f"Stock count reconciliation: {item.variance_reason}",
            reference_type="stock_count", reference_id=str(stock_count.id), performed_by_id=performed_by_id,
        )
        db.add(row)

    stock_count.status = "COMPLETED"
