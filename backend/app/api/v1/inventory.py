import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import client_ip, client_user_agent, get_db, require_permission
from app.models.asset import AssetCategory
from app.models.inventory import GoodsReceipt, InventoryTransaction, StockCount, StockCountItem, StockTransfer
from app.models.location import Location
from app.models.user import User
from app.schemas.common import Page, PaginationParams
from app.schemas.inventory import (
    GoodsReceiptCreate,
    GoodsReceiptRead,
    InventoryTransactionRead,
    StockAdjustmentCreate,
    StockBalance,
    StockCountCreate,
    StockCountRead,
    StockTransferCreate,
    StockTransferRead,
)
from app.services import audit_service, inventory_service, notification_service
from app.services.pagination import paginate
from app.services.warehouse_access_service import check_warehouse_access, get_allowed_warehouse_ids

router = APIRouter(prefix="/inventory", tags=["inventory"])


@router.get("/balances", response_model=list[StockBalance])
def get_stock_balances(
    warehouse_id: uuid.UUID | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("inventory.view")),
):
    stmt = (
        select(
            InventoryTransaction.warehouse_id,
            Location.name.label("warehouse_name"),
            InventoryTransaction.category_id,
            AssetCategory.name.label("category_name"),
            func.sum(InventoryTransaction.quantity).label("quantity_on_hand"),
        )
        .join(Location, Location.id == InventoryTransaction.warehouse_id)
        .join(AssetCategory, AssetCategory.id == InventoryTransaction.category_id)
        .group_by(
            InventoryTransaction.warehouse_id, Location.name, InventoryTransaction.category_id, AssetCategory.name
        )
    )
    if warehouse_id:
        check_warehouse_access(current_user, warehouse_id)
        stmt = stmt.where(InventoryTransaction.warehouse_id == warehouse_id)
    else:
        allowed = get_allowed_warehouse_ids(current_user)
        if allowed is not None:
            stmt = stmt.where(InventoryTransaction.warehouse_id.in_(allowed))

    rows = db.execute(stmt).all()
    return [
        StockBalance(
            warehouse_id=r.warehouse_id, warehouse_name=r.warehouse_name,
            category_id=r.category_id, category_name=r.category_name,
            quantity_on_hand=r.quantity_on_hand or 0,
        )
        for r in rows
    ]


@router.get("/transactions", response_model=Page[InventoryTransactionRead])
def list_transactions(
    params: PaginationParams = Depends(),
    warehouse_id: uuid.UUID | None = None,
    category_id: uuid.UUID | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("inventory.view")),
):
    stmt = select(InventoryTransaction).options(
        selectinload(InventoryTransaction.warehouse),
        selectinload(InventoryTransaction.category),
        selectinload(InventoryTransaction.related_warehouse),
    )
    if warehouse_id:
        check_warehouse_access(current_user, warehouse_id)
        stmt = stmt.where(InventoryTransaction.warehouse_id == warehouse_id)
    else:
        allowed = get_allowed_warehouse_ids(current_user)
        if allowed is not None:
            stmt = stmt.where(InventoryTransaction.warehouse_id.in_(allowed))
    if category_id:
        stmt = stmt.where(InventoryTransaction.category_id == category_id)
    stmt = stmt.order_by(InventoryTransaction.created_at.desc())
    return paginate(db, stmt, InventoryTransaction, params, InventoryTransactionRead)


