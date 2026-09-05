# SLPHC 2026 Logistics Command & Asset Management System

End-to-end census asset accountability for Sierra Leone's 2026 Population and
Housing Census — from procurement/source through warehousing, distribution,
field assignment, return and disposition. Full requirements in
`docs/SLPHC_2026_Logistics_Management_System_Development_Brief.docx`.

**Status:** Phases 1–3 built **and verified running end-to-end** (real login,
real Postgres, real business logic — see "Verified working" below).

- Phase 1 (Foundation) — project scaffold, auth, RBAC, users, roles,
  permissions, admin geography (regions/districts/chiefdoms/sections/SAs/EAs),
  logistics locations/warehouses, audit log, and the dashboard shell. RBAC has
  a per-user layer on top of roles: a `UserPermissionOverride`
  (GRANT/REVOKE) lets an individual user's rights be edited directly — grant
  something their role doesn't carry, or revoke something it does, without
  touching the role itself or anyone else assigned to it. One shared
  `permission_service.effective_permission_codes()` helper computes the
  role+override result and is used everywhere permissions are checked or
  reported (`require_permission`, JWT claim issuance at login, `/auth/me`,
  notification recipient resolution) so an override behaves identically no
  matter which of those paths touches it. Permissions are baked into the JWT
  at login, so an override takes effect for that user on their next login,
  not mid-session — the Permissions dialog on the Users page says as much.
  Editing an existing user (name, email, mobile contact, active status) is
  now possible from the Users page, gated by `users.update` like the rest of
  that page — but changing *which roles* a user has, or editing their
  per-user permission overrides, is hard-restricted to the System
  Administrator role specifically (`require_role("System Administrator")`,
  not just a permission check), same as creating/editing/deleting role
  definitions on the Roles & Permissions page. That page renders read-only
  (checkboxes disabled, no Save button) for anyone who can view it but isn't
  a System Administrator. Settings is hidden from the sidebar and its route
  entirely for non-System-Administrators too. A user can also be scoped to
  one or more specific warehouses (a "Warehouses" button next to Permissions
  on the Users page, System-Administrator-only like the other access
  controls) — `UserWarehouseAccess` rows are opt-in: zero rows means
  unrestricted national access exactly as before, one or more rows means
  every inventory endpoint (balances, transactions, receipts, transfers
  dispatch/receive, adjustments, stock counts) rejects or silently filters
  out anything outside that set, and `GET /warehouses` itself only returns
  the assigned warehouse(s) — so every warehouse dropdown across the app
  (Inventory's Receive/Transfer/Adjust forms, Reports filters) narrows
  automatically with no per-page filtering logic needed on the frontend.
- Phase 2 (Asset Management) — asset category/model catalogue (seeded from
  brief §3), the serialized asset register with generated Asset IDs
  (SLPHC26-XXX-000001), QR codes, a fixed status workflow with server-side
  transition validation, and the Asset Journey timeline.
- Phase 3 (Warehouse & Inventory) — suppliers/donors, procurement batches,
  and a ledger-driven inventory system for the quantity-tracked categories
  from brief §3.2 (SIM cards, cables, bags, etc.): goods receipt, warehouse-
  to-warehouse transfer, manual adjustment (reason required), stock balances
  derived from the ledger (never stored/edited directly, per §17's "Ledger
  principle"), and physical stock counts with variance-driven reconciliation.
  Goods receipt carries full named accountability (brief §5/§7.1) — a
  `GoodsReceipt` header records who received it (store officer name), who
  delivered it (courier/driver name) and which supplier, separate from the
  underlying `InventoryTransaction` ledger rows it links to. Store staff
  (`inventory.receive`) can add a brand-new quantity-tracked category inline
  while receiving stock — no need for the separate `assets.manage_catalogue`
  permission just to name a material that doesn't exist yet. The receiving
  officer's name is never client-supplied: it's always the authenticated
  caller (`current_user.full_name`), set server-side and ignored if a client
  sends its own `received_by_name` — the Receive stock form shows it as a
  read-only field rather than a text box, so the accountability record can't
  be typed to name someone other than whoever actually submitted it.
  Stock transfers are two-phase, mirroring the brief's own asset-in-transit
  model: dispatching a transfer decrements the source warehouse immediately
  (one `TRANSFER_OUT` ledger row) but the destination only gets credited
  (`TRANSFER_IN`) once someone there confirms receipt — the `StockTransfer`
  header tracks `status` (`IN_TRANSIT`/`RECEIVED`), `expected_delivery_date`,
  `actual_delivery_date`, and the named releasing/receiving officer for each
  leg. An hourly Celery Beat task (`notifications.check_overdue_transfers`)
  finds transfers still `IN_TRANSIT` past their expected delivery date and
  emails both the officer who dispatched it and everyone holding
  `inventory.reconcile`, once per transfer (`overdue_notified_at` guards
  against re-sending on the next hourly run). Both named parties on a
  transfer — `released_by_name` (dispatch) and `received_by_name` (confirm
  receipt) — get the same never-client-supplied treatment as the goods
  receipt's `received_by_name`: always `current_user.full_name`, set
  server-side, and shown as a read-only field in the Transfer stock and
  Confirm receipt dialogs rather than free text.
- Email notifications (a focused slice of Phase 8) — SMTP-backed, queued via
  the Celery worker so a slow/down mail server never blocks the triggering
  transaction (brief §12). Wired to 5 events: asset registered, asset marked
  DAMAGED/LOST/DISPOSED, and inventory receipt/transfer/adjustment. Wording
  lives in the DB-driven `notification_templates` table. Recipients are
  everyone holding a relevant permission (`assets.manage_catalogue` for asset
  events, `inventory.reconcile` for inventory events) — a v1 simplification;
  a proper per-event rules table is the natural next step if that set turns
  out wrong for some event. Every send attempt is logged permanently in
  `notifications` (Notifications page in the UI), regardless of whether SMTP
  is even configured (unconfigured → logged as `SKIPPED`, nothing crashes).
- SMS notifications (brief §12: SMS as a second channel alongside email) —
  wired to the AppHiveSL gateway (`api.sierrahive.com`). `NotificationTemplate`
  gained an optional `sms_body_template`; when set, `notify()` also creates
  an SMS `Notification` row (channel `sms`) for every recipient who has a
  phone number on file, alongside the existing email row — same delivery-log/
  retry pipeline, routed to a separate Celery task
  (`notifications.send_sms`) by channel. SMS is opt-in per event, not
  automatic for every notification (brief §12.4's priority table treats it
  as a High/Critical-only channel) — currently wired to the two genuinely
  urgent events, asset marked DAMAGED/LOST/DISPOSED and an overdue stock
  transfer; the rest stay email-only. `SMS_CLIENT_ID`/`SMS_CLIENT_SECRET`/
  `SMS_TOKEN` unset disables SMS the same way an unset `SMTP_HOST` disables
  email (logged as `SKIPPED`, nothing crashes). `SMS_SENDER_ID` must be a
  sender name already registered on the AppHiveSL account — an unregistered
  one is rejected by the gateway with a 400, not silently dropped.
- Dashboard "Office & Store Items" national summary — the user's own idea,
  refined: a compact table on the dashboard's national operations overview
  giving an at-a-glance read on office/administrative stock (laptops,
  desktop computers, printers, printer ink, UPS units, stationery,
  furniture, chargers) separate from the census-fleet KPI cards above it.
  New `GET /dashboard/office-items` matches a curated, fixed list of
  category names (not "every category" — deliberately short, so it stays a
  glance, not a second inventory page) and reports `total`/`available` per
  category: for quantity-tracked stock, on-hand quantity summed nationally
  across every warehouse (both numbers are the same — there's no separate
  allocation sub-state for consumables); for serialized equipment, total
  units registered vs. currently `AVAILABLE`. Degrades gracefully — a
  category name with no match in a given deployment's catalogue is just
  skipped, not an error. Added "Printer Ink & Toner" as a new quantity-
  tracked category to the seed catalogue since nothing already covered it.
  Full per-warehouse or per-unit detail is one click away on Inventory or
  the Asset register, exactly as it was before — this is additive, not a
  replacement.
- Bulk asset import (brief §19.1/§19.2: "Upload 25,000+ tablet records from
  Excel") — Excel parsed client-side (column names matched by alias, no fixed
  template required), validated server-side (missing data, duplicate serial/
  IMEI within the file and against the existing register) with a preview
  report before anything is written, then committed in one batch. A single
  digest email is sent per import (not one per asset) via `asset.bulk_imported`.
  **Used for real**: imported 24,494 tablets from two real Excel exports in
  ~14 seconds, catching one genuine duplicate unit across the two files.
- Detailed accountability reporting (brief §14) — 8 reports scoped to what
  Phases 1–3 actually have data for (the brief's full list also covers
  shipments, field assignment, Starlink and witnesses, none of which exist
  yet): Warehouse Accountability, Asset Receipt, Stock Transfer
  Accountability, Detailed Item Status / Current Custody, Asset
  Chain-of-Custody (one asset's full history), Unaccounted/Exception Assets
  (lost/damaged assets plus overdue transfers), Full System Audit, and
  Notification Delivery. Every report is one generic shape (columns + rows)
  so one renderer covers all of them — view on screen with filters, **Print**
  (a dedicated print stylesheet hides everything but the report), or export
  **PDF/Excel/CSV** (reportlab / openpyxl / stdlib csv). **Email** sends the
  same file as a real attachment to any address(es) typed in, reusing the
  existing Notification delivery-log/retry pipeline — `Notification` gained
  `attachment_filename/content_b64/mime_type` columns so an emailed report
  shows up in the Notification Delivery Report like anything else. A row cap
  (2000) protects both the PDF renderer and the browser table from the
  25,000+-tablet register — the result says `truncated: true` when a report
  hits it, so ask for a narrower date/warehouse/category range rather than
  the whole dataset at once. Gated by a new `reports.view` permission, opened
  up to every role the brief describes as having a reporting mandate (Auditor
  and Senior Management explicitly, plus National Logistics Director,
  Logistics Manager, warehouse/regional/district officers).
- Real national warehouse network — `locations.region_id` was added (a
  location can now be regional-level with no single district, not just
  district-level or national) so the full hierarchy from brief §5 exists:
  1 central + 5 regional + 16 district warehouses, one per region/district,
  all created through the real API (so each is audit-logged normally).

Shipments/dispatch, field assignment, Starlink, and reporting land in the
phases that follow (see the brief, §20).

## Stack

React + TypeScript + Tailwind + shadcn/ui · FastAPI + SQLAlchemy + Alembic ·
PostgreSQL · Redis/Celery · Docker Compose.

## Where this project actually lives

**The working copy is `C:\dev\SLPHC-2026-Census-Logistics-Management-System`
on this machine — not the Google Drive folder it may have started in.**
Docker's WSL2 backend cannot even resolve a Google Drive virtual drive path
(`wsl: Failed to translate 'G:\My Drive\...'`), so Docker bind-mounts (and
`npm install`, for the same reason as ever) only work from a real local disk.
If a Drive copy of this project exists, treat it as a backup/handoff copy —
sync changes into it manually, or better, once this is pushed to git, drop
the Drive copy entirely and clone from the remote instead.

## First-time setup

Requires Docker Desktop. Everything runs in containers — no local Python/Node
install needed.

```bash
cp .env.example .env
# edit .env: set real POSTGRES_PASSWORD, JWT_SECRET_KEY (openssl rand -hex 32),
# and BOOTSTRAP_ADMIN_PASSWORD before starting.
# optionally set SMTP_HOST/PORT/USERNAME/PASSWORD + EMAIL_FROM_ADDRESS to
# enable email notifications — leave SMTP_HOST blank to disable (events still
# log to the Notifications page as SKIPPED, nothing crashes or blocks).

docker compose up -d --build
docker compose exec backend alembic upgrade head
docker compose exec backend python seed.py
```

- Frontend: http://localhost:5173
- Backend API: http://localhost:8000/api (docs at http://localhost:8000/docs)
- Log in with `BOOTSTRAP_ADMIN_EMAIL` / `BOOTSTRAP_ADMIN_PASSWORD` from `.env`,
  then change the password immediately.

**If `http://localhost:5173` won't load** (blank page, or a 404 with no
body) while `docker compose ps` shows the frontend container healthy: some
other process on the host — most often an old `npm run dev`/`vite` you forgot
to fully stop — is squatting on port 5173 over IPv6 (`::1`), and Windows
resolves `localhost` to that before it ever reaches Docker's forwarded port.
Check with PowerShell:
```powershell
Get-NetTCPConnection -LocalPort 5173 | Select LocalAddress,OwningProcess
Get-Process -Id <OwningProcess>   # if it's not com.docker.backend, kill it
```
`http://127.0.0.1:5173` is a quick way to confirm this is the cause (it
bypasses the stale `::1` listener) — but don't use it as your regular URL:
the backend's CORS/cookie setup assumes frontend and backend share the
`localhost` site, and login's silent-refresh flow will fail across a page
reload from `127.0.0.1` (cross-site cookie rules) even though the initial
login appears to work.

## Verified working (2026-09-04)

Ran for real for the first time this session — migrations, seed data, login,
and core business logic all exercised end-to-end (API calls + browser
clicks), not just reviewed:
- `alembic upgrade head` — all 3 migrations apply cleanly
- `seed.py` — 14 roles, 27 permissions, 5 regions/16 districts, 31 asset
  categories, bootstrap admin created
- Login → JWT access token + httpOnly refresh cookie; page reload after
  login stays authenticated (refresh-token rotation works, no race)
- Asset registration → auto-generated `SLPHC26-TAB-000001`, status-transition
  guard (rejects invalid moves, e.g. straight to RETURNED), QR code renders,
  Asset Journey timeline shows both events with correct actor/timestamp
- Inventory: goods receipt (+500), adjustment with reason (-20), balance
  correctly derived as 480 — both via API and reflected live in the UI
- Every mutation above shows up in the Audit Log with actor, IP, timestamp

Real bugs caught and fixed only by actually running this (not by review):
1. A circular import between `app.models.asset`/`inventory`/`procurement`
   and `app.db.base`, caused by unnecessary defensive imports at the bottom
   of those model files (SQLAlchemy resolves `Mapped["ClassName"]` forward
   references via its own registry — it doesn't need the literal Python
   import, and that import was what made the cycle possible).
2. `passlib==1.7.4` doesn't work with `bcrypt>=4.1` (pip installed 5.0.0 by
   default) — a known upstream incompatibility. Fixed by pinning
   `bcrypt==4.0.1` in `requirements.txt`.
3. A refresh-token race: `useAuthBootstrap` and `api.ts`'s automatic 401-retry
   logic each independently called `/auth/refresh`; since refresh tokens
   rotate on single use, concurrent callers 401'd each other. Fixed by
   routing both through the same deduped `refreshAccessToken()`.
4. **SQLAlchemy lazy-loading a relationship on an object that's been `add()`ed
   but never flushed returns `None` silently, even with `autoflush=True`** —
   it does not autoflush-then-query the way you'd expect for a query. Hit
   this building the email notification feature: `inventory_service.py`'s
   `record_receipt`/`transfer`/`adjustment` created `InventoryTransaction`
   rows and returned them without flushing; the notification code immediately
   read `row.category.name` and got a crash (`'NoneType' object has no
   attribute 'name'`), not a stale value — so at least it failed loudly. Fixed
   by adding `db.flush()` right after creating those rows, matching the
   pattern `assets.py` already used correctly. Worth knowing generally: any
   new service function that creates a row and expects the *caller* to read
   a relationship off it needs an explicit flush before returning.
5. **Vite's dev-server file watcher doesn't see edits made from the Windows
   host through the WSL2 bind mount** — inotify events from outside the
   container don't reliably propagate across that boundary. Symptom: edited
   `App.tsx` on disk, confirmed the new content was there via
   `docker compose exec frontend cat`, but `curl localhost:5173/src/App.tsx`
   kept serving the pre-edit version indefinitely — no error, just silently
   stale, until the container was restarted. Fixed in `vite.config.ts` with
   `server.watch.usePolling: true`. If a frontend change ever seems to not
   be taking effect, this is the first thing to suspect — restart the
   `frontend` container to confirm before assuming the code itself is wrong.

## Verified working (2026-09-05) — two-phase stock transfers

Dispatch/receive lifecycle and the overdue-notification path exercised end to
end via API calls, a manually-triggered Celery task run, and browser clicks:
- `POST /inventory/transfers` (dispatch) decrements the source warehouse
  balance immediately and leaves the destination unchanged; rejects a
  quantity larger than the source balance (400)
- `POST /inventory/transfers/{id}/receive` credits the destination balance,
  flips status to `RECEIVED`, stamps `actual_delivery_date`; rejects a second
  receive attempt on an already-received transfer (400)
- `is_overdue` correctly flips to `true` once `expected_delivery_date` is in
  the past on a still-`IN_TRANSIT` transfer
- `notifications.check_overdue_transfers` (run manually, not waiting for the
  hourly Celery Beat tick) found the overdue transfer, emailed both the
  dispatching officer and everyone holding `inventory.reconcile` (delivery
  confirmed `SENT` via the real `mail.statistics.sl` SMTP server), stamped
  `overdue_notified_at`, and — confirmed on a second manual run — did not
  re-send once that stamp was set
- Frontend: the Transfers tab lists both in-transit and received transfers,
  shows a destructive "OVERDUE" badge past the expected date, the Receive
  dialog collects the receiving officer's name and updates the row live, and
  the Transfer stock dialog now collects `expected_delivery_date` and the
  releasing officer's name (`npx tsc --noEmit` clean, no Vite HMR errors)

## Verified working (2026-09-05) — per-user permission overrides

Exercised end to end through the real login flow, not just the DB layer:
- `GET /users/{id}/permissions` returns every permission with `from_role`,
  `override`, and the resulting `effective` flag
- `PUT /users/{id}/permissions` replaces a user's full override set (same
  replace-not-merge semantics as role permission editing); rejects an
  unknown `permission_id` (400)
