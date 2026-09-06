import uuid
from datetime import date, datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.asset import Asset, AssetCategory
from app.models.starlink import (
    FieldTeam,
    HardToReachArea,
    StarlinkCheckin,
    StarlinkComponent,
    StarlinkFault,
    StarlinkInstallation,
    StarlinkKit,
    StarlinkMovement,
    StarlinkReturn,
    StarlinkSubscription,
    StarlinkSubscriptionPayment,
    StarlinkTeamAssignment,
)
from app.services import asset_service, audit_service

STARLINK_CATEGORY_NAME = "Starlink Kits"


def get_starlink_category(db: Session) -> AssetCategory:
    category = db.scalar(select(AssetCategory).where(AssetCategory.name == STARLINK_CATEGORY_NAME))
    if not category:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f'Asset category "{STARLINK_CATEGORY_NAME}" is not seeded on this deployment.',
        )
    return category


def next_sequence_code(db: Session, model, column, prefix: str, width: int = 4) -> str:
    """Simple incrementing code for module-local entities (field teams, fault
    tickets) that don't need the category-locked concurrency guarantee
    generate_asset_tag gives the shared asset-tag sequence."""
    count = db.scalar(select(func.count()).select_from(model)) or 0
    return f"{prefix}-{count + 1:0{width}d}"


def create_kit(
    db: Session,
    *,
    payload,
    performed_by_id: uuid.UUID | None,
) -> StarlinkKit:
    """A Starlink kit is always both an Asset row (physical side) and a
    StarlinkKit row (connectivity side), created together in one
    transaction — see starlink.py's module docstring for why they're split
    this way instead of duplicating Asset's columns."""
    category = get_starlink_category(db)
    asset_tag = asset_service.generate_asset_tag(db, category)

    asset = Asset(
        asset_tag=asset_tag,
        category_id=category.id,
        model_id=payload.model_id,
        serial_number=payload.serial_number,
        supplier_id=payload.supplier_id,
        procurement_id=payload.procurement_id,
        supplier_or_donor=payload.supplier_or_donor,
        purchase_order_ref=payload.purchase_order_ref,
        date_acquired=payload.date_acquired,
        date_received=payload.date_received,
        unit_cost=payload.unit_cost,
        currency=payload.currency,
        warranty_start=payload.warranty_start,
        warranty_end=payload.warranty_end,
        current_location_id=payload.current_location_id,
        condition=payload.condition,
        created_by_id=performed_by_id,
        remarks=payload.remarks,
    )
    db.add(asset)
    db.flush()

    asset_service.record_event(
        db, asset, event_type="registered", performed_by_id=performed_by_id,
        new_status=asset.status, new_location_id=asset.current_location_id,
        condition=asset.condition, reason="Starlink kit registered",
    )

    kit = StarlinkKit(
        asset_id=asset.id,
        kit_type=payload.kit_type,
        terminal_id=payload.terminal_id,
        router_serial_number=payload.router_serial_number,
        funding_source_id=payload.funding_source_id,
    )
    db.add(kit)
    db.flush()

    for comp in payload.components:
        db.add(StarlinkComponent(
            kit_id=kit.id, component_name=comp.component_name,
            quantity=comp.quantity, condition=comp.condition, notes=comp.notes,
        ))

    audit_service.record(
        db, user_id=performed_by_id, action="create", entity_type="starlink_kit", entity_id=str(kit.id),
        new_value={"asset_tag": asset_tag, "kit_type": payload.kit_type},
    )
    db.flush()
    return kit


def record_installation(db, kit: StarlinkKit, payload, performed_by_id) -> StarlinkInstallation:
    installation = StarlinkInstallation(
        kit_id=kit.id,
        installation_type=payload.installation_type,
        location_id=payload.location_id,
        gps_latitude=payload.gps_latitude,
        gps_longitude=payload.gps_longitude,
        installation_date=payload.installation_date,
        technician_name=payload.technician_name,
        installation_company=payload.installation_company,
        mounting_method=payload.mounting_method,
        power_source=payload.power_source,
        backup_power_available=payload.backup_power_available,
        installation_cost=payload.installation_cost,
        router_installed=payload.router_installed,
        connectivity_tested=payload.connectivity_tested,
        download_speed_mbps=payload.download_speed_mbps,
        upload_speed_mbps=payload.upload_speed_mbps,
        latency_ms=payload.latency_ms,
        installed_by_id=performed_by_id,
        verified_by_id=payload.verified_by_id,
        acceptance_status=payload.acceptance_status,
        remarks=payload.remarks,
    )
    db.add(installation)

    kit.installation_status = "TESTED" if payload.connectivity_tested else "INSTALLED"
    kit.operational_status = "INSTALLED_OPERATIONAL" if payload.connectivity_tested else kit.operational_status
    if payload.location_id:
        kit.asset.current_location_id = payload.location_id

    audit_service.record(
        db, user_id=performed_by_id, action="install", entity_type="starlink_kit", entity_id=str(kit.id),
        new_value={"installation_type": payload.installation_type, "connectivity_tested": payload.connectivity_tested},
    )
    db.flush()
    return installation


