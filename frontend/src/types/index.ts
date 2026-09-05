export interface CurrentUser {
  id: string;
  email: string;
  first_name: string;
  last_name: string;
  roles: string[];
  permissions: string[];
  region_id: string | null;
  district_id: string | null;
}

export interface RoleSummary {
  id: string;
  name: string;
}

export interface UserRecord {
  id: string;
  email: string;
  first_name: string;
  last_name: string;
  phone: string | null;
  is_active: boolean;
  roles: RoleSummary[];
  region_id: string | null;
  district_id: string | null;
  last_login_at: string | null;
  created_at: string;
}

export interface Permission {
  id: string;
  code: string;
  module: string;
  description: string | null;
}

export interface Role {
  id: string;
  name: string;
  description: string | null;
  is_system: boolean;
  permissions: Permission[];
}

export interface WarehouseAccess {
  id: string;
  name: string;
}

export interface EffectivePermission {
  id: string;
  code: string;
  module: string;
  description: string | null;
  from_role: boolean;
  override: "GRANT" | "REVOKE" | null;
  effective: boolean;
}

export interface Region {
  id: string;
  name: string;
  code: string;
}

export interface District {
  id: string;
  name: string;
  code: string;
  region_id: string;
}

export interface LocationType {
  id: string;
  name: string;
  description: string | null;
}

export interface LocationRecord {
  id: string;
  location_type_id: string;
  region_id: string | null;
  district_id: string | null;
  name: string;
  address: string | null;
  gps_latitude: number | null;
  gps_longitude: number | null;
  is_active: boolean;
}

export interface Warehouse {
  id: string;
  location_id: string;
  code: string;
  is_central: boolean;
  notes: string | null;
  is_active: boolean;
}

export interface AuditLogEntry {
  id: string;
  user_id: string | null;
  action: string;
  entity_type: string;
  entity_id: string | null;
  old_value: Record<string, unknown> | null;
  new_value: Record<string, unknown> | null;
  reason: string | null;
  ip_address: string | null;
  created_at: string;
}

export interface AssetCategory {
  id: string;
  name: string;
  code_prefix: string;
  tracking_type: "serialized" | "quantity";
  is_active: boolean;
  next_sequence: number;
}

export interface AssetModel {
  id: string;
  category_id: string;
  brand: string;
  model_name: string;
  storage: string | null;
  ram: string | null;
  operating_system: string | null;
  specifications: string | null;
}

export const ASSET_STATUSES = [
  "AVAILABLE",
  "ALLOCATED",
  "IN_TRANSIT",
  "ASSIGNED",
  "RETURNED",
  "UNDER_MAINTENANCE",
  "DAMAGED",
  "LOST",
  "DISPOSED",
] as const;
export type AssetStatus = (typeof ASSET_STATUSES)[number];

export const ASSET_CONDITIONS = ["NEW", "GOOD", "FAIR", "POOR", "DAMAGED", "UNUSABLE"] as const;
export type AssetCondition = (typeof ASSET_CONDITIONS)[number];

export interface AssetListItem {
  id: string;
  asset_tag: string;
  category_id: string;
  serial_number: string | null;
  status: AssetStatus;
  condition: AssetCondition;
  current_location_id: string | null;
  current_custodian_id: string | null;
  created_at: string;
}

export interface AssetRead {
  id: string;
  asset_tag: string;
  category: AssetCategory;
  model: AssetModel | null;
  serial_number: string | null;
  imei_1: string | null;
  imei_2: string | null;
  mac_address: string | null;
  sim_or_phone_number: string | null;
  supplier_or_donor: string | null;
  procurement_batch: string | null;
  purchase_order_ref: string | null;
  date_acquired: string | null;
  date_received: string | null;
  unit_cost: number | null;
  currency: string | null;
  warranty_start: string | null;
  warranty_end: string | null;
  status: AssetStatus;
  condition: AssetCondition;
  current_location: { id: string; name: string } | null;
  current_custodian: { id: string; first_name: string; last_name: string; email: string } | null;
  remarks: string | null;
  created_at: string;
  updated_at: string;
}

export interface AssetStatusEvent {
  id: string;
  event_type: string;
  previous_status: string | null;
  new_status: string | null;
  previous_location_id: string | null;
  new_location_id: string | null;
  previous_custodian_id: string | null;
  new_custodian_id: string | null;
  condition: string | null;
  reason: string | null;
  performed_by: { id: string; first_name: string; last_name: string; email: string } | null;
  created_at: string;
}