- Created a throwaway test user on a limited role (District Logistics
  Officer, 8 permissions) — confirmed they lacked `assets.create` before any
  override, then confirmed `/auth/me` showed it after the admin GRANTed it
  and the test user logged in again (JWT claims only refresh on login, as
  documented above); separately REVOKEd a permission their role does carry
  (`locations.view`) and confirmed it disappeared on next login while the
  earlier GRANT stayed in place
- Frontend: the Users page's new "Permissions" button opens a module-grouped
  checkbox matrix (`tsc --noEmit` clean); unchecking a role-granted
  permission live-shows a "revoked" badge, checking one back shows "granted"
  when it wasn't there via role
- One leftover test account remains, deactivated: `Override Tester`
  (`override-test-<timestamp>@statistics.sl`). It can't be hard-deleted —
  its own login events are rows in the immutable `audit_logs` table with a
  foreign key to it, the same protection that earlier stopped the "Bo
  District Store" test location from being deleted. Harmless as-is; flagging
  in case its presence on the Users list is ever confusing.

## Verified working (2026-09-05) — receiving officer tied to the signed-in account

- `POST /inventory/receipts` with a `received_by_name` field in the body
  (attempting to name someone other than the caller) — the field is silently
  dropped (not part of `GoodsReceiptCreate` any more) and the stored value is
  always `current_user.full_name`, confirmed by checking the response
