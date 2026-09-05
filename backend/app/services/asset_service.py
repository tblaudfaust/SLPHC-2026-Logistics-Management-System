import uuid
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.asset import Asset, AssetCategory, AssetStatusEvent
from app.schemas.asset import BulkImportRow, BulkImportRowError
from app.services import audit_service

MAX_REPORTED_ERRORS = 200
"""Cap on how many row errors a bulk-import response lists individually —
invalid_count is still the true total even when the list is truncated, so a
25,000-row file with widespread bad data doesn't blow up the response."""

# Valid forward/side transitions. Anything not listed here is rejected — this
# is the code-level enforcement of brief §18 rules like "a lost asset cannot
# be available for assignment" / "a damaged asset cannot be reassigned until
# repaired, inspected and returned to an available state".
ALLOWED_STATUS_TRANSITIONS: dict[str, set[str]] = {
    "AVAILABLE": {"ALLOCATED", "IN_TRANSIT", "ASSIGNED", "UNDER_MAINTENANCE", "DAMAGED", "LOST", "DISPOSED"},
    "ALLOCATED": {"AVAILABLE", "IN_TRANSIT", "ASSIGNED", "DAMAGED", "LOST"},
    "IN_TRANSIT": {"AVAILABLE", "ALLOCATED", "ASSIGNED", "DAMAGED", "LOST"},
    "ASSIGNED": {"RETURNED", "DAMAGED", "LOST"},
    "RETURNED": {"AVAILABLE", "UNDER_MAINTENANCE", "DAMAGED", "DISPOSED"},
    "UNDER_MAINTENANCE": {"AVAILABLE", "DAMAGED", "DISPOSED"},
    "DAMAGED": {"UNDER_MAINTENANCE", "DISPOSED"},
    "LOST": {"DISPOSED"},
    "DISPOSED": set(),
}


def generate_asset_tag(db: Session, category: AssetCategory) -> str:
    """Locks the category row so concurrent registrations never collide on the
    same sequence number (brief §6.1 Asset ID convention)."""
    locked = db.execute(
        select(AssetCategory).where(AssetCategory.id == category.id).with_for_update()
    ).scalar_one()
    locked.next_sequence += 1
    db.flush()
    return f"SLPHC26-{locked.code_prefix}-{locked.next_sequence:06d}"


def record_event(
    db: Session,
    asset: Asset,
    *,
    event_type: str,
    performed_by_id: uuid.UUID | None,
    previous_status: str | None = None,
    new_status: str | None = None,
    previous_location_id: uuid.UUID | None = None,
    new_location_id: uuid.UUID | None = None,
    previous_custodian_id: uuid.UUID | None = None,
    new_custodian_id: uuid.UUID | None = None,
    condition: str | None = None,
    reason: str | None = None,
) -> AssetStatusEvent:
    event = AssetStatusEvent(
        asset_id=asset.id,
        event_type=event_type,
        performed_by_id=performed_by_id,
        previous_status=previous_status,
        new_status=new_status,
        previous_location_id=previous_location_id,
        new_location_id=new_location_id,
        previous_custodian_id=previous_custodian_id,
        new_custodian_id=new_custodian_id,
        condition=condition,
        reason=reason,
        created_at=datetime.now(timezone.utc),
    )
    db.add(event)
    return event


def change_status(
    db: Session,
    asset: Asset,
    *,
    new_status: str,
    performed_by_id: uuid.UUID | None,
    reason: str | None,
    ip_address: str | None,
    user_agent: str | None,
) -> Asset:
    allowed = ALLOWED_STATUS_TRANSITIONS.get(asset.status, set())
    if new_status not in allowed:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"Cannot move an asset from {asset.status} to {new_status}.",
        )

    previous_status = asset.status
    asset.status = new_status
    record_event(
        db, asset, event_type="status_change", performed_by_id=performed_by_id,
        previous_status=previous_status, new_status=new_status, reason=reason,
    )
    audit_service.record(
        db, user_id=performed_by_id, action="status_change", entity_type="asset", entity_id=str(asset.id),
        old_value={"status": previous_status}, new_value={"status": new_status}, reason=reason,
        ip_address=ip_address, user_agent=user_agent,
    )
    return asset