export interface Supplier {
  id: string;
  name: string;
  supplier_type: "supplier" | "donor";
  contact_person: string | null;
  phone: string | null;
  email: string | null;
  address: string | null;
  is_active: boolean;
}

export const PROCUREMENT_STATUSES = ["DRAFT", "ORDERED", "PARTIALLY_RECEIVED", "RECEIVED", "CANCELLED"] as const;
export type ProcurementStatus = (typeof PROCUREMENT_STATUSES)[number];

export interface Procurement {
  id: string;
  supplier: Supplier | null;
  reference: string;
  description: string | null;
  status: ProcurementStatus;
  order_date: string | null;
  expected_delivery_date: string | null;
}

export interface StockBalance {
  warehouse_id: string;
  warehouse_name: string;
  category_id: string;
  category_name: string;
  quantity_on_hand: number;
}

export interface InventoryTransaction {
  id: string;
  warehouse: { id: string; name: string };
  category: { id: string; name: string; code_prefix: string };
  transaction_type: string;
  quantity: number;
  related_warehouse: { id: string; name: string } | null;
  reference_type: string | null;
  reference_id: string | null;
  reason: string | null;
  created_at: string;
}

export interface GoodsReceipt {
  id: string;
  warehouse: { id: string; name: string };
  supplier: { id: string; name: string; supplier_type: "supplier" | "donor" } | null;
  procurement_id: string | null;
  received_by_name: string;
  delivered_by_name: string | null;
  receipt_date: string;
  remarks: string | null;
  items: InventoryTransaction[];
  created_at: string;
}

export interface StockTransfer {
  id: string;
  category: { id: string; name: string; code_prefix: string };
  from_warehouse: { id: string; name: string };
  to_warehouse: { id: string; name: string };
  quantity: number;
  status: "IN_TRANSIT" | "RECEIVED";
  expected_delivery_date: string;
  actual_delivery_date: string | null;
  released_by_name: string;
  received_by_name: string | null;
  reason: string | null;
  is_overdue: boolean;
  created_at: string;
}

export interface StockCountItem {
  id: string;
  category: { id: string; name: string; code_prefix: string };
  expected_quantity: number;
  physical_quantity: number;
  variance: number;
  variance_reason: string | null;
}

export interface StockCount {
  id: string;
  warehouse_id: string;
  status: "DRAFT" | "COMPLETED";
  count_date: string;
  notes: string | null;
  items: StockCountItem[];
}

export type NotificationStatus = "PENDING" | "SENT" | "FAILED" | "SKIPPED";

export interface NotificationEntry {
  id: string;
  event_type: string;
  channel: string;
  recipient_email: string | null;
  recipient_phone: string | null;
  subject: string;
  status: NotificationStatus;
  provider_response: string | null;
  related_entity_type: string | null;
  related_entity_id: string | null;
  created_at: string;
  sent_at: string | null;
}

export interface BulkImportRow {
  row_number: number;
  serial_number: string | null;
  imei_1: string | null;
  imei_2: string | null;
  box_number: string | null;
}

export interface BulkImportRowError {
  row_number: number;
  serial_number: string | null;
  reason: string;
}

export interface BulkImportResponse {
  total_rows: number;
  valid_count: number;
  invalid_count: number;
  errors: BulkImportRowError[];
  committed: boolean;
  created_count: number | null;
  first_asset_tag: string | null;
  last_asset_tag: string | null;
}

export interface Page<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}

export interface ReportDefinition {
  id: string;
  name: string;
  description: string;
  filters: string[];
}

export interface ReportColumn {
  key: string;
  label: string;
}

export interface ReportResult {
  report_id: string;
  title: string;
  generated_at: string;
  generated_by: string;
  filters_applied: Record<string, string>;
  columns: ReportColumn[];
  rows: Record<string, string | number>[];
  row_count: number;
  truncated: boolean;
}

export interface OfficeItemSummary {
  category_name: string;
  tracking_type: "serialized" | "quantity";
  total: number;
  available: number;
}

export interface DashboardSummary {
  total_assets: number;
  available: number;
  allocated: number;
  in_transit: number;
  delivered: number;
  assigned: number;
  pending_receipt: number;
  returned: number;
  damaged: number;
  lost: number;
  unaccounted: number;
  active_alerts: number;
  regions_count: number;
  districts_count: number;
  users_count: number;
}
