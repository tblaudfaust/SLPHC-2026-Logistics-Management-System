"""Detailed accountability reporting (brief §14). Every report is produced as
one common shape — columns + rows of already-formatted display strings — so
one generic PDF/Excel/CSV renderer and one generic frontend table cover all
of them, instead of a bespoke template per report. Reports are read-only
projections over existing data; none of them create or mutate anything.

Scoped to what the system actually has data for today (Phases 1-3 plus
notifications and two-phase stock transfers) — the brief's full 22-report
list also covers shipments, field assignment, Starlink and witnesses, none
of which exist yet. Add a new entry to REPORT_DEFINITIONS + a query function
below as each later phase lands; the export/email plumbing needs no changes."""

import csv
import io
from dataclasses import dataclass, field
from datetime import date, datetime, time, timezone
from pathlib import Path

from fastapi import HTTPException, status
from openpyxl import Workbook
from openpyxl.styles import Font
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models.asset import Asset, AssetCategory, AssetStatusEvent
from app.models.audit_log import AuditLog
from app.models.inventory import GoodsReceipt, InventoryTransaction, StockTransfer
from app.models.location import Location
from app.models.notification import Notification
from app.models.user import User

LOGO_PATH = Path(__file__).resolve().parent.parent / "assets" / "statistics_sl_logo.jpg"

ORG_ADDRESS_LINES = [
    "Statistics Sierra Leone (Stats SL)",
    "A.J. Momoh Street / Tower Hill, P.M.B. 595, Freetown, Sierra Leone",
    "E: info@statistics.sl  ·  T: +232-78-208595 / 30-593333  ·  W: www.statistics.sl",
]


def _draw_pdf_footer(canvas, doc) -> None:
    canvas.saveState()
    canvas.setFont("Helvetica", 7)
    canvas.setFillColor(colors.HexColor("#64748b"))
    width, _ = doc.pagesize
    y = 1.0 * cm
    for line in reversed(ORG_ADDRESS_LINES):
        canvas.drawCentredString(width / 2, y, line)
        y += 0.32 * cm
    canvas.drawRightString(width - 1.5 * cm, 1.0 * cm, f"Page {canvas.getPageNumber()}")
    canvas.restoreState()

ROW_LIMIT = 2000


@dataclass
class ReportResult:
    report_id: str
    title: str
    columns: list[tuple[str, str]]  # (key, label)
    rows: list[dict] = field(default_factory=list)
    truncated: bool = False


def _dt_range(date_from: date | None, date_to: date | None) -> tuple[datetime, datetime]:
    start = datetime.combine(date_from or date(2000, 1, 1), time.min, tzinfo=timezone.utc)
    end = datetime.combine(date_to or date.today(), time.max, tzinfo=timezone.utc)
    return start, end


def _cap(rows: list) -> tuple[list, bool]:
    if len(rows) > ROW_LIMIT:
        return rows[:ROW_LIMIT], True
    return rows, False


# --------------------------------------------------------------------------
# Report definitions — id -> (name, description, filter keys, query function)
# --------------------------------------------------------------------------

