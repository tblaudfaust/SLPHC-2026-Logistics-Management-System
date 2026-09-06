"""Idempotent seed script: run after `alembic upgrade head`.

Seeds the permission catalogue, the 14 roles from brief §4 with a starting
(read-heavy, refine later) permission grant per role, Sierra Leone's real
region/district hierarchy, the brief §3 asset category catalogue, a
District Office warehouse for each of the 16 districts, a Regional Store
warehouse for each of the 5 regions, the national Freetown Central Store,
and one bootstrap System Administrator user.

Usage: python seed.py  (inside the backend container / venv)
"""
from app.core.config import settings
from app.core.security import hash_password
from app.db.base import Base  # noqa: F401  (ensures all models are registered)
from app.db.session import SessionLocal
from app.models.asset import AssetCategory
from app.models.location import District, Location, LocationType, Region
from app.models.notification import NotificationTemplate
from app.models.rbac import Permission, Role
from app.models.user import User
from app.models.warehouse import Warehouse

PERMISSIONS = [
    ("users.view", "users", "View user accounts"),
    ("users.create", "users", "Create user accounts"),
    ("users.update", "users", "Edit user accounts"),
    ("users.delete", "users", "Deactivate/delete user accounts"),
    ("roles.view", "roles", "View roles and permissions"),
    ("roles.create", "roles", "Create roles"),
    ("roles.update", "roles", "Edit roles and their permissions"),
    ("roles.delete", "roles", "Delete non-system roles"),
    ("locations.view", "locations", "View administrative geography and facilities"),
    ("locations.manage", "locations", "Create/edit administrative geography and facilities"),
    ("warehouses.view", "warehouses", "View warehouses"),
    ("warehouses.manage", "warehouses", "Create/edit warehouses"),
    ("audit.view", "audit", "View system audit logs"),
    ("dashboard.view", "dashboard", "View the executive dashboard"),
    ("assets.view", "assets", "View the asset register and asset profiles"),
    ("assets.create", "assets", "Register new assets"),
    ("assets.update", "assets", "Edit assets and change their status"),
    ("assets.manage_catalogue", "assets", "Manage asset categories and models"),
    ("suppliers.view", "suppliers", "View suppliers and donors"),
    ("suppliers.manage", "suppliers", "Create/edit suppliers and donors"),
    ("procurements.view", "procurements", "View procurement batches/purchase orders"),
    ("procurements.manage", "procurements", "Create/edit procurement batches/purchase orders"),
    ("inventory.view", "inventory", "View stock balances and the inventory ledger"),
    ("inventory.receive", "inventory", "Record goods receipts"),
    ("inventory.transfer", "inventory", "Transfer stock between warehouses"),
    ("inventory.adjust", "inventory", "Post manual stock adjustments"),
    ("inventory.reconcile", "inventory", "Run and finalize physical stock counts"),
    ("notifications.view", "notifications", "View the notification delivery log"),
    ("reports.view", "reports", "View, export and email accountability reports"),
    ("starlink.view", "starlink", "View Starlink kits, deployments and subscriptions"),
    (
        "starlink.manage", "starlink",
        "Register/edit Starlink kits, field teams, funding sources and hard-to-reach areas",
    ),
    ("starlink.install", "starlink", "Record Starlink installations"),
    ("starlink.subscription", "starlink", "Manage Starlink subscriptions and payments"),
    ("starlink.assign", "starlink", "Assign, return or move Starlink kits to/from field teams"),
    ("starlink.checkin", "starlink", "Submit a field team's daily Starlink check-in"),
    ("starlink.maintenance", "starlink", "Report and resolve Starlink faults"),
]

