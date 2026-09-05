import { useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Spinner } from "@/components/ui/spinner";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeaderCell,
  TableRow,
} from "@/components/ui/table";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";
import type { District, LocationRecord, Page, Region, Warehouse } from "@/types";

export function LocationsPage() {
  const [selectedRegionId, setSelectedRegionId] = useState<string | null>(null);

  const regionsQuery = useQuery({ queryKey: ["regions"], queryFn: () => api.get<Region[]>("/regions") });
  const districtsQuery = useQuery({
    queryKey: ["districts", selectedRegionId],
    queryFn: () => api.get<District[]>("/districts", { region_id: selectedRegionId ?? undefined }),
  });
  const warehousesQuery = useQuery({
    queryKey: ["warehouses"],
    queryFn: () => api.get<Page<Warehouse>>("/warehouses", { page_size: 100 }),
  });
  const locationsQuery = useQuery({
    queryKey: ["locations-for-select"],
    queryFn: () => api.get<Page<LocationRecord>>("/locations", { page_size: 100 }),
  });
  const locationsById = new Map((locationsQuery.data?.items ?? []).map((l) => [l.id, l]));

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-slate-900">Locations &amp; Warehouses</h1>
        <p className="text-sm text-slate-500">
          National administrative geography and logistics facilities.
        </p>
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Regions</CardTitle>
          </CardHeader>
          <CardContent className="space-y-1">
            {regionsQuery.isLoading && <Spinner />}
            <button
              onClick={() => setSelectedRegionId(null)}
              className={cn(
                "w-full rounded-md px-3 py-2 text-left text-sm",
                selectedRegionId === null ? "bg-brand-700 text-white" : "hover:bg-slate-100",
              )}
            >
              All regions
            </button>
            {regionsQuery.data?.map((region) => (
              <button
                key={region.id}
                onClick={() => setSelectedRegionId(region.id)}
                className={cn(
                  "flex w-full items-center justify-between rounded-md px-3 py-2 text-left text-sm",
                  selectedRegionId === region.id ? "bg-brand-700 text-white" : "hover:bg-slate-100",
                )}
              >
                {region.name}
                <Badge variant={selectedRegionId === region.id ? "neutral" : "default"}>
                  {region.code}
                </Badge>
              </button>
            ))}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Districts</CardTitle>
          </CardHeader>
          <CardContent>
            {districtsQuery.isLoading && <Spinner />}
            <Table>
              <TableHead>
                <TableRow>
                  <TableHeaderCell>Name</TableHeaderCell>
                  <TableHeaderCell>Code</TableHeaderCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {districtsQuery.data?.map((d) => (
                  <TableRow key={d.id}>
                    <TableCell>{d.name}</TableCell>
                    <TableCell>{d.code}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Warehouses</CardTitle>
        </CardHeader>
        <CardContent>
          {warehousesQuery.isLoading && <Spinner />}
          <Table>
            <TableHead>
              <TableRow>
                <TableHeaderCell>Code</TableHeaderCell>
                <TableHeaderCell>Name</TableHeaderCell>
                <TableHeaderCell>Scope</TableHeaderCell>
                <TableHeaderCell>Status</TableHeaderCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {warehousesQuery.data?.items.map((w) => {
                const location = locationsById.get(w.location_id);
                const scope = w.is_central
                  ? "Central"
                  : location?.region_id
                    ? "Regional"
                    : location?.district_id
                      ? "District"
                      : "Regional/District";
                return (
                  <TableRow key={w.id}>
                    <TableCell className="font-medium text-slate-900">{w.code}</TableCell>
                    <TableCell>{location?.name ?? "-"}</TableCell>
                    <TableCell>{scope}</TableCell>
                    <TableCell>
                      <Badge variant={w.is_active ? "success" : "neutral"}>
                        {w.is_active ? "Active" : "Inactive"}
                      </Badge>
                    </TableCell>
                  </TableRow>
                );
              })}
              {warehousesQuery.data?.items.length === 0 && (
                <TableRow>
                  <TableCell colSpan={4} className="py-8 text-center text-slate-400">
                    No warehouses registered yet.
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  );
}