def _report_warehouse_accountability(db: Session, f: dict) -> ReportResult:
    start, end = _dt_range(f.get("date_from"), f.get("date_to"))

    opening_stmt = select(
        InventoryTransaction.warehouse_id, InventoryTransaction.category_id,
        func.sum(InventoryTransaction.quantity).label("qty"),
    ).where(InventoryTransaction.created_at < start).group_by(
        InventoryTransaction.warehouse_id, InventoryTransaction.category_id
    )
    period_stmt = select(
        InventoryTransaction.warehouse_id, InventoryTransaction.category_id,
        InventoryTransaction.transaction_type,
        func.sum(InventoryTransaction.quantity).label("qty"),
    ).where(InventoryTransaction.created_at >= start, InventoryTransaction.created_at <= end).group_by(
        InventoryTransaction.warehouse_id, InventoryTransaction.category_id, InventoryTransaction.transaction_type
    )
    if f.get("warehouse_id"):
        opening_stmt = opening_stmt.where(InventoryTransaction.warehouse_id == f["warehouse_id"])
        period_stmt = period_stmt.where(InventoryTransaction.warehouse_id == f["warehouse_id"])
    if f.get("category_id"):
        opening_stmt = opening_stmt.where(InventoryTransaction.category_id == f["category_id"])
        period_stmt = period_stmt.where(InventoryTransaction.category_id == f["category_id"])

    buckets: dict[tuple, dict] = {}

    def _bucket(warehouse_id, category_id):
        key = (warehouse_id, category_id)
        return buckets.setdefault(
            key, {"opening": 0, "receipts": 0, "transfers_in": 0, "transfers_out": 0, "adjustments": 0, "other": 0}
        )

    for row in db.execute(opening_stmt).all():
        _bucket(row.warehouse_id, row.category_id)["opening"] = row.qty or 0

    for row in db.execute(period_stmt).all():
        b = _bucket(row.warehouse_id, row.category_id)
        if row.transaction_type == "RECEIPT":
            b["receipts"] += row.qty or 0
        elif row.transaction_type == "TRANSFER_IN":
            b["transfers_in"] += row.qty or 0
        elif row.transaction_type == "TRANSFER_OUT":
            b["transfers_out"] += row.qty or 0
        elif row.transaction_type == "ADJUSTMENT":
            b["adjustments"] += row.qty or 0
        else:
            b["other"] += row.qty or 0

    if not buckets:
        return ReportResult("warehouse_accountability", "Warehouse Accountability Report", _WAREHOUSE_COLUMNS, [])

    warehouse_ids = {k[0] for k in buckets}
    category_ids = {k[1] for k in buckets}
    warehouses = {loc.id: loc.name for loc in db.scalars(select(Location).where(Location.id.in_(warehouse_ids)))}
    categories = {c.id: c.name for c in db.scalars(select(AssetCategory).where(AssetCategory.id.in_(category_ids)))}

    rows = []
    for (warehouse_id, category_id), b in buckets.items():
        closing = b["opening"] + b["receipts"] + b["transfers_in"] - b["transfers_out"] + b["adjustments"] + b["other"]
        rows.append({
            "warehouse": warehouses.get(warehouse_id, "Unknown"),
            "category": categories.get(category_id, "Unknown"),
            "opening_stock": b["opening"],
            "receipts": b["receipts"],
            "transfers_in": b["transfers_in"],
            "transfers_out": -b["transfers_out"] if b["transfers_out"] else 0,
            "adjustments": b["adjustments"] + b["other"],
            "closing_stock": closing,
        })
    rows.sort(key=lambda r: (r["warehouse"], r["category"]))
    rows, truncated = _cap(rows)
    return ReportResult("warehouse_accountability", "Warehouse Accountability Report", _WAREHOUSE_COLUMNS, rows, truncated)


_WAREHOUSE_COLUMNS = [
    ("warehouse", "Warehouse"), ("category", "Category"), ("opening_stock", "Opening Stock"),
    ("receipts", "Receipts"), ("transfers_in", "Transfers In"), ("transfers_out", "Transfers Out"),
    ("adjustments", "Adjustments"), ("closing_stock", "Closing Stock"),
]


def _report_goods_receipt(db: Session, f: dict) -> ReportResult:
    start, end = _dt_range(f.get("date_from"), f.get("date_to"))
    stmt = (
        select(GoodsReceipt)
        .options(selectinload(GoodsReceipt.warehouse), selectinload(GoodsReceipt.supplier))
        .where(GoodsReceipt.receipt_date >= start.date(), GoodsReceipt.receipt_date <= end.date())
        .order_by(GoodsReceipt.receipt_date.desc())
    )
    if f.get("warehouse_id"):
        stmt = stmt.where(GoodsReceipt.warehouse_id == f["warehouse_id"])
    receipts = db.scalars(stmt.limit(ROW_LIMIT + 1)).all()
    receipts, truncated = _cap(list(receipts))

    items_by_receipt: dict[str, list[InventoryTransaction]] = {}
    if receipts:
        receipt_ids = [str(r.id) for r in receipts]
        item_rows = db.scalars(
            select(InventoryTransaction)
            .options(selectinload(InventoryTransaction.category))
            .where(InventoryTransaction.reference_type == "goods_receipt", InventoryTransaction.reference_id.in_(receipt_ids))
        ).all()
        for item in item_rows:
            items_by_receipt.setdefault(item.reference_id, []).append(item)

    rows = [
        {
            "date": r.receipt_date.isoformat(),
            "warehouse": r.warehouse.name,
            "supplier": r.supplier.name if r.supplier else "Unregistered / unknown",
            "received_by": r.received_by_name,
            "delivered_by": r.delivered_by_name or "-",
            "items": "; ".join(f"{i.category.name}: +{i.quantity}" for i in items_by_receipt.get(str(r.id), [])),
            "remarks": r.remarks or "",
        }
        for r in receipts
    ]
    columns = [
        ("date", "Date"), ("warehouse", "Warehouse"), ("supplier", "Supplier"),
        ("received_by", "Received By"), ("delivered_by", "Delivered By"),
        ("items", "Items Received"), ("remarks", "Remarks"),
    ]
    return ReportResult("goods_receipt", "Asset Receipt Report", columns, rows, truncated)