# role_name -> permission codes. System Administrator gets everything below.
ROLE_PERMISSIONS: dict[str, list[str]] = {
    "System Administrator": [p[0] for p in PERMISSIONS],
    "National Logistics Director": [
        "dashboard.view", "audit.view", "locations.view", "warehouses.view", "users.view", "roles.view",
        "assets.view", "suppliers.view", "procurements.view", "inventory.view", "notifications.view",
        "reports.view", "starlink.view", "starlink.manage", "starlink.assign", "starlink.subscription",
    ],
    "Logistics Manager": [
        "dashboard.view", "locations.view", "warehouses.view", "warehouses.manage", "users.view", "audit.view",
        "assets.view", "assets.create", "assets.update", "assets.manage_catalogue",
        "suppliers.view", "suppliers.manage", "procurements.view", "procurements.manage",
        "inventory.view", "inventory.receive", "inventory.transfer", "inventory.adjust", "inventory.reconcile",
        "notifications.view", "reports.view", "starlink.view", "starlink.manage", "starlink.assign",
    ],
    "Central Warehouse Manager": [
        "dashboard.view", "warehouses.view", "warehouses.manage", "locations.view",
        "assets.view", "assets.create", "assets.update",
        "suppliers.view", "procurements.view",
        "inventory.view", "inventory.receive", "inventory.transfer", "inventory.adjust", "inventory.reconcile",
        "notifications.view", "reports.view", "starlink.view", "starlink.manage", "starlink.assign",
    ],
    "Regional Logistics Officer": [
        "dashboard.view", "locations.view", "warehouses.view", "assets.view", "inventory.view", "reports.view",
        "starlink.view", "starlink.assign",
    ],
    "District Logistics Officer": [
        "dashboard.view", "locations.view", "warehouses.view", "assets.view", "assets.update",
        "inventory.view", "inventory.receive", "inventory.reconcile", "reports.view",
        "starlink.view", "starlink.assign", "starlink.checkin",
    ],
    "Warehouse Officer": [
        "dashboard.view", "warehouses.view", "assets.view", "assets.create", "assets.update",
        "inventory.view", "inventory.receive", "inventory.transfer",
    ],
    "IT Asset Officer": [
        "dashboard.view", "locations.view", "assets.view", "assets.create", "assets.update",
        "assets.manage_catalogue", "notifications.view", "starlink.view", "starlink.install", "starlink.maintenance",
    ],
    "Starlink / Connectivity Officer": [
        "dashboard.view", "locations.view", "assets.view", "assets.update",
        "starlink.view", "starlink.manage", "starlink.install", "starlink.subscription",
        "starlink.assign", "starlink.maintenance", "starlink.checkin",
    ],
    "Transport Officer": ["dashboard.view", "locations.view", "assets.view"],
    "Supervisor": ["dashboard.view", "assets.view", "starlink.view", "starlink.checkin"],
    "Enumerator": ["dashboard.view"],
    "Auditor": [
        "audit.view", "dashboard.view", "users.view", "roles.view", "locations.view", "warehouses.view",
        "assets.view", "suppliers.view", "procurements.view", "inventory.view", "notifications.view",
        "reports.view", "starlink.view",
    ],
    "Senior Management": ["dashboard.view", "assets.view", "inventory.view", "reports.view", "starlink.view"],
}

# Sierra Leone's actual administrative geography (5 regions / 16 districts, post-2017 reform).
REGIONS_DISTRICTS = {
    ("Western Area", "WA"): [("Western Area Urban", "WAU"), ("Western Area Rural", "WAR")],
    ("Northern Province", "NP"): [
        ("Bombali", "BOM"), ("Falaba", "FAL"), ("Koinadugu", "KOI"), ("Tonkolili", "TON"),
    ],
    ("North West Province", "NW"): [("Kambia", "KAM"), ("Karene", "KAR"), ("Port Loko", "PLO")],
    ("Southern Province", "SP"): [
        ("Bo", "BO"), ("Bonthe", "BON"), ("Moyamba", "MOY"), ("Pujehun", "PUJ"),
    ],
    ("Eastern Province", "EP"): [("Kailahun", "KAI"), ("Kenema", "KEN"), ("Kono", "KNO")],
}

DISTRICT_OFFICE_TYPE = "District Office"
REGIONAL_STORE_TYPE = "Regional Store"
CENTRAL_STORE_TYPE = "Central Store"

LOCATION_TYPES = [
    (DISTRICT_OFFICE_TYPE, "District-level logistics store/office"),
    (REGIONAL_STORE_TYPE, "Regional-level logistics store"),
    (CENTRAL_STORE_TYPE, "National central logistics store"),
]