- A normal receipt with no `received_by_name` field at all — same result,
  correctly set to the logged-in admin's name
- Frontend: the Receive stock dialog now shows a read-only "Received by"
  box pre-filled with the signed-in user's name instead of an editable text
  input, with a one-line explanation of why (`tsc --noEmit` clean)

## Verified working (2026-09-05) — detailed accountability reporting

All 8 reports run against the system's real, live-imported data (including
the 24,494-tablet register), not fixtures:
- All 8 `GET /reports/{id}` endpoints return real rows against production
  data — `warehouse_accountability` computed correct opening/receipts/
  transfers/closing math per warehouse×category; `asset_status` against
  24,494+ real tablets correctly capped at 2000 rows with `truncated: true`;
  `asset_chain_of_custody` returns 400 without `asset_id`, 200 with a real
  asset's full event history
- `GET /reports/{id}/export?format=pdf|xlsx|csv` — all three formats
  produced valid, non-empty files (checked the PDF's `%PDF` header and
  opened it — a real 1-page table with the branded header, generated-by
  line and filter summary, not a stub); a 2000-row PDF export (the capped
  `asset_status` report) rendered in ~2.3s
- `POST /reports/{id}/email` — sent a real email via `mail.statistics.sl`
  with the exported file as a genuine MIME attachment (decoded the stored
  base64 from the `notifications` table and confirmed the PDF header/opened
  it); the delivery-log row shows `status: SENT` like any other notification