def _report_stock_transfer(db: Session, f: dict) -> ReportResult:
    start, end = _dt_range(f.get("date_from"), f.get("date_to"))
    stmt = (
        select(StockTransfer)
        .options(
            selectinload(StockTransfer.category), selectinload(StockTransfer.from_warehouse),
            selectinload(StockTransfer.to_warehouse),
        )
        .where(StockTransfer.created_at >= start, StockTransfer.created_at <= end)
        .order_by(StockTransfer.created_at.desc())
    )
    if f.get("warehouse_id"):
        stmt = stmt.where(
            (StockTransfer.from_warehouse_id == f["warehouse_id"]) | (StockTransfer.to_warehouse_id == f["warehouse_id"])
        )
    if f.get("category_id"):
        stmt = stmt.where(StockTransfer.category_id == f["category_id"])
    if f.get("status"):
        stmt = stmt.where(StockTransfer.status == f["status"])
    transfers = db.scalars(stmt.limit(ROW_LIMIT + 1)).all()
    transfers, truncated = _cap(list(transfers))

    rows = [
        {
            "category": t.category.name,
            "from_warehouse": t.from_warehouse.name,
            "to_warehouse": t.to_warehouse.name,
            "quantity": t.quantity,
            "status": "OVERDUE" if t.is_overdue else t.status,
            "expected_delivery_date": t.expected_delivery_date.isoformat(),
            "actual_delivery_date": t.actual_delivery_date.isoformat() if t.actual_delivery_date else "-",
            "released_by": t.released_by_name,
            "received_by": t.received_by_name or "-",
            "reason": t.reason or "",
        }
        for t in transfers
    ]
    columns = [
        ("category", "Category"), ("from_warehouse", "From"), ("to_warehouse", "To"), ("quantity", "Qty"),
        ("status", "Status"), ("expected_delivery_date", "Expected"), ("actual_delivery_date", "Delivered"),
        ("released_by", "Released By"), ("received_by", "Received By"), ("reason", "Reason"),
    ]
    return ReportResult("stock_transfer_accountability", "Stock Transfer Accountability Report", columns, rows, truncated)


def _report_asset_status(db: Session, f: dict) -> ReportResult:
    stmt = select(Asset).options(
        selectinload(Asset.category), selectinload(Asset.current_location), selectinload(Asset.current_custodian)
    )
    if f.get("category_id"):
        stmt = stmt.where(Asset.category_id == f["category_id"])
    if f.get("status"):
        stmt = stmt.where(Asset.status == f["status"])
    if f.get("warehouse_id"):
        stmt = stmt.where(Asset.current_location_id == f["warehouse_id"])
    stmt = stmt.order_by(Asset.asset_tag)
    assets = db.scalars(stmt.limit(ROW_LIMIT + 1)).all()
    assets, truncated = _cap(list(assets))

    rows = [
        {
            "asset_tag": a.asset_tag,
            "category": a.category.name,
            "serial_number": a.serial_number or a.imei_1 or "-",
            "status": a.status,
            "condition": a.condition,
            "location": a.current_location.name if a.current_location else "-",
            "custodian": a.current_custodian.full_name if a.current_custodian else "-",
            "last_updated": a.updated_at.strftime("%Y-%m-%d %H:%M") if a.updated_at else "-",
        }
        for a in assets
    ]
    columns = [
        ("asset_tag", "Asset ID"), ("category", "Category"), ("serial_number", "Serial / IMEI"),
        ("status", "Status"), ("condition", "Condition"), ("location", "Current Location"),
        ("custodian", "Current Custodian"), ("last_updated", "Last Updated"),
    ]
    return ReportResult("asset_status", "Detailed Item Status Report", columns, rows, truncated)