# Asset category catalogue from brief §3 — database-driven, admins can add
# more later. (name, code_prefix, tracking_type)
ASSET_CATEGORIES = [
    # §3.1 Major Serialized Assets (tracked individually)
    ("Android Tablets", "TAB", "serialized"),
    ("Power Banks", "PWB", "serialized"),
    ("Starlink Kits", "STR", "serialized"),
    ("Smartphones", "PHN", "serialized"),
    ("Laptops", "LAP", "serialized"),
    ("Desktop Computers", "DSK", "serialized"),
    ("Servers", "SRV", "serialized"),
    ("Routers", "RTR", "serialized"),
    ("MiFi Devices / Modems", "MIFI", "serialized"),
    ("GPS Devices", "GPS", "serialized"),
    ("Printers and Scanners", "PRN", "serialized"),
    ("UPS Devices", "UPS", "serialized"),
    ("Network Switches / Access Points", "NSW", "serialized"),
    ("External Hard Drives", "HDD", "serialized"),
    ("Other IT Equipment", "OIT", "serialized"),
    # §3.2 Other Census Logistics (quantity-based stock movement)
    ("SIM Cards", "SIM", "quantity"),
    ("SD Cards", "SDC", "quantity"),
    ("Chargers and USB Cables", "CHG", "quantity"),
    ("Tablet Cases", "TCS", "quantity"),
    ("Census Bags", "BAG", "quantity"),
    ("Reflective Jackets / Vests", "VST", "quantity"),
    ("ID Materials", "IDM", "quantity"),
    ("Training Materials", "TRN", "quantity"),
    ("Stationery", "STA", "quantity"),
    ("Furniture", "FUR", "quantity"),
    ("Storage Boxes", "BOX", "quantity"),
    ("Extension Cables", "EXT", "quantity"),
    ("Charging Equipment", "CHE", "quantity"),
    ("Solar Chargers", "SOL", "quantity"),
    ("Power Equipment", "PWE", "quantity"),
    ("Other census materials", "OCM", "quantity"),
    # Office/administrative supplies — added for the dashboard's office-items
    # summary (not part of the original brief §3 census fleet, but the same
    # ledger-driven stock model applies).
    ("Printer Ink & Toner", "INK", "quantity"),
]

