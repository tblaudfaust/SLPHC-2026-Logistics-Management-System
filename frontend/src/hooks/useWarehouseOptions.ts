import { useQuery } from "@tanstack/react-query";

import { api } from "@/lib/api";
import type { LocationRecord, Page, Warehouse } from "@/types";

export function useWarehouseOptions() {
  const locationsQuery = useQuery({
    queryKey: ["locations-for-select"],
    queryFn: () => api.get<Page<LocationRecord>>("/locations", { page_size: 100 }),
  });
  const warehousesQuery = useQuery({
    queryKey: ["warehouses-for-select"],
    queryFn: () => api.get<Page<Warehouse>>("/warehouses", { page_size: 100 }),
  });
  const locationsById = new Map((locationsQuery.data?.items ?? []).map((l) => [l.id, l]));
  const options = (warehousesQuery.data?.items ?? []).map((w) => ({
    id: w.location_id,
    name: locationsById.get(w.location_id)?.name ?? w.code,
  }));
  return { options, isLoading: locationsQuery.isLoading || warehousesQuery.isLoading };
}