def _report_asset_chain_of_custody(db: Session, f: dict) -> ReportResult:
    asset_id = f.get("asset_id")
    if not asset_id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "asset_id is required for this report.")
    asset = db.get(Asset, asset_id)
    if not asset:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Asset not found.")

    events = db.scalars(
        select(AssetStatusEvent)
        .options(selectinload(AssetStatusEvent.performed_by))
        .where(AssetStatusEvent.asset_id == asset_id)
        .order_by(AssetStatusEvent.created_at.asc())
    ).all()

    location_ids = {e.previous_location_id for e in events if e.previous_location_id} | {
        e.new_location_id for e in events if e.new_location_id
    }
    locations = {loc.id: loc.name for loc in db.scalars(select(Location).where(Location.id.in_(location_ids)))} if location_ids else {}

    user_ids = {e.previous_custodian_id for e in events if e.previous_custodian_id} | {
        e.new_custodian_id for e in events if e.new_custodian_id
    }
    users = {u.id: u.full_name for u in db.scalars(select(User).where(User.id.in_(user_ids)))} if user_ids else {}

    rows = [
        {
            "date": e.created_at.strftime("%Y-%m-%d %H:%M"),
            "event": e.event_type,
            "status_change": (
                f"{e.previous_status or '-'} -> {e.new_status}" if e.new_status else "-"
            ),
            "location_change": (
                f"{locations.get(e.previous_location_id, '-')} -> {locations.get(e.new_location_id, '-')}"
                if e.new_location_id else "-"
            ),
            "custodian_change": (
                f"{users.get(e.previous_custodian_id, '-')} -> {users.get(e.new_custodian_id, '-')}"
                if e.new_custodian_id else "-"
            ),
            "condition": e.condition or "-",
            "reason": e.reason or "-",
            "performed_by": e.performed_by.full_name if e.performed_by else "System",
        }
        for e in events
    ]
    columns = [
        ("date", "Date/Time"), ("event", "Event"), ("status_change", "Status Change"),
        ("location_change", "Location Change"), ("custodian_change", "Custodian Change"),
        ("condition", "Condition"), ("reason", "Reason"), ("performed_by", "Performed By"),
    ]
    title = f"Asset Chain-of-Custody Report — {asset.asset_tag}"
    return ReportResult("asset_chain_of_custody", title, columns, rows, False)


def _report_unaccounted_assets(db: Session, f: dict) -> ReportResult:
    rows = []
    exception_assets = db.scalars(
        select(Asset)
        .options(selectinload(Asset.category), selectinload(Asset.current_location), selectinload(Asset.current_custodian))
        .where(Asset.status.in_(["LOST", "DAMAGED"]))
    ).all()
    for a in exception_assets:
        rows.append({
            "type": "Lost Asset" if a.status == "LOST" else "Damaged Asset",
            "reference": a.asset_tag,
            "category": a.category.name,
            "detail": (
                f"Last custodian: {a.current_custodian.full_name}" if a.current_custodian
                else (f"Last location: {a.current_location.name}" if a.current_location else "Unknown")
            ),
            "since": a.updated_at.strftime("%Y-%m-%d") if a.updated_at else "-",
            "notes": a.remarks or "",
        })

    overdue_transfers = db.scalars(
        select(StockTransfer)
        .options(
            selectinload(StockTransfer.category), selectinload(StockTransfer.from_warehouse),
            selectinload(StockTransfer.to_warehouse),
        )
        .where(StockTransfer.status == "IN_TRANSIT", StockTransfer.expected_delivery_date < date.today())
    ).all()
    for t in overdue_transfers:
        rows.append({
            "type": "Overdue Transfer",
            "reference": f"{t.quantity}x {t.category.name}",
            "category": t.category.name,
            "detail": f"{t.from_warehouse.name} -> {t.to_warehouse.name} (released by {t.released_by_name})",
            "since": t.expected_delivery_date.isoformat(),
            "notes": t.reason or "",
        })

    rows.sort(key=lambda r: r["since"])
    rows, truncated = _cap(rows)
    columns = [
        ("type", "Exception Type"), ("reference", "Reference"), ("category", "Category"),
        ("detail", "Detail"), ("since", "Since"), ("notes", "Notes"),
    ]
    return ReportResult("unaccounted_assets", "Unaccounted / Exception Assets Report", columns, rows, truncated)


