import type { BadgeProps } from "@/components/ui/badge";
import type { FuelRequestStatus, FuelVoucherStatus } from "@/types";

export const REQUEST_STATUS_BADGE_VARIANT: Record<FuelRequestStatus, NonNullable<BadgeProps["variant"]>> = {
  DRAFT: "neutral",
  SUBMITTED: "default",
  UNDER_REVIEW: "warning",
  APPROVED: "success",
  REJECTED: "destructive",
  ISSUED: "default",
  RECEIVED: "success",
  RECONCILED: "neutral",
};

export const REQUEST_STATUS_LABEL: Record<FuelRequestStatus, string> = {
  DRAFT: "Draft",
  SUBMITTED: "Submitted",
  UNDER_REVIEW: "Under Review",
  APPROVED: "Approved",
  REJECTED: "Rejected",
  ISSUED: "Issued",
  RECEIVED: "Received",
  RECONCILED: "Reconciled",
};

// Mirrors backend fuel_service.decide_approval / issue_fuel / acknowledge_receipt
// / reconcile_issue's status checks, so the UI only ever shows an action the
// API will actually accept.
export const REQUEST_STATUS_TRANSITIONS: Record<FuelRequestStatus, FuelRequestStatus[]> = {
  DRAFT: ["SUBMITTED"],
  SUBMITTED: ["UNDER_REVIEW", "REJECTED"],
  UNDER_REVIEW: ["APPROVED", "REJECTED"],
  APPROVED: ["ISSUED"],
  REJECTED: [],
  ISSUED: ["RECEIVED"],
  RECEIVED: ["RECONCILED"],
  RECONCILED: [],
};

export const VOUCHER_STATUS_BADGE_VARIANT: Record<FuelVoucherStatus, NonNullable<BadgeProps["variant"]>> = {
  AVAILABLE: "success",
  ISSUED: "default",
  REDEEMED: "neutral",
  CANCELLED: "destructive",
  LOST: "destructive",
  RECONCILED: "neutral",
};

export const VOUCHER_STATUS_LABEL: Record<FuelVoucherStatus, string> = {
  AVAILABLE: "Available",
  ISSUED: "Issued",
  REDEEMED: "Redeemed",
  CANCELLED: "Cancelled",
  LOST: "Lost",
  RECONCILED: "Reconciled",
};
