import { useQuery } from "@tanstack/react-query";

import { api } from "@/lib/api";
import type { AssetCategory } from "@/types";

export function categoryLabel(category: AssetCategory): string {
  return `${category.name} (${category.code_prefix})`;
}

/** Shared category list for every screen that needs one, filtered
 * server-side to the tracking type that screen actually deals in — the
 * Asset Register only ever registers/filters by serialized categories,
 * Receive/Transfer Stock only by quantity-tracked ones — so every caller
 * asking for the same `trackingType` shares one cached query instead of
 * each screen fetching everything and re-filtering it on its own. */
export function useAssetCategories(trackingType?: "serialized" | "quantity") {
  return useQuery({
    queryKey: ["asset-categories", trackingType ?? "all"],
    queryFn: () => api.get<AssetCategory[]>("/asset-categories", { tracking_type: trackingType }),
  });
}
