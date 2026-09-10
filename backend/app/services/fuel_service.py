"""Fuel Management business logic. Vehicles/Generators are created the same
way starlink_service.create_kit creates a StarlinkKit — a paired Asset row
(physical side: asset_tag, status, location, condition) plus this module's
own extension row (vehicle/generator-specific fields). Every other fuel
entity (allocation, request, approval, issue, receipt, voucher, stock
ledger, reconciliation) is genuinely new.

Fuel efficiency: vehicle_efficiency() / generator_consumption_rate() per the
brief's own formulas (distance = current - previous odometer; efficiency =
distance / litres; operating_hours = current - previous hour-meter;
consumption_rate = litres / hours)."""

import uuid
from datetime import date as date_type, datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.asset import Asset, AssetCategory
from app.models.fuel import (
    FuelAllocation,
    FuelApproval,
    FuelIssue,
    FuelReceipt,
    FuelReconciliation,
    FuelRequest,
    FuelSequenceCounter,
    FuelStockTransaction,
    Generator,
    Vehicle,
)
from app.models.location import Region
from app.models.starlink import StarlinkKit
from app.services import asset_service, audit_service

VEHICLE_CATEGORY_NAME = "Vehicles"
GENERATOR_CATEGORY_NAME = "Generators"


def _get_or_create_category(db: Session, name: str, code_prefix: str) -> AssetCategory:
    category = db.scalar(select(AssetCategory).where(AssetCategory.name == name))
    if not category:
        category = AssetCategory(name=name, code_prefix=code_prefix, tracking_type="serialized")
        db.add(category)
        db.flush()
    return category


def generate_fuel_reference(db: Session, entity_type: str) -> str:
    """Collision-safe per-entity-type counter, mirroring
    asset_service.generate_asset_tag's SELECT...FOR UPDATE pattern (not
    starlink_service.next_sequence_code, which is non-locking)."""
    counter = db.scalar(
        select(FuelSequenceCounter).where(FuelSequenceCounter.entity_type == entity_type).with_for_update()
    )
    if not counter:
        counter = FuelSequenceCounter(entity_type=entity_type, next_sequence=0)
        db.add(counter)
        db.flush()
    counter.next_sequence += 1
    db.flush()
    return f"SLPHC-FUEL-2026-{entity_type[:3].upper()}-{counter.next_sequence:06d}"


# --------------------------------------------------------------------------
# Vehicles / Generators
# --------------------------------------------------------------------------

def create_vehicle(db: Session, *, payload, performed_by_id: uuid.UUID | None) -> Vehicle:
    category = _get_or_create_category(db, VEHICLE_CATEGORY_NAME, "VEH")
    asset_tag = asset_service.generate_asset_tag(db, category)
    asset = Asset(
        asset_tag=asset_tag, category_id=category.id, condition=payload.condition,
        current_location_id=payload.current_location_id, created_by_id=performed_by_id,
    )
    db.add(asset)
    db.flush()
    asset_service.record_event(
        db, asset, event_type="registered", performed_by_id=performed_by_id,
        new_status=asset.status, new_location_id=asset.current_location_id,
        condition=asset.condition, reason="Vehicle registered",
    )

    vehicle = Vehicle(
        asset_id=asset.id, registration_number=payload.registration_number, vehicle_type=payload.vehicle_type,
        make=payload.make, model=payload.model, fuel_type=payload.fuel_type, tank_capacity=payload.tank_capacity,
        assigned_driver_name=payload.assigned_driver_name, current_odometer=payload.current_odometer,
    )
    db.add(vehicle)
    db.flush()

    audit_service.record(
        db, user_id=performed_by_id, action="create", entity_type="vehicle", entity_id=str(vehicle.id),
        new_value={"asset_tag": asset_tag, "registration_number": payload.registration_number},
    )
    return vehicle