- Frontend, driven through the actual browser: selected a report, filter
  panel rendered the right inputs for that report (date range + warehouse +
  category + status for Stock Transfer Accountability), Generate rendered
  the table on screen, Email dialog collected recipients/format/note and
  sent successfully, PDF export button fired a real 200 request
  (`tsc --noEmit` clean)
- Granted the new `reports.view` permission to the roles already live in the
  database (seed.py's "don't touch existing roles" idempotency — by design,
  see the SQLAlchemy lazy-load / seed notes above — meant a plain re-seed
  would only reach System Administrator, so the rest were granted directly)

**Fixed same day**: the PDF export's column headers were white text on a
solid dark-navy fill. Legible in an on-screen PDF viewer, but risky the
moment it's actually printed — many browsers/printers skip background
fills by default (the exact use case this report set is built for), which
would leave the header row blank. Changed to dark slate text on a light
blue-gray fill with a navy underline instead, so headers stay legible
whether or not the background renders.

## Verified working (2026-09-05) — official branding and address footer

Replaced the placeholder "SL" text badge with the real logo, then swapped it
again same-day for the correct one:
- First pass used the Statistics Sierra Leone organizational logo (`Stats SL
  logo.jpeg`, supplied by the user); replaced shortly after with the
  official **2026 Decennial Population and Housing Census** logo
  (`2026-Census-Logo_2.jpg`) once the user supplied it and said to use it
  instead. Because both used the same on-disk filenames
  (`frontend/public/statistics-sl-logo.jpg` and
  `backend/app/assets/statistics_sl_logo.jpg`), the swap needed no code
  changes — confirmed the new image reached the login page, the sidebar, the
  browser tab favicon, and the PDF letterhead all from that one file
  replacement.