def create_subscription(db, kit: StarlinkKit, payload, performed_by_id) -> StarlinkSubscription:
    db.execute(
        StarlinkSubscription.__table__.update()
        .where(StarlinkSubscription.kit_id == kit.id, StarlinkSubscription.is_current.is_(True))
        .values(is_current=False)
    )
    subscription = StarlinkSubscription(
        kit_id=kit.id,
        account_reference=payload.account_reference,
        plan_name=payload.plan_name,
        subscription_type=payload.subscription_type,
        activation_date=payload.activation_date,
        subscription_start_date=payload.subscription_start_date,
        billing_cycle=payload.billing_cycle,
        monthly_cost=payload.monthly_cost,
        annual_estimated_cost=payload.annual_estimated_cost,
        currency=payload.currency,
        next_payment_date=payload.next_payment_date,
        renewal_date=payload.renewal_date,
        expiry_date=payload.expiry_date,
        status=payload.status,
        responsible_officer_id=payload.responsible_officer_id,
        is_current=True,
        remarks=payload.remarks,
    )
    db.add(subscription)
    kit.subscription_status = payload.status

    audit_service.record(
        db, user_id=performed_by_id, action="create", entity_type="starlink_subscription", entity_id=str(kit.id),
        new_value={"plan_name": payload.plan_name, "status": payload.status},
    )
    db.flush()
    return subscription


def record_payment(db, subscription: StarlinkSubscription, payload, performed_by_id) -> StarlinkSubscriptionPayment:
    payment = StarlinkSubscriptionPayment(
        subscription_id=subscription.id,
        payment_date=payload.payment_date,
        amount=payload.amount,
        currency=payload.currency or subscription.currency,
        payment_reference=payload.payment_reference,
        payment_status=payload.payment_status,
        recorded_by_id=performed_by_id,
        remarks=payload.remarks,
    )
    db.add(payment)
    subscription.last_payment_date = payload.payment_date
    if subscription.status in ("PAYMENT_DUE", "PAYMENT_OVERDUE") and payload.payment_status == "PAID":
        subscription.status = "ACTIVE"
        subscription.kit.subscription_status = "ACTIVE"
    db.flush()
    return payment


def assign_to_team(db, kit: StarlinkKit, payload, current_user) -> StarlinkTeamAssignment:
    if kit.kit_type != "ROAMING":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Only roaming kits can be assigned to a field team.")

    active = db.scalar(
        select(StarlinkTeamAssignment).where(
            StarlinkTeamAssignment.kit_id == kit.id, StarlinkTeamAssignment.status == "ACTIVE"
        )
    )
    if active:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "This kit already has an active field team assignment — return it before reassigning.",
        )

    assignment = StarlinkTeamAssignment(
        kit_id=kit.id,
        field_team_id=payload.field_team_id,
        region_id=payload.region_id,
        district_id=payload.district_id,
        chiefdom=payload.chiefdom,
        section=payload.section,
        locality=payload.locality,
        enumeration_area=payload.enumeration_area,
        field_location=payload.field_location,
        hard_to_reach_area_id=payload.hard_to_reach_area_id,
        assignment_purpose=payload.assignment_purpose,
        deployment_start_date=payload.deployment_start_date,
        expected_return_date=payload.expected_return_date,
        released_by_name=current_user.full_name,
        witnessed_by_name=payload.witnessed_by_name,
        equipment_condition_at_release=payload.equipment_condition_at_release,
        status="ACTIVE",
        remarks=payload.remarks,
        created_by_id=current_user.id,
    )
    db.add(assignment)

    kit.current_field_team_id = payload.field_team_id
    kit.current_hard_to_reach_area_id = payload.hard_to_reach_area_id
    kit.operational_status = "FIELD_OPERATIONAL"
    kit.asset.status = "ASSIGNED" if kit.asset.status in ("AVAILABLE", "ALLOCATED") else kit.asset.status

    asset_service.record_event(
        db, kit.asset, event_type="starlink_team_assignment", performed_by_id=current_user.id,
        new_status=kit.asset.status, new_custodian_id=None, reason=f"Deployed to field team {payload.field_team_id}",
    )
    audit_service.record(
        db, user_id=current_user.id, action="assign_team", entity_type="starlink_kit", entity_id=str(kit.id),
        new_value={"field_team_id": str(payload.field_team_id)},
    )
    db.flush()
    return assignment