@router.post("/receipts", response_model=GoodsReceiptRead, status_code=status.HTTP_201_CREATED)
def create_goods_receipt(
    payload: GoodsReceiptCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("inventory.receive")),
):
    check_warehouse_access(current_user, payload.warehouse_id)
    receipt, rows, created_categories = inventory_service.create_goods_receipt(
        db, warehouse_id=payload.warehouse_id, supplier_id=payload.supplier_id,
        procurement_id=payload.procurement_id, received_by_name=current_user.full_name,
        delivered_by_name=payload.delivered_by_name, receipt_date=payload.receipt_date,
        remarks=payload.remarks,
        items=[(item.category_id, item.new_category_name, item.quantity) for item in payload.items],
        performed_by_id=current_user.id,
    )
    if created_categories:
        audit_service.record(
            db, user_id=current_user.id, action="create", entity_type="asset_category",
            entity_id=",".join(str(c.id) for c in created_categories),
            new_value={"names": [c.name for c in created_categories], "created_via": "goods_receipt"},
            ip_address=client_ip(request), user_agent=client_user_agent(request),
        )
    audit_service.record(
        db, user_id=current_user.id, action="goods_receipt", entity_type="goods_receipt",
        entity_id=str(receipt.id),
        new_value={
            "warehouse_id": str(payload.warehouse_id), "received_by_name": receipt.received_by_name,
            "delivered_by_name": payload.delivered_by_name,
            "items": [
                {"category": i.category_id and str(i.category_id) or i.new_category_name, "quantity": i.quantity}
                for i in payload.items
            ],
        },
        ip_address=client_ip(request), user_agent=client_user_agent(request),
    )

    items_summary = "; ".join(f"{r.category.name}: +{r.quantity}" for r in rows)
    supplier_name = receipt.supplier.name if receipt.supplier else "an unregistered supplier"
    notifications = notification_service.notify(
        db, event_type="inventory.receipt",
        context={
            "warehouse_name": rows[0].warehouse.name, "items_summary": items_summary,
            "received_by": receipt.received_by_name,
            "delivered_by": payload.delivered_by_name or "not recorded",
            "supplier_name": supplier_name,
        },
        recipients=notification_service.get_users_with_permission(db, "inventory.reconcile"),
        related_entity_type="goods_receipt", related_entity_id=str(receipt.id),
    )

    db.commit()
    db.refresh(receipt)
    for row in rows:
        db.refresh(row)
    notification_service.dispatch(notifications)
    return GoodsReceiptRead(
        id=receipt.id, warehouse=rows[0].warehouse, supplier=receipt.supplier,
        procurement_id=receipt.procurement_id, received_by_name=receipt.received_by_name,
        delivered_by_name=receipt.delivered_by_name, receipt_date=receipt.receipt_date,
        remarks=receipt.remarks, items=rows, created_at=receipt.created_at,
    )