- Added Statistics Sierra Leone's official postal address/contact block as a
  footer in three places: the Dashboard ("welcome") page, the on-screen/
  printed Reports view (inside `.print-area`, so it's part of what the
  Print button reproduces), and every PDF export (drawn on every page via
  `onFirstPage`/`onLaterPages`, alongside a page number) — verified by
  regenerating a PDF and reading it back. The Excel export also gets it as a
  print-only footer (`ws.oddFooter`) rather than a data row, so it doesn't
  pollute the actual data grid.

## Verified working (2026-09-05) — edit user, and System-Administrator-only lockdown

Tested with real accounts, not just unit-level checks:
- `PUT /users/{id}` now accepts `email` (with a 409 on a duplicate, and a
  same-value resubmit correctly treated as a no-op success) and `phone` —
  confirmed both via API and through the new Edit dialog in the browser
- A throwaway role holding `users.update` but not System Administrator could
  edit a target user's name/email/phone (200) but was rejected (403)
  attempting to change that user's `role_ids` — the split between "editing a
  profile" and "editing roles" holds even when a role has the former
  permission without being the admin role
- A real Auditor-role login (has `roles.view` but no update rights) saw the
  Roles & Permissions page render read-only — disabled checkboxes, a banner
  explaining why, no Save button — and could not reach `PUT /roles/{id}`
  (403) even by calling the API directly
