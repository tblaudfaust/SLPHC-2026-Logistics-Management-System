import type { BadgeProps } from "@/components/ui/badge";
import type { AssetStatus } from "@/types";

export const STATUS_BADGE_VARIANT: Record<AssetStatus, NonNullable<BadgeProps["variant"]>> = {
  AVAILABLE: "success",
  ALLOCATED: "default",
  IN_TRANSIT: "default",
  ASSIGNED: "default",
  RETURNED: "neutral",
  UNDER_MAINTENANCE: "warning",
  DAMAGED: "destructive",
  LOST: "destructive",
  DISPOSED: "neutral",
};

export const STATUS_LABEL: Record<AssetStatus, string> = {
  AVAILABLE: "Available",
  ALLOCATED: "Allocated",
  IN_TRANSIT: "In Transit",
  ASSIGNED: "Assigned",
  RETURNED: "Returned",
  UNDER_MAINTENANCE: "Under Maintenance",
  DAMAGED: "Damaged",
  LOST: "Lost",
  DISPOSED: "Disposed",
};

// Mirrors backend ALLOWED_STATUS_TRANSITIONS (app/services/asset_service.py) so
// the status-change dropdown only ever offers moves the API will accept.
export const ALLOWED_STATUS_TRANSITIONS: Record<AssetStatus, AssetStatus[]> = {
  AVAILABLE: ["ALLOCATED", "IN_TRANSIT", "ASSIGNED", "UNDER_MAINTENANCE", "DAMAGED", "LOST", "DISPOSED"],
  ALLOCATED: ["AVAILABLE", "IN_TRANSIT", "ASSIGNED", "DAMAGED", "LOST"],
  IN_TRANSIT: ["AVAILABLE", "ALLOCATED", "ASSIGNED", "DAMAGED", "LOST"],
  ASSIGNED: ["RETURNED", "DAMAGED", "LOST"],
  RETURNED: ["AVAILABLE", "UNDER_MAINTENANCE", "DAMAGED", "DISPOSED"],
  UNDER_MAINTENANCE: ["AVAILABLE", "DAMAGED", "DISPOSED"],
  DAMAGED: ["UNDER_MAINTENANCE", "DISPOSED"],
  LOST: ["DISPOSED"],
  DISPOSED: [],
};