def create_generator(db: Session, *, payload, performed_by_id: uuid.UUID | None) -> Generator:
    category = _get_or_create_category(db, GENERATOR_CATEGORY_NAME, "GEN")
    asset_tag = asset_service.generate_asset_tag(db, category)
    asset = Asset(
        asset_tag=asset_tag, category_id=category.id, condition=payload.condition,
        current_location_id=payload.current_location_id, created_by_id=performed_by_id,
    )
    db.add(asset)
    db.flush()
    asset_service.record_event(
        db, asset, event_type="registered", performed_by_id=performed_by_id,
        new_status=asset.status, new_location_id=asset.current_location_id,
        condition=asset.condition, reason="Generator registered",
    )

    generator = Generator(
        asset_id=asset.id, capacity_kva=payload.capacity_kva, fuel_type=payload.fuel_type,
        current_hour_meter=payload.current_hour_meter,
    )
    db.add(generator)
    db.flush()

    audit_service.record(
        db, user_id=performed_by_id, action="create", entity_type="generator", entity_id=str(generator.id),
        new_value={"asset_tag": asset_tag},
    )
    return generator


# --------------------------------------------------------------------------
# Fuel efficiency (brief formulas)
# --------------------------------------------------------------------------

def vehicle_efficiency(previous_odometer: int, current_odometer: int, litres_consumed: float) -> dict:
    distance = max(current_odometer - previous_odometer, 0)
    efficiency = (distance / litres_consumed) if litres_consumed else None
    return {"distance_travelled": distance, "fuel_efficiency": efficiency}


def generator_consumption_rate(previous_hour_meter: float, current_hour_meter: float, litres_consumed: float) -> dict:
    hours = max(current_hour_meter - previous_hour_meter, 0)
    rate = (litres_consumed / hours) if hours else None
    return {"operating_hours": hours, "consumption_rate": rate}


# --------------------------------------------------------------------------
# Allocations
# --------------------------------------------------------------------------

def allocation_committed_litres(db: Session, allocation_id: uuid.UUID) -> dict:
    """Litres requested/approved/issued so far against one allocation —
    rejected requests don't count against it. Used both to render the
    allocation's own summary and to enforce brief rule #2 ('requested
    quantity cannot automatically exceed available allocation')."""
    requests = db.scalars(
        select(FuelRequest).where(
            FuelRequest.allocation_id == allocation_id, FuelRequest.status != "REJECTED"
        )
    ).all()
    requested = sum(float(r.quantity_requested) for r in requests)
    approved = 0.0
    issued = 0.0
    for r in requests:
        final = next((a for a in r.approvals if a.approval_level == 2 and a.decision == "APPROVED"), None)
        if final and final.approved_quantity is not None:
            approved += float(final.approved_quantity)
    issue_stmt = (
        select(func.coalesce(func.sum(FuelIssue.quantity_issued), 0))
        .join(FuelRequest, FuelIssue.fuel_request_id == FuelRequest.id)
        .where(FuelRequest.allocation_id == allocation_id)
    )
    issued = float(db.scalar(issue_stmt) or 0)
    return {"requested": requested, "approved": approved, "issued": issued}


def check_allocation_balance(db: Session, allocation: FuelAllocation, additional_litres: float) -> None:
    committed = allocation_committed_litres(db, allocation.id)
    remaining = float(allocation.allocated_litres) - committed["requested"]
    if additional_litres > remaining:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"Requested quantity ({additional_litres}L) exceeds the remaining balance on "
            f"{allocation.allocation_reference} ({remaining}L of {allocation.allocated_litres}L left).",
        )


# --------------------------------------------------------------------------
# Requests
# --------------------------------------------------------------------------