# Email notification templates (brief §12.2 trigger events — the slice wired
# up so far: new-asset and inventory-movement notifications). {placeholders}
# are filled from the event context at send time (see notification_service.py).
NOTIFICATION_TEMPLATES = [
    # (event_type, subject_template, body_template, sms_body_template)
    # sms_body_template is None for routine/low-priority events (brief
    # §12.4's priority table treats SMS as opt-in, not "every event") — set
    # only on the two genuinely urgent ones below.
    (
        "asset.registered",
        "New asset registered: {asset_tag}",
        "{asset_tag} ({category_name}) was registered by {registered_by} at {location_name}.",
        None,
    ),
    (
        "asset.status_critical",
        "Asset {asset_tag} marked {new_status}",
        "{asset_tag} ({category_name}) changed from {previous_status} to {new_status}, "
        "recorded by {changed_by}.\n\nReason: {reason}",
        "ALERT: {asset_tag} ({category_name}) marked {new_status}. By {changed_by}. Reason: {reason}",
    ),
    (
        "asset.bulk_imported",
        "{count} {category_name} imported by {imported_by}",
        "{imported_by} bulk-imported {count} {category_name} "
        "({first_asset_tag} through {last_asset_tag}).\n\n"
        "{skipped_count} row(s) were skipped (duplicates or missing data) — see the "
        "import report for details.\n\n"
        "This is a single summary email for the whole batch, not one per asset.",
        None,
    ),
    (
        "user.password_reset",
        "Your SLPHC 2026 Logistics password has been reset",
        "Hello {first_name},\n\n"
        "An administrator has reset your password. Your temporary password is:\n\n"
        "    {temporary_password}\n\n"
        "Please sign in and change it immediately from Settings.\n\n"
        "If you did not expect this, contact your system administrator.",
        None,
    ),
    (
        "inventory.receipt",
        "Stock received at {warehouse_name}",
        "Goods received at {warehouse_name} from {supplier_name}.\n\n"
        "Received by: {received_by}\nDelivered by: {delivered_by}\n\n{items_summary}",
        None,
    ),
    (
        "inventory.transfer_dispatched",
        "Stock transfer dispatched: {category_name}",
        "{released_by} dispatched {quantity} unit(s) of {category_name} "
        "from {from_warehouse} to {to_warehouse}.\n\nExpected delivery: {expected_delivery_date}.",
        "Transfer dispatched: {quantity}x {category_name} {from_warehouse}->{to_warehouse} by "
        "{released_by}. Due {expected_delivery_date}.",
    ),
    (
        "inventory.transfer_received",
        "Stock transfer received: {category_name}",
        "{received_by} confirmed receipt of {quantity} unit(s) of {category_name} at {to_warehouse}.",
        None,
    ),
    (
        "inventory.transfer_overdue",
        "OVERDUE: {category_name} transfer from {from_warehouse} to {to_warehouse}",
        "A transfer of {quantity} unit(s) of {category_name} from {from_warehouse} to {to_warehouse}, "
        "released by {released_by}, was expected to arrive by {expected_delivery_date} and has not yet "
        "been confirmed received.\n\nPlease follow up with both the releasing and receiving parties.",
        "OVERDUE: {quantity}x {category_name} {from_warehouse}->{to_warehouse}, due "
        "{expected_delivery_date}. Follow up needed.",
    ),
    (
        "inventory.adjustment",
        "Stock adjustment at {warehouse_name}: {category_name}",
        "{performed_by} adjusted {category_name} at {warehouse_name} by {quantity_delta:+d}.\n\n"
        "Reason: {reason}",
        None,
    ),
    (
        "starlink.subscription_expiring",
        "Starlink subscription expiring in {days_remaining} day(s): {asset_tag}",
        "The {plan_name} subscription for Starlink kit {asset_tag} ({kit_type}) expires on "
        "{expiry_date} — {days_remaining} day(s) from now.\n\nRenew it before service is interrupted.",
        "Starlink {asset_tag} subscription expires {expiry_date} ({days_remaining}d). Renew soon.",
    ),
    (
        "starlink.subscription_expired",
        "Starlink subscription EXPIRED: {asset_tag}",
        "The {plan_name} subscription for Starlink kit {asset_tag} ({kit_type}) expired on "
        "{expiry_date} and has not been renewed. Connectivity may already be lost.",
        "ALERT: Starlink {asset_tag} subscription expired {expiry_date}.",
    ),
    (
        "starlink.payment_overdue",
        "Starlink payment overdue: {asset_tag}",
        "The subscription payment for Starlink kit {asset_tag} ({plan_name}) was due on "
        "{next_payment_date} and has not been recorded as paid.",
        "Starlink {asset_tag} payment overdue since {next_payment_date}.",
    ),
    (
        "starlink.offline_reported",
        "Starlink reported offline: {asset_tag}",
        "{asset_tag} ({kit_type}) at {location_label} was reported offline in the latest check-in "
        "({checkin_at}). Connectivity quality: {connectivity_quality}.",
        "ALERT: Starlink {asset_tag} offline at {location_label} ({checkin_at}).",
    ),
    (
        "starlink.support_requested",
        "ICT support requested: Starlink {asset_tag}",
        "The field team carrying {asset_tag} has requested technical support.\n\n"
        "Reported problem: {technical_problem}\n\nLocation: {location_label}",
        "Support needed: Starlink {asset_tag} at {location_label}. {technical_problem}",
    ),
    (
        "starlink.hard_to_reach_gap",
        "Starlink required but not assigned: {area_name}",
        "{area_name} in {district_name} is classified Starlink Required, but the field team "
        "deployed there currently has no active Starlink assignment.",
        "GAP: {area_name} ({district_name}) needs Starlink — none assigned.",
    ),
    (
        "starlink.kit_overdue_return",
        "Starlink kit overdue for return: {asset_tag}",
        "{asset_tag} was due back from {team_name} on {expected_return_date} and has not yet been "
        "returned or reassigned.",
        "OVERDUE: Starlink {asset_tag} from {team_name}, due {expected_return_date}.",
    ),
]