def validate_bulk_rows(
    db: Session, *, rows: list[BulkImportRow]
) -> tuple[list[BulkImportRow], list[BulkImportRowError]]:
    """Checks required fields, duplicates *within the uploaded file*, and
    duplicates against assets already in the register (brief §19.1: 'show
    rows uploaded, valid records, invalid records, duplicates ... before
    committing an import'). Read-only — makes no DB changes."""
    errors: list[BulkImportRowError] = []
    seen_serials: dict[str, int] = {}
    seen_imeis: dict[str, int] = {}
    candidates: list[BulkImportRow] = []

    for row in rows:
        if not row.serial_number and not row.imei_1:
            errors.append(BulkImportRowError(
                row_number=row.row_number, serial_number=row.serial_number,
                reason="Missing both serial number and IMEI — at least one is required.",
            ))
            continue
        if row.serial_number and row.serial_number in seen_serials:
            errors.append(BulkImportRowError(
                row_number=row.row_number, serial_number=row.serial_number,
                reason=f"Duplicate serial number — also on row {seen_serials[row.serial_number]} in this file.",
            ))
            continue
        if row.imei_1 and row.imei_1 in seen_imeis:
            errors.append(BulkImportRowError(
                row_number=row.row_number, serial_number=row.serial_number,
                reason=f"Duplicate IMEI — also on row {seen_imeis[row.imei_1]} in this file.",
            ))
            continue
        if row.serial_number:
            seen_serials[row.serial_number] = row.row_number
        if row.imei_1:
            seen_imeis[row.imei_1] = row.row_number
        candidates.append(row)

    existing_serials: set[str] = set()
    existing_imeis: set[str] = set()
    serials_to_check = [r.serial_number for r in candidates if r.serial_number]
    imeis_to_check = [r.imei_1 for r in candidates if r.imei_1]
    if serials_to_check:
        existing_serials = set(
            db.scalars(select(Asset.serial_number).where(Asset.serial_number.in_(serials_to_check))).all()
        )
    if imeis_to_check:
        existing_imeis = set(
            db.scalars(select(Asset.imei_1).where(Asset.imei_1.in_(imeis_to_check))).all()
        )

    valid_rows: list[BulkImportRow] = []
    for row in candidates:
        if row.serial_number and row.serial_number in existing_serials:
            errors.append(BulkImportRowError(
                row_number=row.row_number, serial_number=row.serial_number,
                reason="Serial number already registered in the asset register.",
            ))
            continue
        if row.imei_1 and row.imei_1 in existing_imeis:
            errors.append(BulkImportRowError(
                row_number=row.row_number, serial_number=row.serial_number,
                reason="IMEI already registered in the asset register.",
            ))
            continue
        valid_rows.append(row)

    errors.sort(key=lambda e: e.row_number)
    return valid_rows, errors


def bulk_register_assets(
    db: Session,
    *,
    category: AssetCategory,
    model_id: uuid.UUID | None,
    current_location_id: uuid.UUID | None,
    supplier_id: uuid.UUID | None,
    procurement_id: uuid.UUID | None,
    rows: list[BulkImportRow],
    performed_by_id: uuid.UUID | None,
) -> list[Asset]:
    """Reserves a contiguous block of the category's sequence in one locked
    update (not one lock+update per row — the difference between a couple of
    queries and tens of thousands for a 25,000-row import) then bulk-creates
    the Asset and registration-event rows."""
    locked = db.execute(
        select(AssetCategory).where(AssetCategory.id == category.id).with_for_update()
    ).scalar_one()
    start_sequence = locked.next_sequence + 1
    locked.next_sequence += len(rows)

    now = datetime.now(timezone.utc)
    assets: list[Asset] = []
    events: list[AssetStatusEvent] = []
    for offset, row in enumerate(rows):
        asset_tag = f"SLPHC26-{locked.code_prefix}-{start_sequence + offset:06d}"
        asset = Asset(
            asset_tag=asset_tag,
            category_id=category.id,
            model_id=model_id,
            serial_number=row.serial_number,
            imei_1=row.imei_1,
            imei_2=row.imei_2,
            supplier_id=supplier_id,
            procurement_id=procurement_id,
            current_location_id=current_location_id,
            created_by_id=performed_by_id,
            remarks=f"Box {row.box_number}" if row.box_number else None,
        )
        assets.append(asset)
    db.add_all(assets)
    db.flush()  # assigns PKs so events below can reference asset.id

    for asset in assets:
        events.append(AssetStatusEvent(
            asset_id=asset.id, event_type="registered", performed_by_id=performed_by_id,
            new_status=asset.status, new_location_id=asset.current_location_id,
            condition=asset.condition, reason="Bulk import", created_at=now,
        ))
    db.add_all(events)
    db.flush()

    return assets