def create_request(db: Session, *, payload, requester_id: uuid.UUID) -> FuelRequest:
    """Brief rule #1/#2: created directly as SUBMITTED (no separate draft-
    editing flow this phase — DRAFT stays a valid status value for future
    use) and blocked from exceeding its allocation's remaining balance."""
    if payload.asset_type == "VEHICLE" and not payload.vehicle_id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "vehicle_id is required when asset_type is VEHICLE.")
    if payload.asset_type == "GENERATOR" and not payload.generator_id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "generator_id is required when asset_type is GENERATOR.")
    if payload.asset_type == "STARLINK" and not payload.starlink_kit_id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "starlink_kit_id is required when asset_type is STARLINK.")
    if payload.asset_type == "VEHICLE" and payload.current_odometer is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "current_odometer is required for a vehicle request.")
    if payload.asset_type == "GENERATOR" and payload.operating_hours is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "operating_hours is required for a generator request.")
    if payload.vehicle_id and not db.get(Vehicle, payload.vehicle_id):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Unknown vehicle_id.")
    if payload.generator_id and not db.get(Generator, payload.generator_id):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Unknown generator_id.")
    if payload.starlink_kit_id and not db.get(StarlinkKit, payload.starlink_kit_id):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Unknown starlink_kit_id.")

    allocation = None
    if payload.allocation_id:
        allocation = db.get(FuelAllocation, payload.allocation_id)
        if not allocation:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Unknown allocation_id.")
        check_allocation_balance(db, allocation, float(payload.quantity_requested))

    reference = generate_fuel_reference(db, "request")
    request = FuelRequest(
        request_reference=reference, requester_id=requester_id, region_id=payload.region_id,
        district_id=payload.district_id, activity_id=payload.activity_id, allocation_id=payload.allocation_id,
        asset_type=payload.asset_type, vehicle_id=payload.vehicle_id, generator_id=payload.generator_id,
        starlink_kit_id=payload.starlink_kit_id, fuel_type=payload.fuel_type,
        quantity_requested=payload.quantity_requested, purpose=payload.purpose, destination=payload.destination,
        date_required=payload.date_required, current_odometer=payload.current_odometer,
        expected_distance=payload.expected_distance, operating_hours=payload.operating_hours,
        status="SUBMITTED",
    )
    db.add(request)
    db.flush()

    audit_service.record(
        db, user_id=requester_id, action="submit", entity_type="fuel_request", entity_id=str(request.id),
        new_value={"reference": reference, "quantity_requested": float(payload.quantity_requested)},
    )
    return request


def decide_approval(
    db: Session, *, request: FuelRequest, approver_id: uuid.UUID, approval_level: int, payload,
) -> FuelApproval:
    """approval_level 1 = Director review (SUBMITTED -> UNDER_REVIEW or
    REJECTED); 2 = final authorization by the Statistician General or Deputy
    Statistician General (UNDER_REVIEW -> APPROVED or REJECTED). Enforced
    strictly in order — level 2 cannot be recorded before level 1."""
    if payload.decision not in ("APPROVED", "REJECTED"):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "decision must be APPROVED or REJECTED.")

    if approval_level == 1:
        if request.status != "SUBMITTED":
            raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Request is {request.status}, not SUBMITTED.")
    elif approval_level == 2:
        if request.status != "UNDER_REVIEW":
            raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Request is {request.status}, not UNDER_REVIEW.")
    else:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "approval_level must be 1 or 2.")

    if payload.decision == "APPROVED":
        if payload.approved_quantity is None:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "approved_quantity is required to approve.")
        if payload.approved_quantity > float(request.quantity_requested):
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST, "Approved quantity cannot exceed the requested quantity."
            )

    approval = FuelApproval(
        fuel_request_id=request.id, approver_id=approver_id, approval_level=approval_level,
        requested_quantity=request.quantity_requested,
        approved_quantity=payload.approved_quantity if payload.decision == "APPROVED" else None,
        decision=payload.decision, comments=payload.comments,
    )
    db.add(approval)

    if payload.decision == "REJECTED":
        request.status = "REJECTED"
    elif approval_level == 1:
        request.status = "UNDER_REVIEW"
    else:
        request.status = "APPROVED"

    db.flush()
    audit_service.record(
        db, user_id=approver_id, action="approve" if payload.decision == "APPROVED" else "reject",
        entity_type="fuel_request", entity_id=str(request.id),
        new_value={"approval_level": approval_level, "decision": payload.decision, "new_status": request.status},
        reason=payload.comments,
    )
    return approval