def run() -> None:
    db = SessionLocal()
    try:
        permissions_by_code = {}
        for code, module, description in PERMISSIONS:
            perm = db.query(Permission).filter_by(code=code).one_or_none()
            if not perm:
                perm = Permission(code=code, module=module, description=description)
                db.add(perm)
                db.flush()
            permissions_by_code[code] = perm

        for role_name, perm_codes in ROLE_PERMISSIONS.items():
            role = db.query(Role).filter_by(name=role_name).one_or_none()
            if not role:
                role = Role(name=role_name, is_system=True)
                role.permissions = [permissions_by_code[c] for c in perm_codes]
                db.add(role)
            elif role_name == "System Administrator":
                # The one deliberate exception to "leave existing roles
                # alone": System Administrator is contractually "every
                # permission" (see PERMISSIONS/ROLE_PERMISSIONS above), so
                # when the permission catalogue grows on a later deploy, this
                # role must grow with it — top up only (never remove), so a
                # permission added here always reaches every existing DB.
                current = {p.code for p in role.permissions}
                role.permissions += [permissions_by_code[c] for c in perm_codes if c not in current]
            # Every other existing role is left alone: an admin may have
            # customized its permissions via the Roles UI, and re-running
            # this idempotent seed (e.g. after a deploy) must not silently
            # revert that.

        for (region_name, region_code), districts in REGIONS_DISTRICTS.items():
            region = db.query(Region).filter_by(code=region_code).one_or_none()
            if not region:
                region = Region(name=region_name, code=region_code)
                db.add(region)
                db.flush()
            for district_name, district_code in districts:
                district = db.query(District).filter_by(code=district_code).one_or_none()
                if not district:
                    db.add(District(name=district_name, code=district_code, region_id=region.id))

        for name, code_prefix, tracking_type in ASSET_CATEGORIES:
            if not db.query(AssetCategory).filter_by(code_prefix=code_prefix).one_or_none():
                db.add(AssetCategory(name=name, code_prefix=code_prefix, tracking_type=tracking_type))

        for event_type, subject_template, body_template, sms_body_template in NOTIFICATION_TEMPLATES:
            if not db.query(NotificationTemplate).filter_by(event_type=event_type).one_or_none():
                db.add(
                    NotificationTemplate(
                        event_type=event_type, subject_template=subject_template, body_template=body_template,
                        sms_body_template=sms_body_template,
                    )
                )

        db.commit()

        for type_name, description in LOCATION_TYPES:
            if not db.query(LocationType).filter_by(name=type_name).one_or_none():
                db.add(LocationType(name=type_name, description=description))
        db.commit()

        district_office_type = db.query(LocationType).filter_by(name=DISTRICT_OFFICE_TYPE).one()
        regional_store_type = db.query(LocationType).filter_by(name=REGIONAL_STORE_TYPE).one()

        for district in db.query(District).all():
            location_name = f"{district.name.replace(' ', '-')}-District-Office"
            location = db.query(Location).filter_by(name=location_name).one_or_none()
            if not location:
                location = Location(
                    location_type_id=district_office_type.id, district_id=district.id, name=location_name,
                )
                db.add(location)
                db.flush()
            if not db.query(Warehouse).filter_by(location_id=location.id).one_or_none():
                db.add(Warehouse(location_id=location.id, code=f"{district.code}-DO"))

        for region in db.query(Region).all():
            location_name = f"{region.name.replace(' ', '-')}-Store"
            location = db.query(Location).filter_by(name=location_name).one_or_none()
            if not location:
                location = Location(
                    location_type_id=regional_store_type.id, region_id=region.id, name=location_name,
                )
                db.add(location)
                db.flush()
            if not db.query(Warehouse).filter_by(location_id=location.id).one_or_none():
                db.add(Warehouse(location_id=location.id, code=f"{region.code}-RS"))

        central_store_type = db.query(LocationType).filter_by(name=CENTRAL_STORE_TYPE).one()
        freetown = db.query(District).filter_by(code="WAU").one()
        location_name = "Freetown-Central-Store"
        location = db.query(Location).filter_by(name=location_name).one_or_none()
        if not location:
            location = Location(location_type_id=central_store_type.id, district_id=freetown.id, name=location_name)
            db.add(location)
            db.flush()
        if not db.query(Warehouse).filter_by(location_id=location.id).one_or_none():
            db.add(Warehouse(location_id=location.id, code="FT-CS", is_central=True))

        db.commit()

        admin = db.query(User).filter_by(email=settings.BOOTSTRAP_ADMIN_EMAIL).one_or_none()
        if not admin:
            admin_role = db.query(Role).filter_by(name="System Administrator").one()
            admin = User(
                email=settings.BOOTSTRAP_ADMIN_EMAIL,
                hashed_password=hash_password(settings.BOOTSTRAP_ADMIN_PASSWORD),
                first_name="System",
                last_name="Administrator",
                roles=[admin_role],
            )
            db.add(admin)
            db.commit()
            print(f"Created bootstrap admin: {settings.BOOTSTRAP_ADMIN_EMAIL} "
                  f"(change the password immediately after first login).")
        else:
            print("Bootstrap admin already exists, skipping.")

        print("Seed complete.")
    finally:
        db.close()


if __name__ == "__main__":
    run()