- The same Auditor login had no Settings link in the sidebar at all, while
  logging back in as System Administrator restored it — confirmed via two
  full login cycles in the browser, not just reading the nav-filter code
- `PUT /users/{id}/permissions` (the per-user override editor) now requires
  the System Administrator role the same way role editing does

## Verified working (2026-09-05) — per-user warehouse access scope

Exercised with a real District Logistics Officer account, not just unit
checks:
- Scoped a fresh test user to Bo District Warehouse only, via
  `PUT /users/{id}/warehouses` — confirmed `GET /users/{id}/warehouses`
  returned `[]` before and the assigned warehouse after
- That user could view/list Bo's balances (200) but was rejected (403)
  requesting Freetown Central Store's balances by `warehouse_id`, and an
  unfiltered balances call correctly returned only Bo's rows — same pattern
  confirmed for receiving stock (403 at Freetown, 201 at Bo)
- `GET /warehouses` for that user returned only `WH-BO-01` — verified again
  through the actual browser UI with a second test user scoped to Kenema:
  logged in as them and confirmed the Receive Stock dialog's warehouse
  dropdown showed only "Kenema District Warehouse", with zero warehouse-
  specific filtering code added to that dialog — it inherited the scope for
  free because the shared `useWarehouseOptions` hook calls the now-filtered
  `/warehouses` endpoint
- A System Administrator remained unaffected throughout (sees and can act on
  every warehouse), confirming the scope is genuinely opt-in

## Verified working (2026-09-05) — SMS notifications (AppHiveSL)

