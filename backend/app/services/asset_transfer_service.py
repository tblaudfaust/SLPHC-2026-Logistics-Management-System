import uuid
from datetime import date as date_type

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.asset import Asset, AssetTransfer, AssetTransferItem
from app.models.location import Location
from app.services import asset_service


def _require_warehouse(db: Session, location_id: uuid.UUID) -> Location:
    location = db.get(Location, location_id)
    if not location or not location.warehouse:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Unknown or non-warehouse location_id.")
    return location


def dispatch_asset_transfer(
    db: Session,
    *,
    asset_ids: list[uuid.UUID],
    from_warehouse_id: uuid.UUID,
    to_warehouse_id: uuid.UUID,
    expected_delivery_date: date_type,
    released_by_name: str,
    reason: str | None,
    performed_by_id: uuid.UUID | None,
) -> AssetTransfer:
    """Phase 1 of 2. Flips each picked asset to IN_TRANSIT immediately —
    its current_location_id is left unchanged until receive_asset_transfer()
    confirms arrival, matching how a manually-triggered IN_TRANSIT status
    change already behaves (brief §9.2: neither at its old nor new location
    while moving)."""
    if from_warehouse_id == to_warehouse_id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Source and destination warehouses must differ.")
    _require_warehouse(db, from_warehouse_id)
    _require_warehouse(db, to_warehouse_id)

    assets = db.scalars(select(Asset).where(Asset.id.in_(asset_ids)).with_for_update()).all()
    missing = set(asset_ids) - {a.id for a in assets}
    if missing:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"{len(missing)} selected asset(s) could not be found.")

    for asset in assets:
        if asset.current_location_id != from_warehouse_id:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                f"{asset.asset_tag} is not currently at the selected source warehouse.",
            )
        if asset.status != "AVAILABLE":
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                f"{asset.asset_tag} is {asset.status}, not AVAILABLE — cannot transfer.",
            )

    transfer = AssetTransfer(
        from_warehouse_id=from_warehouse_id, to_warehouse_id=to_warehouse_id, status="IN_TRANSIT",
        expected_delivery_date=expected_delivery_date, released_by_name=released_by_name, reason=reason,
        dispatched_by_id=performed_by_id,
    )
    db.add(transfer)
    db.flush()

    for asset in assets:
        db.add(AssetTransferItem(asset_transfer_id=transfer.id, asset_id=asset.id))
        previous_status = asset.status
        asset.status = "IN_TRANSIT"
        asset_service.record_event(
            db, asset, event_type="transfer_dispatched", performed_by_id=performed_by_id,
            previous_status=previous_status, new_status="IN_TRANSIT",
            reason=reason or "Dispatched for inter-warehouse transfer",
        )
    db.flush()
    return transfer


def receive_asset_transfer(
    db: Session, *, transfer: AssetTransfer, received_by_name: str, performed_by_id: uuid.UUID | None,
) -> AssetTransfer:
    """Phase 2 — moves every picked asset to the destination and closes out
    the transfer's accountability."""
    if transfer.status == "RECEIVED":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "This transfer has already been received.")

    for item in transfer.items:
        asset = item.asset
        previous_location_id = asset.current_location_id
        previous_status = asset.status
        asset.current_location_id = transfer.to_warehouse_id
        asset.status = "AVAILABLE"
        asset_service.record_event(
            db, asset, event_type="transfer_received", performed_by_id=performed_by_id,
            previous_status=previous_status, new_status="AVAILABLE",
            previous_location_id=previous_location_id, new_location_id=transfer.to_warehouse_id,
            reason="Received via inter-warehouse transfer",
        )

    transfer.status = "RECEIVED"
    transfer.received_by_name = received_by_name
    transfer.received_by_id = performed_by_id
    transfer.actual_delivery_date = date_type.today()
    db.flush()
    return transfer