@router.get("/receipts", response_model=Page[GoodsReceiptRead])
def list_goods_receipts(
    params: PaginationParams = Depends(),
    warehouse_id: uuid.UUID | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("inventory.view")),
):
    """Hand-rolled rather than the shared paginate() helper — GoodsReceiptRead's
    `items` has no direct ORM relationship to select through (the link to
    InventoryTransaction is a string reference_id, not a FK), so each page's
    line items are fetched in one follow-up query and grouped in Python."""
    stmt = select(GoodsReceipt).options(
        selectinload(GoodsReceipt.supplier), selectinload(GoodsReceipt.warehouse)
    )
    if warehouse_id:
        check_warehouse_access(current_user, warehouse_id)
        stmt = stmt.where(GoodsReceipt.warehouse_id == warehouse_id)
    else:
        allowed = get_allowed_warehouse_ids(current_user)
        if allowed is not None:
            stmt = stmt.where(GoodsReceipt.warehouse_id.in_(allowed))

    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    stmt = stmt.order_by(GoodsReceipt.receipt_date.desc(), GoodsReceipt.created_at.desc())
    offset = (params.page - 1) * params.page_size
    receipts = db.execute(stmt.offset(offset).limit(params.page_size)).scalars().all()

    items_by_receipt: dict[str, list[InventoryTransaction]] = {}
    if receipts:
        receipt_ids = [str(r.id) for r in receipts]
        item_rows = db.execute(
            select(InventoryTransaction)
            .options(selectinload(InventoryTransaction.category), selectinload(InventoryTransaction.warehouse))
            .where(InventoryTransaction.reference_type == "goods_receipt", InventoryTransaction.reference_id.in_(receipt_ids))
        ).scalars().all()
        for item in item_rows:
            items_by_receipt.setdefault(item.reference_id, []).append(item)

    return Page(
        items=[
            GoodsReceiptRead(
                id=r.id, warehouse=r.warehouse, supplier=r.supplier, procurement_id=r.procurement_id,
                received_by_name=r.received_by_name, delivered_by_name=r.delivered_by_name,
                receipt_date=r.receipt_date, remarks=r.remarks,
                items=items_by_receipt.get(str(r.id), []), created_at=r.created_at,
            )
            for r in receipts
        ],
        total=total, page=params.page, page_size=params.page_size,
        pages=max(1, -(-total // params.page_size)),
    )


def _transfer_read_query():
    return select(StockTransfer).options(
        selectinload(StockTransfer.category),
        selectinload(StockTransfer.from_warehouse),
        selectinload(StockTransfer.to_warehouse),
    )


@router.get("/transfers", response_model=Page[StockTransferRead])
def list_stock_transfers(
    params: PaginationParams = Depends(),
    status_filter: str | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("inventory.view")),
):
    stmt = _transfer_read_query()
    allowed = get_allowed_warehouse_ids(current_user)
    if allowed is not None:
        stmt = stmt.where(
            (StockTransfer.from_warehouse_id.in_(allowed)) | (StockTransfer.to_warehouse_id.in_(allowed))
        )
    if status_filter:
        stmt = stmt.where(StockTransfer.status == status_filter)
    stmt = stmt.order_by(StockTransfer.created_at.desc())
    return paginate(db, stmt, StockTransfer, params, StockTransferRead)


@router.post("/transfers", response_model=StockTransferRead, status_code=status.HTTP_201_CREATED)
def create_stock_transfer(
    payload: StockTransferCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("inventory.transfer")),
):
    check_warehouse_access(current_user, payload.from_warehouse_id)
    transfer, out_row = inventory_service.dispatch_transfer(
        db, category_id=payload.category_id, from_warehouse_id=payload.from_warehouse_id,
        to_warehouse_id=payload.to_warehouse_id, quantity=payload.quantity,
        expected_delivery_date=payload.expected_delivery_date, released_by_name=current_user.full_name,
        reason=payload.reason, performed_by_id=current_user.id,
    )
    audit_service.record(
        db, user_id=current_user.id, action="stock_transfer_dispatch", entity_type="stock_transfer",
        entity_id=str(transfer.id),
        new_value={
            "from": str(payload.from_warehouse_id), "to": str(payload.to_warehouse_id),
            "quantity": payload.quantity, "expected_delivery_date": str(payload.expected_delivery_date),
            "released_by_name": transfer.released_by_name,
        },
        ip_address=client_ip(request), user_agent=client_user_agent(request),
    )

    notifications = notification_service.notify(
        db, event_type="inventory.transfer_dispatched",
        context={
            "category_name": out_row.category.name, "quantity": payload.quantity,
            "from_warehouse": out_row.warehouse.name, "to_warehouse": transfer.to_warehouse.name,
            "released_by": transfer.released_by_name,
            "expected_delivery_date": payload.expected_delivery_date.isoformat(),
        },
        recipients=notification_service.get_users_with_permission(db, "inventory.reconcile"),
        related_entity_type="stock_transfer", related_entity_id=str(transfer.id),
    )

    db.commit()
    db.refresh(transfer)
    notification_service.dispatch(notifications)
    return transfer


@router.post("/transfers/{transfer_id}/receive", response_model=StockTransferRead)
def receive_stock_transfer(
    transfer_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("inventory.receive")),
):
    transfer = db.get(StockTransfer, transfer_id)
    if not transfer:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Transfer not found.")
    check_warehouse_access(current_user, transfer.to_warehouse_id)

    in_row = inventory_service.receive_transfer(
        db, transfer=transfer, received_by_name=current_user.full_name, performed_by_id=current_user.id,
    )
    audit_service.record(
        db, user_id=current_user.id, action="stock_transfer_receive", entity_type="stock_transfer",
        entity_id=str(transfer.id),
        new_value={"received_by_name": transfer.received_by_name, "quantity": in_row.quantity},
        ip_address=client_ip(request), user_agent=client_user_agent(request),
    )

    notifications = notification_service.notify(
        db, event_type="inventory.transfer_received",
        context={
            "category_name": in_row.category.name, "quantity": in_row.quantity,
            "to_warehouse": in_row.warehouse.name, "received_by": transfer.received_by_name,
        },
        recipients=notification_service.get_users_with_permission(db, "inventory.reconcile"),
        related_entity_type="stock_transfer", related_entity_id=str(transfer.id),
    )

    db.commit()
    db.refresh(transfer)
    notification_service.dispatch(notifications)
    return transfer