Verified with real spend against the live gateway, not a sandbox:
- A direct `send_sms()` call to a real phone was accepted (`status: pending`)
  and, checked against `GET /v1/transactions/{ticket}/status` a few seconds
  later, showed `status: "success"` — actual delivery confirmed by the
  recipient, not just an API 200
- First attempt used a placeholder sender ID and got a real, informative
  gateway error (`400: "Sender ID not configured"`) — corrected to the
  account's actual registered sender ID (`STATS SL`) and retried successfully
- Triggered a real `asset.status_critical` event (marked a test asset
  DAMAGED) end to end through `notify()` → `dispatch()` → Celery, not a
  direct service call — it correctly created both an email row and an SMS
  row per recipient who has a phone on file, routed each to the right task
  by channel, and every row landed `SENT` with the gateway's response
  (cost, ticket, status) stored in `provider_response`
- Frontend: Notifications page now shows a Channel column and renders phone
  numbers for SMS rows / addresses for email rows in one Recipient column
  (`tsc --noEmit` clean)
- **Note for the record**: that end-to-end test fired real SMS, at real
  cost, to three people who hold `assets.manage_catalogue` and have a phone
  on file — Theophilus Blaudfaust (confirmed receipt before the test),
  Moses Johnson, and Lansana Kanneh. The latter two received a message as a
  side effect of testing the actual notification pipeline (which pages
  every relevant permission-holder, exactly as designed), not because they
  individually agreed to a test message.

## Verified working (2026-09-05) — Transfer stock officer names locked to the signed-in user

Extended the same fix from goods receipt to both legs of a stock transfer:
- `POST /inventory/transfers` with a spoofed `released_by_name` in the body
  — silently dropped (removed from `StockTransferCreate` entirely), stored
  value always `current_user.full_name`
- `POST /inventory/transfers/{id}/receive` sent with no body at all (the
  request schema is now empty and the field removed from the API) — stored
  `received_by_name` still correctly set to the caller
- Frontend: dispatched a transfer through the actual Transfer stock dialog
  (now shows a read-only "Released by" box) and confirmed receipt through
  the actual Confirm receipt dialog (same treatment for "Received by") —
  the Transfers list showed "System Administrator / System Administrator"
  for both legs, not free text (`tsc --noEmit` clean)

## Production deployment (Hostinger VPS)

Live at `https://sl-logistics-ops.statistics.sl`, deployed on a Hostinger
Ubuntu 24.04 VPS at `/opt/slphc`.

`docker-compose.prod.yml` differs from the dev `docker-compose.yml`:
- Backend/celery run the built image directly — no source bind-mount, no
  `--reload`; `uvicorn` runs with `--workers 2`.
- Postgres and Redis are not exposed on the host at all (internal Docker
  network only) — the dev compose file's `5432`/`6379` host port mappings
  are dropped.
- The frontend is compiled to static files by a one-shot `frontend-build`
  service (`frontend/Dockerfile.prod`, `npm run build` with
  `VITE_API_BASE_URL=/api` baked in) into a shared volume, instead of
  running the Vite dev server.
- A `caddy` service (`Caddyfile`) fronts everything on 80/443: serves the
  built frontend as static files with SPA fallback, reverse-proxies
  `/api/*` to the backend container, and obtains/renews its Let's Encrypt
  certificate automatically (Caddy's automatic HTTPS — no certbot/manual
  cert management). `ENVIRONMENT=production` in `.env` makes the refresh
  cookie `Secure`, which requires this HTTPS front end to work at all.
- `.env` on the VPS is generated on the server itself (fresh
  `POSTGRES_PASSWORD`/`JWT_SECRET_KEY`/`BOOTSTRAP_ADMIN_PASSWORD` — never
  the dev-machine ones), with `BACKEND_CORS_ORIGINS`/`QR_CODE_BASE_URL`
  pointed at the production domain. SMTP/SMS credentials are the same real
  ones used in dev (same mailbox/gateway). It is not committed — matches
  `.gitignore`'s existing `.env` exclusion.

Redeploy after a `git push` to `main`:

```bash
ssh root@<vps-ip>
cd /opt/slphc
git pull
docker compose -f docker-compose.prod.yml build
docker compose -f docker-compose.prod.yml up -d
# only if a new Alembic revision was added:
docker compose -f docker-compose.prod.yml exec backend alembic upgrade head
```

## Verified working (2026-09-05) — production deployment