# --------------------------------------------------------------------------
# Issuance / Receipt
# --------------------------------------------------------------------------

def issue_fuel(db: Session, *, request: FuelRequest, payload, issued_by_id: uuid.UUID) -> FuelIssue:
    """Brief rule #4: issued quantity cannot exceed approved quantity (no
    additional-authorization override built this phase — a request needing
    more than its final approval would need a fresh request instead)."""
    if request.status != "APPROVED":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Request is {request.status}, not APPROVED.")
    final_approval = next(
        (a for a in request.approvals if a.approval_level == 2 and a.decision == "APPROVED"), None
    )
    if not final_approval or final_approval.approved_quantity is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "No final approval found for this request.")
    approved_quantity = float(final_approval.approved_quantity)
    if payload.quantity_issued > approved_quantity:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"Issued quantity ({payload.quantity_issued}L) cannot exceed the approved quantity ({approved_quantity}L).",
        )

    total_cost = (payload.price_per_litre * payload.quantity_issued) if payload.price_per_litre else None
    reference = generate_fuel_reference(db, "issue")
    issue = FuelIssue(
        issue_reference=reference, fuel_request_id=request.id, supplier_id=payload.supplier_id,
        fuel_station_id=payload.fuel_station_id, quantity_approved=approved_quantity,
        quantity_issued=payload.quantity_issued, price_per_litre=payload.price_per_litre, total_cost=total_cost,
        voucher_number=payload.voucher_number, issued_by_id=issued_by_id, witness_name=payload.witness_name,
        issue_date=payload.issue_date, odometer_reading=payload.odometer_reading, comments=payload.comments,
    )
    db.add(issue)
    db.flush()

    db.add(FuelStockTransaction(
        depot_location_id=payload.depot_location_id, fuel_type=request.fuel_type, transaction_type="ISSUE",
        quantity=-payload.quantity_issued, reference_type="fuel_issue", reference_id=str(issue.id),
        performed_by_id=issued_by_id,
    ))

    # odometer_reading is the single shared "reading at issuance" field —
    # kilometres for a vehicle, hour-meter hours for a generator — and
    # becomes the new baseline the *next* request's distance/hours diff is
    # computed from (see vehicle_efficiency/generator_consumption_rate).
    # Previously this branch used request.operating_hours (the requester's
    # *expected* hours) to bump the generator's hour-meter at issue time,
    # which double-counted against whatever reconciliation later recorded.
    if payload.odometer_reading is not None:
        if request.asset_type == "VEHICLE" and request.vehicle:
            request.vehicle.current_odometer = payload.odometer_reading
        elif request.asset_type == "GENERATOR" and request.generator:
            request.generator.current_hour_meter = payload.odometer_reading

    request.status = "ISSUED"
    db.flush()

    audit_service.record(
        db, user_id=issued_by_id, action="issue", entity_type="fuel_request", entity_id=str(request.id),
        new_value={"issue_reference": reference, "quantity_issued": payload.quantity_issued},
    )
    return issue


def acknowledge_receipt(db: Session, *, issue: FuelIssue, payload, receiver_id: uuid.UUID) -> FuelReceipt:
    if issue.request.status != "ISSUED":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Request is {issue.request.status}, not ISSUED.")

    receipt = FuelReceipt(
        fuel_issue_id=issue.id, receiver_id=receiver_id, quantity_received=payload.quantity_received,
        date_received=payload.date_received, receipt_number=payload.receipt_number,
        acknowledgement=payload.acknowledgement, attachment=payload.attachment, remarks=payload.remarks,
    )
    db.add(receipt)
    issue.request.status = "RECEIVED"
    db.flush()

    audit_service.record(
        db, user_id=receiver_id, action="acknowledge_receipt", entity_type="fuel_issue", entity_id=str(issue.id),
        new_value={"quantity_received": payload.quantity_received, "acknowledgement": payload.acknowledgement},
    )
    return receipt