def return_from_team(db, assignment: StarlinkTeamAssignment, payload, current_user) -> StarlinkReturn:
    if assignment.status != "ACTIVE":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "This assignment has already been closed.")

    kit = assignment.kit
    assignment.status = "RETURNED"
    assignment.actual_return_date = payload.return_date
    assignment.received_by_name = current_user.full_name

    conditions = [payload.dish_condition, payload.router_condition, payload.power_supply_condition]
    final_condition = "DAMAGED" if "DAMAGED" in conditions or payload.damaged_accessories else (
        "POOR" if "POOR" in conditions else "GOOD"
    )

    ret = StarlinkReturn(
        assignment_id=assignment.id,
        kit_id=kit.id,
        returned_by_name=assignment.released_by_name,
        received_by_name=current_user.full_name,
        witnessed_by_name=payload.witnessed_by_name,
        return_date=payload.return_date,
        dish_condition=payload.dish_condition,
        router_condition=payload.router_condition,
        power_supply_condition=payload.power_supply_condition,
        missing_accessories=payload.missing_accessories,
        damaged_accessories=payload.damaged_accessories,
        subscription_status_at_return=kit.subscription_status,
        final_condition=final_condition,
        reassignment_required=payload.reassignment_required,
        maintenance_required=payload.maintenance_required,
        remarks=payload.remarks,
    )
    db.add(ret)

    kit.current_field_team_id = None
    kit.current_hard_to_reach_area_id = None
    kit.operational_status = "UNDER_MAINTENANCE" if payload.maintenance_required else "NOT_DEPLOYED"
    kit.asset.status = "UNDER_MAINTENANCE" if payload.maintenance_required else "AVAILABLE"
    kit.asset.condition = final_condition if final_condition != "GOOD" else kit.asset.condition

    asset_service.record_event(
        db, kit.asset, event_type="starlink_team_return", performed_by_id=current_user.id,
        new_status=kit.asset.status, condition=kit.asset.condition,
        reason=f"Returned from field team assignment {assignment.id}",
    )
    audit_service.record(
        db, user_id=current_user.id, action="return_team", entity_type="starlink_kit", entity_id=str(kit.id),
        new_value={"final_condition": final_condition, "missing_accessories": payload.missing_accessories},
    )
    db.flush()
    return ret


def record_movement(db, kit: StarlinkKit, payload, current_user) -> StarlinkMovement:
    origin_id = kit.asset.current_location_id
    movement = StarlinkMovement(
        kit_id=kit.id,
        origin_location_id=origin_id,
        destination_location_id=payload.destination_location_id,
        from_custodian_id=kit.asset.current_custodian_id,
        to_custodian_id=payload.to_custodian_id,
        field_team_id=payload.field_team_id,
        transfer_date=payload.transfer_date,
        purpose=payload.purpose,
        released_by_name=current_user.full_name,
        witnessed_by_name=payload.witnessed_by_name,
        condition_at_release=payload.condition_at_release,
        condition_at_receipt=payload.condition_at_receipt,
        accessories_issued=payload.accessories_issued,
        accessories_received=payload.accessories_received,
        remarks=payload.remarks,
        performed_by_id=current_user.id,
    )
    db.add(movement)

    if payload.destination_location_id:
        kit.asset.current_location_id = payload.destination_location_id
    if payload.to_custodian_id:
        kit.asset.current_custodian_id = payload.to_custodian_id

    asset_service.record_event(
        db, kit.asset, event_type="starlink_movement", performed_by_id=current_user.id,
        previous_location_id=origin_id, new_location_id=kit.asset.current_location_id,
        new_custodian_id=kit.asset.current_custodian_id, reason=payload.purpose,
    )
    audit_service.record(
        db, user_id=current_user.id, action="move", entity_type="starlink_kit", entity_id=str(kit.id),
        old_value={"location_id": str(origin_id) if origin_id else None},
        new_value={"location_id": str(payload.destination_location_id) if payload.destination_location_id else None},
    )
    db.flush()
    return movement