def _report_audit_trail(db: Session, f: dict) -> ReportResult:
    start, end = _dt_range(f.get("date_from"), f.get("date_to"))
    stmt = select(AuditLog).where(AuditLog.created_at >= start, AuditLog.created_at <= end)
    if f.get("entity_type"):
        stmt = stmt.where(AuditLog.entity_type == f["entity_type"])
    if f.get("action"):
        stmt = stmt.where(AuditLog.action == f["action"])
    stmt = stmt.order_by(AuditLog.created_at.desc())
    entries = db.scalars(stmt.limit(ROW_LIMIT + 1)).all()
    entries, truncated = _cap(list(entries))

    user_ids = {e.user_id for e in entries if e.user_id}
    users = {u.id: u.email for u in db.scalars(select(User).where(User.id.in_(user_ids)))} if user_ids else {}

    rows = [
        {
            "date": e.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            "user": users.get(e.user_id, "System") if e.user_id else "System",
            "action": e.action,
            "entity_type": e.entity_type,
            "entity_id": (e.entity_id or "")[:36],
            "ip_address": e.ip_address or "-",
            "reason": e.reason or "-",
        }
        for e in entries
    ]
    columns = [
        ("date", "Date/Time"), ("user", "User"), ("action", "Action"), ("entity_type", "Entity Type"),
        ("entity_id", "Entity ID"), ("ip_address", "IP Address"), ("reason", "Reason"),
    ]
    return ReportResult("audit_trail", "Full System Audit Report", columns, rows, truncated)


def _report_notification_delivery(db: Session, f: dict) -> ReportResult:
    start, end = _dt_range(f.get("date_from"), f.get("date_to"))
    stmt = select(Notification).where(Notification.created_at >= start, Notification.created_at <= end)
    if f.get("status"):
        stmt = stmt.where(Notification.status == f["status"])
    stmt = stmt.order_by(Notification.created_at.desc())
    entries = db.scalars(stmt.limit(ROW_LIMIT + 1)).all()
    entries, truncated = _cap(list(entries))

    rows = [
        {
            "date": e.created_at.strftime("%Y-%m-%d %H:%M"),
            "event_type": e.event_type,
            "channel": e.channel,
            "recipient": e.recipient_email,
            "subject": e.subject,
            "status": e.status,
            "sent_at": e.sent_at.strftime("%Y-%m-%d %H:%M") if e.sent_at else "-",
        }
        for e in entries
    ]
    columns = [
        ("date", "Created"), ("event_type", "Event"), ("channel", "Channel"), ("recipient", "Recipient"),
        ("subject", "Subject"), ("status", "Status"), ("sent_at", "Sent At"),
    ]
    return ReportResult("notification_delivery", "Notification Delivery Report", columns, rows, truncated)


REPORT_DEFINITIONS: dict[str, dict] = {
    "warehouse_accountability": {
        "name": "Warehouse Accountability Report",
        "description": "Opening stock, receipts, transfers and adjustments by warehouse and category over a date range.",
        "filters": ["date_from", "date_to", "warehouse_id", "category_id"],
        "fn": _report_warehouse_accountability,
    },
    "goods_receipt": {
        "name": "Asset Receipt Report",
        "description": "Goods received into a warehouse, with supplier, receiving officer and delivery details.",
        "filters": ["date_from", "date_to", "warehouse_id"],
        "fn": _report_goods_receipt,
    },
    "stock_transfer_accountability": {
        "name": "Stock Transfer Accountability Report",
        "description": "Warehouse-to-warehouse transfers with releasing/receiving officers, dates and overdue status.",
        "filters": ["date_from", "date_to", "warehouse_id", "category_id", "status"],
        "fn": _report_stock_transfer,
    },
    "asset_status": {
        "name": "Detailed Item Status / Current Custody Report",
        "description": "One row per serialized asset: current status, condition, location and custodian.",
        "filters": ["category_id", "status", "warehouse_id"],
        "fn": _report_asset_status,
    },
    "asset_chain_of_custody": {
        "name": "Asset Chain-of-Custody Report",
        "description": "Complete lifetime history of a single selected asset.",
        "filters": ["asset_id"],
        "fn": _report_asset_chain_of_custody,
    },
    "unaccounted_assets": {
        "name": "Unaccounted / Exception Assets Report",
        "description": "Lost or damaged assets, plus stock transfers overdue past their expected delivery date.",
        "filters": [],
        "fn": _report_unaccounted_assets,
    },
    "audit_trail": {
        "name": "Full System Audit Report",
        "description": "Every recorded system action: user, action, affected record, IP address and time.",
        "filters": ["date_from", "date_to", "entity_type", "action"],
        "fn": _report_audit_trail,
    },
    "notification_delivery": {
        "name": "Notification Delivery Report",
        "description": "Email notification volume and delivery outcome (sent/failed/skipped) over a date range.",
        "filters": ["date_from", "date_to", "status"],
        "fn": _report_notification_delivery,
    },
}