@router.post("/adjustments", response_model=InventoryTransactionRead, status_code=status.HTTP_201_CREATED)
def create_stock_adjustment(
    payload: StockAdjustmentCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("inventory.adjust")),
):
    check_warehouse_access(current_user, payload.warehouse_id)
    row = inventory_service.record_adjustment(
        db, warehouse_id=payload.warehouse_id, category_id=payload.category_id,
        quantity_delta=payload.quantity_delta, reason=payload.reason, performed_by_id=current_user.id,
    )
    audit_service.record(
        db, user_id=current_user.id, action="stock_adjustment", entity_type="inventory",
        entity_id=str(payload.category_id),
        new_value={"warehouse_id": str(payload.warehouse_id), "quantity_delta": payload.quantity_delta},
        reason=payload.reason,
        ip_address=client_ip(request), user_agent=client_user_agent(request),
    )

    notifications = notification_service.notify(
        db, event_type="inventory.adjustment",
        context={
            "category_name": row.category.name, "warehouse_name": row.warehouse.name,
            "quantity_delta": payload.quantity_delta, "reason": payload.reason,
            "performed_by": current_user.full_name,
        },
        recipients=notification_service.get_users_with_permission(db, "inventory.reconcile"),
        related_entity_type="asset_category", related_entity_id=str(payload.category_id),
    )

    db.commit()
    db.refresh(row)
    notification_service.dispatch(notifications)
    return row


# --- Stock counts / reconciliation ------------------------------------------

def _stock_count_read_query():
    return select(StockCount).options(selectinload(StockCount.items).selectinload(StockCountItem.category))


@router.get("/stock-counts", response_model=list[StockCountRead])
def list_stock_counts(
    warehouse_id: uuid.UUID | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("inventory.view")),
):
    stmt = _stock_count_read_query().order_by(StockCount.count_date.desc())
    if warehouse_id:
        check_warehouse_access(current_user, warehouse_id)
        stmt = stmt.where(StockCount.warehouse_id == warehouse_id)
    else:
        allowed = get_allowed_warehouse_ids(current_user)
        if allowed is not None:
            stmt = stmt.where(StockCount.warehouse_id.in_(allowed))
    return db.scalars(stmt).all()


@router.post("/stock-counts", response_model=StockCountRead, status_code=status.HTTP_201_CREATED)
def create_stock_count(
    payload: StockCountCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("inventory.reconcile")),
):
    check_warehouse_access(current_user, payload.warehouse_id)
    stock_count = StockCount(
        warehouse_id=payload.warehouse_id, count_date=payload.count_date,
        counted_by_id=current_user.id, notes=payload.notes,
    )
    db.add(stock_count)
    db.flush()

    for item in payload.items:
        expected = inventory_service.get_balance(db, payload.warehouse_id, item.category_id) or 0
        db.add(
            StockCountItem(
                stock_count_id=stock_count.id, category_id=item.category_id,
                expected_quantity=expected, physical_quantity=item.physical_quantity,
                variance_reason=item.variance_reason,
            )
        )
    db.commit()
    return db.execute(_stock_count_read_query().where(StockCount.id == stock_count.id)).scalar_one()


@router.post("/stock-counts/{stock_count_id}/finalize", response_model=StockCountRead)
def finalize_stock_count(
    stock_count_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("inventory.reconcile")),
):
    stock_count = db.execute(
        _stock_count_read_query().where(StockCount.id == stock_count_id)
    ).scalar_one_or_none()
    if not stock_count:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Stock count not found.")
    check_warehouse_access(current_user, stock_count.warehouse_id)

    inventory_service.finalize_stock_count(db, stock_count, performed_by_id=current_user.id)
    audit_service.record(
        db, user_id=current_user.id, action="stock_count_finalized", entity_type="stock_count",
        entity_id=str(stock_count.id),
        ip_address=client_ip(request), user_agent=client_user_agent(request),
    )
    db.commit()
    return db.execute(_stock_count_read_query().where(StockCount.id == stock_count.id)).scalar_one()