def record_checkin(db, payload, current_user) -> tuple[StarlinkCheckin, list]:
    """Returns (checkin, notifications) — the caller must call
    notification_service.dispatch(notifications) only after committing, so a
    Celery task is never enqueued for a Notification row that didn't survive
    the transaction (same rule every other notify() call site in this
    codebase follows)."""
    kit = db.get(StarlinkKit, payload.kit_id)
    if not kit:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Starlink kit not found.")

    checkin = StarlinkCheckin(
        kit_id=payload.kit_id,
        field_team_id=kit.current_field_team_id,
        checkin_at=payload.checkin_at or datetime.now(timezone.utc),
        region_id=payload.region_id,
        district_id=payload.district_id,
        chiefdom_section=payload.chiefdom_section,
        current_location=payload.current_location,
        gps_latitude=payload.gps_latitude,
        gps_longitude=payload.gps_longitude,
        starlink_available=payload.starlink_available,
        starlink_operational=payload.starlink_operational,
        internet_available=payload.internet_available,
        power_available=payload.power_available,
        equipment_condition=payload.equipment_condition,
        connectivity_quality=payload.connectivity_quality,
        technical_problem=payload.technical_problem,
        technical_support_required=payload.technical_support_required,
        comment=payload.comment,
        submitted_by_id=current_user.id,
    )
    db.add(checkin)

    kit.last_connectivity_quality = payload.connectivity_quality
    kit.last_checkin_at = checkin.checkin_at
    kit.operational_status = "FIELD_OPERATIONAL" if payload.starlink_operational else "FIELD_OFFLINE"

    audit_service.record(
        db, user_id=current_user.id, action="checkin", entity_type="starlink_kit", entity_id=str(kit.id),
        new_value={"connectivity_quality": payload.connectivity_quality, "operational": payload.starlink_operational},
    )

    # Real-time alerts (not the hourly scan) — a field team offline or asking
    # for help shouldn't wait up to an hour to page anyone. Only *added* to
    # the session here; dispatch happens in the router after it commits.
    from app.services import notification_service

    location_label = payload.current_location or "an unspecified location"
    notifications: list = []
    if payload.technical_support_required:
        notifications = notification_service.notify(
            db, event_type="starlink.support_requested",
            context={
                "asset_tag": kit.asset.asset_tag, "location_label": location_label,
                "technical_problem": payload.technical_problem or "Not specified",
            },
            recipients=notification_service.get_users_with_permission(db, "starlink.maintenance"),
            related_entity_type="starlink_kit", related_entity_id=str(kit.id),
        )
    elif not payload.starlink_operational:
        notifications = notification_service.notify(
            db, event_type="starlink.offline_reported",
            context={
                "asset_tag": kit.asset.asset_tag, "kit_type": kit.kit_type, "location_label": location_label,
                "checkin_at": checkin.checkin_at.isoformat(), "connectivity_quality": payload.connectivity_quality,
            },
            recipients=notification_service.get_users_with_permission(db, "starlink.assign"),
            related_entity_type="starlink_kit", related_entity_id=str(kit.id),
        )

    db.flush()
    return checkin, notifications


def create_fault(db, kit: StarlinkKit, payload, current_user) -> StarlinkFault:
    ticket_number = next_sequence_code(db, StarlinkFault, StarlinkFault.ticket_number, "FLT")
    fault = StarlinkFault(
        ticket_number=ticket_number,
        kit_id=kit.id,
        date_reported=payload.date_reported,
        reported_by_id=current_user.id,
        current_location_id=kit.asset.current_location_id,
        fault_description=payload.fault_description,
        fault_category=payload.fault_category,
        priority=payload.priority,
        status="REPORTED",
    )
    db.add(fault)
    db.flush()  # assigns fault.id before the audit entry below reads it
    kit.operational_status = "UNDER_MAINTENANCE"
    kit.asset.status = "UNDER_MAINTENANCE" if kit.asset.status not in ("DAMAGED", "LOST", "DISPOSED") else kit.asset.status

    audit_service.record(
        db, user_id=current_user.id, action="create", entity_type="starlink_fault", entity_id=str(fault.id),
        new_value={"ticket_number": ticket_number, "priority": payload.priority},
    )
    db.flush()
    return fault


def update_fault(db, fault: StarlinkFault, payload, current_user) -> StarlinkFault:
    old_status = fault.status
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(fault, field, value)

    if payload.status == "RESOLVED" and old_status != "RESOLVED":
        fault.resolved_by_id = current_user.id
        if fault.date_resolved is None:
            fault.date_resolved = date.today()
        fault.kit.operational_status = "NOT_DEPLOYED" if fault.kit.kit_type == "ROAMING" else "INSTALLED_OPERATIONAL"
        fault.kit.asset.status = "AVAILABLE"

    audit_service.record(
        db, user_id=current_user.id, action="update", entity_type="starlink_fault", entity_id=str(fault.id),
        old_value={"status": old_status}, new_value={"status": fault.status},
    )
    db.flush()
    return fault