def list_definitions() -> list[dict]:
    return [
        {"id": rid, "name": d["name"], "description": d["description"], "filters": d["filters"]}
        for rid, d in REPORT_DEFINITIONS.items()
    ]


def run_report(db: Session, report_id: str, filters: dict) -> ReportResult:
    definition = REPORT_DEFINITIONS.get(report_id)
    if not definition:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Unknown report: {report_id}")
    return definition["fn"](db, filters)


# --------------------------------------------------------------------------
# Export rendering — one generic renderer per format, shared by every report
# --------------------------------------------------------------------------

def render_pdf(result: ReportResult, *, generated_by: str, filters_applied: dict[str, str]) -> bytes:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=landscape(A4),
        leftMargin=1.5 * cm, rightMargin=1.5 * cm, topMargin=1.5 * cm, bottomMargin=2.3 * cm,
    )
    styles = getSampleStyleSheet()
    title_block = [
        Paragraph("Statistics Sierra Leone", styles["Heading2"]),
        Paragraph("SLPHC 2026 Logistics Command &amp; Asset Management System", styles["Normal"]),
        Paragraph(result.title, styles["Heading3"]),
    ]
    if LOGO_PATH.exists():
        logo = Image(str(LOGO_PATH), width=2.2 * cm, height=2.2 * cm)
        letterhead = Table([[logo, title_block]], colWidths=[2.6 * cm, None])
        letterhead.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (0, 0), 0),
        ]))
        elements = [letterhead]
    else:
        elements = list(title_block)
    elements.append(
        Paragraph(
            f"Generated {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')} by {generated_by}",
            styles["Normal"],
        )
    )
    if filters_applied:
        filter_text = " · ".join(f"{k}: {v}" for k, v in filters_applied.items())
        elements.append(Paragraph(f"Filters: {filter_text}", styles["Normal"]))
    if result.truncated:
        elements.append(Paragraph(f"Showing the first {ROW_LIMIT} rows — refine the filters to see fewer.", styles["Normal"]))
    elements.append(Spacer(1, 0.5 * cm))

    cell_style = styles["BodyText"]
    cell_style.fontSize = 8
    header_style = styles["BodyText"].clone("ReportHeader")
    header_style.fontSize = 8
    header_style.textColor = colors.HexColor("#0f172a")
    # Dark text on a light header fill, not white-on-navy: a printer or PDF
    # viewer set to skip background fills (a common default) would otherwise
    # leave white header text invisible on a plain white page.
    header = [Paragraph(f"<b>{label}</b>", header_style) for _, label in result.columns]
    data = [header]
    for row in result.rows:
        data.append([Paragraph(str(row.get(key, "")), cell_style) for key, _ in result.columns])

    table = Table(data, repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e2e8f0")),
        ("LINEBELOW", (0, 0), (-1, 0), 1, colors.HexColor("#1e3a5f")),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    elements.append(table)
    if not result.rows:
        elements.append(Spacer(1, 0.5 * cm))
        elements.append(Paragraph("No records match these filters.", styles["Normal"]))

    doc.build(elements, onFirstPage=_draw_pdf_footer, onLaterPages=_draw_pdf_footer)
    return buffer.getvalue()


def render_csv(result: ReportResult) -> bytes:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow([label for _, label in result.columns])
    for row in result.rows:
        writer.writerow([row.get(key, "") for key, _ in result.columns])
    return buffer.getvalue().encode("utf-8")


def render_xlsx(result: ReportResult) -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = result.title[:31] or "Report"
    ws.append([label for _, label in result.columns])
    for cell in ws[1]:
        cell.font = Font(bold=True)
    for row in result.rows:
        ws.append([row.get(key, "") for key, _ in result.columns])
    ws.oddFooter.center.text = " | ".join(ORG_ADDRESS_LINES)
    ws.oddFooter.center.size = 7
    buffer = io.BytesIO()
    wb.save(buffer)
    return buffer.getvalue()


EXPORT_MIME_TYPES = {
    "pdf": "application/pdf",
    "csv": "text/csv",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}


def render_export(result: ReportResult, fmt: str, *, generated_by: str, filters_applied: dict[str, str]) -> bytes:
    if fmt == "pdf":
        return render_pdf(result, generated_by=generated_by, filters_applied=filters_applied)
    if fmt == "csv":
        return render_csv(result)
    if fmt == "xlsx":
        return render_xlsx(result)
    raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Unsupported export format: {fmt}")