- Provisioned a fresh Hostinger Ubuntu 24.04 VPS: installed Docker Engine +
  Compose plugin, configured `ufw` to allow only SSH/80/443.
- `npm run build` (which type-checks via `tsc -b`, unlike the dev server)
  caught two pre-existing TypeScript errors — an unused import in
  `ReportsPage.tsx` and an under-annotated `flatMap` return type in
  `UsersPage.tsx` — fixed both before the image would build.
- Built and started `docker-compose.prod.yml`; Caddy obtained a Let's
  Encrypt certificate for `sl-logistics-ops.statistics.sl` on first start
  (confirmed in its logs: `certificate obtained successfully`).
- Ran `alembic upgrade head` (all 11 revisions applied) and `seed.py`
  (roles/permissions/bootstrap admin created) against the production
  database.
- `curl` verification: `https://` frontend returns 200, `http://` redirects
  308 to `https://`, `/api/auth/login` with the bootstrap admin returns a
  valid access token and sets `slphc_refresh_token` with
  `HttpOnly; Secure; SameSite=lax`.

## Fixed (2026-09-05) — login broken in production despite correct credentials

`curl` against `/api/auth/login` worked, but the actual login page showed
"Unable to reach the server" for the correct bootstrap admin password.
Root cause: `frontend/src/lib/api.ts`'s `buildUrl()` called
`new URL(BASE_URL + path)` with no base argument. `VITE_API_BASE_URL` is
baked in as the relative path `/api` in production (so one build works on
any origin) — the `URL` constructor, unlike `fetch()`, does not resolve a
relative string against the page's own origin and throws
`TypeError: Invalid URL` instead. That exception isn't an `ApiError`, so
the login form's catch-all reported it as an unreachable server — every
`apiRequest` call, not just login, was silently broken this way. Fixed by
passing `window.location.origin` as the constructor's base (harmless when
`BASE_URL` is already absolute, as in local dev). Verified by rebuilding
the frontend image and logging in through the actual production login
form — landed on the Dashboard as System Administrator.

## Verified working (2026-09-05) — self-service password change, admin password reset, account deletion

- Settings was gated to System Administrators only in both the sidebar
  nav item and implicitly (no other user could reach the page), so no
  non-admin had any way to change their own password — the backend
  endpoint (`POST /users/me/change-password`) existed already but nothing
  in the frontend called it. Un-gated the nav item; the notification-
  config placeholder card stays admin-only inside the page.
- Tested self-service change password against the live bootstrap admin
  account through the actual Settings UI: changed the password, saw
  "Password updated.", then changed it back to the documented one so
  existing credentials stay valid.
- Admin password reset (`POST /users/{id}/reset-password`, System
  Administrator only): created a throwaway test account, reset its
  password through the actual Users page dialog — got a random temporary
  password back, shown once, plus an emailed copy via the same templated-
  notification pipeline as every other system event (new `user.password_reset`
  template, seeded idempotently like the rest — re-running `seed.py` added
  it without touching existing data).
- Account deletion (`DELETE /users/{id}`, System Administrator only):
  verified both outcomes for real. Deleting the freshly-reset test account
  fell back to deactivation ("This account has history... tied to it") —
  correct, since the password-reset notification had already created a
  `Notification` row referencing it. Deleting a second, completely
  untouched test account fully removed it ("User account deleted.").
  Real accounts with any activity (assets, transactions, audit trail) will
  always deactivate rather than hard-delete — those records must never
  silently disappear or get nulled out.

## Verified working (2026-09-05) — district and regional store warehouses

Seeded (via `seed.py`, idempotent — matched by name) a `Warehouse` for
every one of the 16 districts and 5 regions: two new `LocationType` rows
(District Office, Regional Store), a `Location` per district/region named
`<Name>-District-Office` / `<Name>-Store` (spaces to hyphens, e.g.
`Bo-District-Office`, `Eastern-Province-Store`), and a `Warehouse` row for
each with a short code (district/region code + `-DO`/`-RS`). Confirmed on
the live Locations & Warehouses page: all 21 appear, correctly scoped
(District/Regional) and Active.

## Local (non-Docker) frontend dev

```bash
cd frontend
npm install
npm run dev
```

## Backend tests

Tests run against a real Postgres database (Postgres-specific column types are
used, so SQLite is not a substitute):

```bash
docker compose exec backend pytest
```