def dashboard_summary(db: Session) -> dict:
    kits = db.scalars(select(StarlinkKit)).all()
    total = len(kits)
    fixed = sum(1 for k in kits if k.kit_type == "FIXED")
    roaming = total - fixed
    deployed = sum(1 for k in kits if k.operational_status in ("FIELD_OPERATIONAL", "FIELD_OFFLINE", "INSTALLED_OPERATIONAL", "INSTALLED_OFFLINE"))
    under_maintenance = sum(1 for k in kits if k.operational_status == "UNDER_MAINTENANCE")
    damaged_or_lost = sum(1 for k in kits if k.asset.status in ("DAMAGED", "LOST"))
    available = sum(1 for k in kits if k.operational_status == "NOT_DEPLOYED" and k.asset.status == "AVAILABLE")

    installed = sum(1 for k in kits if k.installation_status in ("INSTALLED", "TESTED", "OPERATIONAL"))
    awaiting_installation = sum(1 for k in kits if k.installation_status == "NOT_INSTALLED")
    installed_and_operational = sum(1 for k in kits if k.operational_status == "INSTALLED_OPERATIONAL")
    installed_but_offline = sum(1 for k in kits if k.operational_status == "INSTALLED_OFFLINE")

    online = sum(1 for k in kits if k.operational_status in ("FIELD_OPERATIONAL", "INSTALLED_OPERATIONAL"))
    offline = sum(1 for k in kits if k.operational_status in ("FIELD_OFFLINE", "INSTALLED_OFFLINE"))
    support_requested = db.scalar(
        select(func.count()).select_from(StarlinkCheckin).where(StarlinkCheckin.technical_support_required.is_(True))
    ) or 0

    today = date.today()
    current_subs = db.scalars(select(StarlinkSubscription).where(StarlinkSubscription.is_current.is_(True))).all()
    active_subs = sum(1 for s in current_subs if s.status == "ACTIVE")
    expiring_30 = sum(1 for s in current_subs if s.expiry_date and today <= s.expiry_date <= today + timedelta(days=30))
    expiring_14 = sum(1 for s in current_subs if s.expiry_date and today <= s.expiry_date <= today + timedelta(days=14))
    expiring_7 = sum(1 for s in current_subs if s.expiry_date and today <= s.expiry_date <= today + timedelta(days=7))
    expired = sum(1 for s in current_subs if s.status == "EXPIRED" or (s.expiry_date and s.expiry_date < today))
    payments_overdue = sum(1 for s in current_subs if s.status == "PAYMENT_OVERDUE")

    active_assignments = db.scalars(
        select(StarlinkTeamAssignment).where(StarlinkTeamAssignment.status == "ACTIVE")
    ).all()
    roaming_assigned = len(active_assignments)
    in_hard_to_reach = sum(1 for a in active_assignments if a.hard_to_reach_area_id)
    hard_to_reach_with = sum(
        1 for a in active_assignments
        if a.hard_to_reach_area_id and a.kit.operational_status == "FIELD_OPERATIONAL"
    )
    hard_to_reach_without = in_hard_to_reach - hard_to_reach_with
    overdue = sum(1 for a in active_assignments if a.expected_return_date < today)

    starlink_required_areas = set(
        db.scalars(
            select(HardToReachArea.id).where(HardToReachArea.starlink_required.is_(True))
        ).all()
    )
    assigned_area_ids = {a.hard_to_reach_area_id for a in active_assignments if a.hard_to_reach_area_id}
    gap = len(starlink_required_areas - assigned_area_ids)

    return {
        "total_kits": total, "fixed_kits": fixed, "roaming_kits": roaming,
        "available_kits": available, "deployed_kits": deployed,
        "under_maintenance_kits": under_maintenance, "damaged_or_lost_kits": damaged_or_lost,
        "installed": installed, "awaiting_installation": awaiting_installation,
        "installed_and_operational": installed_and_operational, "installed_but_offline": installed_but_offline,
        "subscriptions_active": active_subs, "subscriptions_expiring_30d": expiring_30,
        "subscriptions_expiring_14d": expiring_14, "subscriptions_expiring_7d": expiring_7,
        "subscriptions_expired": expired, "payments_overdue": payments_overdue,
        "roaming_assigned_to_teams": roaming_assigned, "teams_in_hard_to_reach_areas": in_hard_to_reach,
        "hard_to_reach_with_connectivity": hard_to_reach_with, "hard_to_reach_without_connectivity": hard_to_reach_without,
        "kits_overdue_for_return": overdue, "hard_to_reach_gap": gap,
        "online_kits": online, "offline_kits": offline, "support_requested": support_requested,
    }
