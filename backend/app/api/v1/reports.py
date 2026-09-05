import uuid
from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.orm import Session

from app.api.deps import client_ip, client_user_agent, get_db, require_permission
from app.models.asset import Asset, AssetCategory
from app.models.location import Location
from app.models.user import User
from app.schemas.report import ReportDefinitionRead, ReportEmailRequest, ReportResultRead
from app.services import audit_service, notification_service, report_service

router = APIRouter(prefix="/reports", tags=["reports"])


def _collect_filters(
    date_from: date | None, date_to: date | None, warehouse_id: uuid.UUID | None,
    category_id: uuid.UUID | None, status_filter: str | None, asset_id: uuid.UUID | None,
    entity_type: str | None, action: str | None,
) -> dict:
    return {
        "date_from": date_from, "date_to": date_to, "warehouse_id": warehouse_id, "category_id": category_id,
        "status": status_filter, "asset_id": asset_id, "entity_type": entity_type, "action": action,
    }


def _readable_filters(db: Session, filters: dict) -> dict[str, str]:
    """Renders the raw filter dict (UUIDs and dates) as labels a human reads
    on a printed/emailed report, rather than bare IDs."""
    readable: dict[str, str] = {}
    if filters.get("date_from"):
        readable["From"] = filters["date_from"].isoformat()
    if filters.get("date_to"):
        readable["To"] = filters["date_to"].isoformat()
    if filters.get("warehouse_id"):
        loc = db.get(Location, filters["warehouse_id"])
        readable["Warehouse"] = loc.name if loc else str(filters["warehouse_id"])
    if filters.get("category_id"):
        cat = db.get(AssetCategory, filters["category_id"])
        readable["Category"] = cat.name if cat else str(filters["category_id"])
    if filters.get("status"):
        readable["Status"] = filters["status"]
    if filters.get("asset_id"):
        asset = db.get(Asset, filters["asset_id"])
        readable["Asset"] = asset.asset_tag if asset else str(filters["asset_id"])
    if filters.get("entity_type"):
        readable["Entity type"] = filters["entity_type"]
    if filters.get("action"):
        readable["Action"] = filters["action"]
    return readable


@router.get("", response_model=list[ReportDefinitionRead])
def list_reports(_=Depends(require_permission("reports.view"))):
    return report_service.list_definitions()


@router.get("/{report_id}", response_model=ReportResultRead)
def get_report(
    report_id: str,
    date_from: date | None = None,
    date_to: date | None = None,
    warehouse_id: uuid.UUID | None = None,
    category_id: uuid.UUID | None = None,
    status_filter: str | None = None,
    asset_id: uuid.UUID | None = None,
    entity_type: str | None = None,
    action: str | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("reports.view")),
):
    filters = _collect_filters(
        date_from, date_to, warehouse_id, category_id, status_filter, asset_id, entity_type, action
    )
    result = report_service.run_report(db, report_id, filters)
    return ReportResultRead(
        report_id=result.report_id, title=result.title, generated_at=datetime.now(timezone.utc),
        generated_by=current_user.full_name, filters_applied=_readable_filters(db, filters),
        columns=[{"key": k, "label": label} for k, label in result.columns],
        rows=result.rows, row_count=len(result.rows), truncated=result.truncated,
    )


@router.get("/{report_id}/export")
def export_report(
    report_id: str,
    format: str = "pdf",
    date_from: date | None = None,
    date_to: date | None = None,
    warehouse_id: uuid.UUID | None = None,
    category_id: uuid.UUID | None = None,
    status_filter: str | None = None,
    asset_id: uuid.UUID | None = None,
    entity_type: str | None = None,
    action: str | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("reports.view")),
):
    filters = _collect_filters(
        date_from, date_to, warehouse_id, category_id, status_filter, asset_id, entity_type, action
    )
    result = report_service.run_report(db, report_id, filters)
    content = report_service.render_export(
        result, format, generated_by=current_user.full_name, filters_applied=_readable_filters(db, filters)
    )
    mime_type = report_service.EXPORT_MIME_TYPES.get(format, "application/octet-stream")
    filename = f"{report_id}.{format}"
    return Response(
        content=content, media_type=mime_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/{report_id}/email")
def email_report(
    report_id: str,
    payload: ReportEmailRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("reports.view")),
):
    filters = _collect_filters(
        payload.date_from, payload.date_to,
        uuid.UUID(payload.warehouse_id) if payload.warehouse_id else None,
        uuid.UUID(payload.category_id) if payload.category_id else None,
        payload.status,
        uuid.UUID(payload.asset_id) if payload.asset_id else None,
        payload.entity_type, payload.action,
    )
    result = report_service.run_report(db, report_id, filters)
    filters_applied = _readable_filters(db, filters)
    content = report_service.render_export(
        result, payload.format, generated_by=current_user.full_name, filters_applied=filters_applied
    )
    mime_type = report_service.EXPORT_MIME_TYPES.get(payload.format, "application/octet-stream")
    filename = f"{report_id}.{payload.format}"

    filter_lines = "\n".join(f"- {k}: {v}" for k, v in filters_applied.items())
    body = (
        f"{result.title}\n\nGenerated by {current_user.full_name} on "
        f"{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}.\n"
        f"{len(result.rows)} row(s){' (truncated)' if result.truncated else ''}.\n"
        + (f"\nFilters applied:\n{filter_lines}\n" if filter_lines else "")
        + (f"\n{payload.message}\n" if payload.message else "")
        + "\nSee the attached file for the full report."
    )

    notifications = notification_service.send_direct_email(
        db, recipient_emails=payload.recipient_emails, subject=f"SLPHC 2026 Logistics — {result.title}",
        body=body, attachment=(filename, content, mime_type),
        related_entity_type="report", related_entity_id=report_id,
    )
    audit_service.record(
        db, user_id=current_user.id, action="email_report", entity_type="report", entity_id=report_id,
        new_value={"recipients": payload.recipient_emails, "format": payload.format, "filters": filters_applied},
        ip_address=client_ip(request), user_agent=client_user_agent(request),
    )
    db.commit()
    notification_service.dispatch(notifications)
    return {"detail": f"Report queued for delivery to {len(payload.recipient_emails)} recipient(s)."}