def reconcile_issue(db: Session, *, issue: FuelIssue, payload, reconciled_by_id: uuid.UUID) -> FuelReconciliation:
    if issue.request.status != "RECEIVED":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Request is {issue.request.status}, not RECEIVED.")

    balance = None
    if payload.quantity_used is not None:
        balance = float(issue.quantity_issued) - float(payload.quantity_used)

    reconciliation = FuelReconciliation(
        fuel_issue_id=issue.id, reconciled_by_id=reconciled_by_id, quantity_issued=issue.quantity_issued,
        quantity_used=payload.quantity_used, balance=balance, distance_travelled=payload.distance_travelled,
        hours_operated=payload.hours_operated, comments=payload.comments,
        reconciliation_date=payload.reconciliation_date,
    )
    db.add(reconciliation)
    issue.request.status = "RECONCILED"
    db.flush()

    audit_service.record(
        db, user_id=reconciled_by_id, action="reconcile", entity_type="fuel_issue", entity_id=str(issue.id),
        new_value={"quantity_used": payload.quantity_used, "balance": balance},
    )
    return reconciliation


# --------------------------------------------------------------------------
# Stock ledger
# --------------------------------------------------------------------------

def record_stock_receipt(db: Session, *, payload, performed_by_id: uuid.UUID | None) -> FuelStockTransaction:
    row = FuelStockTransaction(
        depot_location_id=payload.depot_location_id, fuel_type=payload.fuel_type, transaction_type="RECEIPT",
        quantity=payload.quantity, reference_type="fuel_supplier", reference_id=str(payload.supplier_id) if payload.supplier_id else None,
        remarks=payload.remarks, performed_by_id=performed_by_id,
    )
    db.add(row)
    db.flush()
    audit_service.record(
        db, user_id=performed_by_id, action="receipt", entity_type="fuel_stock", entity_id=str(row.id),
        new_value={"depot_location_id": str(payload.depot_location_id), "quantity": payload.quantity},
    )
    return row


def record_stock_adjustment(db: Session, *, payload, performed_by_id: uuid.UUID | None) -> FuelStockTransaction:
    row = FuelStockTransaction(
        depot_location_id=payload.depot_location_id, fuel_type=payload.fuel_type, transaction_type="ADJUSTMENT",
        quantity=payload.quantity_delta, remarks=payload.reason, performed_by_id=performed_by_id,
    )
    db.add(row)
    db.flush()
    audit_service.record(
        db, user_id=performed_by_id, action="adjust", entity_type="fuel_stock", entity_id=str(row.id),
        new_value={"depot_location_id": str(payload.depot_location_id), "quantity_delta": payload.quantity_delta},
        reason=payload.reason,
    )
    return row


def get_fuel_stock_balances(db: Session) -> list[dict]:
    from app.models.location import Location

    stmt = (
        select(
            FuelStockTransaction.depot_location_id, Location.name.label("depot_name"),
            FuelStockTransaction.fuel_type, func.sum(FuelStockTransaction.quantity).label("quantity_on_hand"),
        )
        .join(Location, FuelStockTransaction.depot_location_id == Location.id)
        .group_by(FuelStockTransaction.depot_location_id, Location.name, FuelStockTransaction.fuel_type)
        .order_by(Location.name, FuelStockTransaction.fuel_type)
    )
    return [
        {
            "depot_location_id": row.depot_location_id, "depot_name": row.depot_name,
            "fuel_type": row.fuel_type, "quantity_on_hand": float(row.quantity_on_hand or 0),
        }
        for row in db.execute(stmt).all()
    ]


# --------------------------------------------------------------------------
# Dashboard
# --------------------------------------------------------------------------

def dashboard_summary(db: Session) -> dict:
    total_allocated = float(db.scalar(select(func.coalesce(func.sum(FuelAllocation.allocated_litres), 0))) or 0)
    total_requested = float(
        db.scalar(
            select(func.coalesce(func.sum(FuelRequest.quantity_requested), 0))
            .where(FuelRequest.status != "REJECTED")
        ) or 0
    )

    approved_rows = db.execute(
        select(FuelApproval.approved_quantity).where(FuelApproval.approval_level == 2, FuelApproval.decision == "APPROVED")
    ).all()
    total_approved = sum(float(r[0]) for r in approved_rows if r[0] is not None)

    total_issued = float(db.scalar(select(func.coalesce(func.sum(FuelIssue.quantity_issued), 0))) or 0)
    total_received = float(db.scalar(select(func.coalesce(func.sum(FuelReceipt.quantity_received), 0))) or 0)
    total_consumed = float(
        db.scalar(select(func.coalesce(func.sum(FuelReconciliation.quantity_used), 0))) or 0
    )
    total_expenditure = float(db.scalar(select(func.coalesce(func.sum(FuelIssue.total_cost), 0))) or 0)

    pending_requests = db.scalar(select(func.count()).select_from(FuelRequest).where(FuelRequest.status == "SUBMITTED")) or 0
    pending_approvals = db.scalar(
        select(func.count()).select_from(FuelRequest).where(FuelRequest.status == "UNDER_REVIEW")
    ) or 0
    unreconciled = db.scalar(
        select(func.count()).select_from(FuelRequest).where(FuelRequest.status == "RECEIVED")
    ) or 0

    active_vehicles = db.scalar(
        select(func.count()).select_from(Vehicle).join(Asset, Vehicle.asset_id == Asset.id)
        .where(Asset.status != "DISPOSED")
    ) or 0
    active_generators = db.scalar(
        select(func.count()).select_from(Generator).join(Asset, Generator.asset_id == Asset.id)
        .where(Asset.status != "DISPOSED")
    ) or 0
    active_starlink_teams = db.scalar(
        select(func.count(func.distinct(StarlinkKit.current_field_team_id)))
        .where(StarlinkKit.current_field_team_id.is_not(None))
    ) or 0

    consumption_by_region = [
        {"region": row.name, "litres_issued": float(row.total or 0)}
        for row in db.execute(
            select(Region.name, func.sum(FuelIssue.quantity_issued).label("total"))
            .select_from(FuelIssue)
            .join(FuelRequest, FuelIssue.fuel_request_id == FuelRequest.id)
            .join(Region, FuelRequest.region_id == Region.id)
            .group_by(Region.name)
            .order_by(Region.name)
        ).all()
    ]

    allocation_vs_consumption = [
        {
            "allocation_reference": a.allocation_reference, "allocated": float(a.allocated_litres),
            "issued": allocation_committed_litres(db, a.id)["issued"],
        }
        for a in db.scalars(select(FuelAllocation).order_by(FuelAllocation.created_at.desc()).limit(10)).all()
    ]

    return {
        "total_allocated_litres": total_allocated, "total_requested_litres": total_requested,
        "total_approved_litres": total_approved, "total_issued_litres": total_issued,
        "total_received_litres": total_received, "total_consumed_litres": total_consumed,
        "remaining_balance_litres": total_allocated - total_issued,
        "total_expenditure": total_expenditure, "pending_requests": pending_requests,
        "pending_approvals": pending_approvals, "unreconciled_transactions": unreconciled,
        "active_vehicles": active_vehicles, "active_generators": active_generators,
        "active_starlink_teams": active_starlink_teams,
        "consumption_by_region": consumption_by_region,
        "allocation_vs_consumption": allocation_vs_consumption,
    }
