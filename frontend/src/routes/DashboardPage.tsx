import { useQuery } from "@tanstack/react-query";
import {
  AlertTriangle,
  Boxes,
  CheckCircle2,
  MapPinned,
  PackageCheck,
  PackageX,
  Printer,
  Truck,
  Users2,
} from "lucide-react";

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
import { useAuthStore } from "@/store/authStore";
import type { DashboardSummary, OfficeItemSummary } from "@/types";

const kpiCards: { key: keyof DashboardSummary; label: string; icon: typeof Boxes }[] = [
  { key: "total_assets", label: "Total Assets", icon: Boxes },
  { key: "available", label: "Available", icon: CheckCircle2 },
  { key: "in_transit", label: "In Transit", icon: Truck },
  { key: "assigned", label: "Assigned", icon: PackageCheck },
  { key: "damaged", label: "Damaged", icon: AlertTriangle },
  { key: "unaccounted", label: "Unaccounted", icon: PackageX },
];

export function DashboardPage() {
  const user = useAuthStore((s) => s.user);
  const { data, isLoading, isError } = useQuery({
    queryKey: ["dashboard-summary"],
    queryFn: () => api.get<DashboardSummary>("/dashboard/summary"),
  });
  const officeItemsQuery = useQuery({
    queryKey: ["dashboard-office-items"],
    queryFn: () => api.get<OfficeItemSummary[]>("/dashboard/office-items"),
  });

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-slate-900">
          Welcome, {user?.first_name ?? "Officer"}
        </h1>
        <p className="text-sm text-slate-500">
          National operations overview — asset readiness, distribution progress and accountability.
        </p>
      </div>

      {isLoading && (
        <div className="flex items-center gap-2 text-sm text-slate-500">
          <Spinner /> Loading dashboard...
        </div>
      )}

      {isError && (
        <div className="rounded-md border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
          Could not load live KPIs — the asset register comes online in a later build phase, so
          these will read zero until then. This card confirms whether the API itself is reachable.
        </div>
      )}

      {data && (
        <>
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-6">
            {kpiCards.map(({ key, label, icon: Icon }) => (
              <Card key={key}>
                <CardContent className="flex flex-col gap-2 p-4">
                  <Icon size={18} className="text-brand-600" />
                  <p className="text-2xl font-semibold text-slate-900">{data[key]}</p>
                  <p className="text-xs text-slate-500">{label}</p>
                </CardContent>
              </Card>
            ))}
          </div>

          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Printer size={16} /> Office &amp; Store Items — National Summary
              </CardTitle>
              <p className="text-xs text-slate-500">
                Quick stock insight for what keeps district offices running — laptops, printers,
                stationery and the like. For per-warehouse detail, use Inventory or Reports.
              </p>
            </CardHeader>
            <CardContent className="p-0">
              {officeItemsQuery.isLoading && (
                <div className="flex items-center gap-2 p-4 text-sm text-slate-500">
                  <Spinner /> Loading...
                </div>
              )}
              {officeItemsQuery.data && (
                <Table>
                  <TableHead>
                    <TableRow>
                      <TableHeaderCell>Item</TableHeaderCell>
                      <TableHeaderCell>Type</TableHeaderCell>
                      <TableHeaderCell>Total</TableHeaderCell>
                      <TableHeaderCell>Available</TableHeaderCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {officeItemsQuery.data.map((item) => (
                      <TableRow key={item.category_name}>
                        <TableCell className="font-medium text-slate-900">{item.category_name}</TableCell>
                        <TableCell>
                          <Badge variant="neutral" className="text-[10px]">
                            {item.tracking_type === "serialized" ? "Equipment" : "Stock"}
                          </Badge>
                        </TableCell>
                        <TableCell>{item.total}</TableCell>
                        <TableCell>{item.available}</TableCell>
                      </TableRow>
                    ))}
                    {officeItemsQuery.data.length === 0 && (
                      <TableRow>
                        <TableCell colSpan={4} className="py-6 text-center text-slate-400">
                          No office-item categories configured yet.
                        </TableCell>
                      </TableRow>
                    )}
                  </TableBody>
                </Table>
              )}
            </CardContent>
          </Card>

          <div className="grid gap-4 sm:grid-cols-3">
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <MapPinned size={16} /> Regions Configured
                </CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-3xl font-semibold text-slate-900">{data.regions_count}</p>
              </CardContent>
            </Card>
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <MapPinned size={16} /> Districts Configured
                </CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-3xl font-semibold text-slate-900">{data.districts_count}</p>
              </CardContent>
            </Card>
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Users2 size={16} /> System Users
                </CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-3xl font-semibold text-slate-900">{data.users_count}</p>
              </CardContent>
            </Card>
          </div>
        </>
      )}

      <footer className="mt-8 border-t border-slate-200 pt-4 text-center text-xs text-slate-400">
        <p className="font-medium text-slate-500">Statistics Sierra Leone (Stats SL)</p>
        <p>A.J. Momoh Street / Tower Hill, P.M.B. 595, Freetown, Sierra Leone</p>
        <p>
          E: info@statistics.sl &middot; T: +232-78-208595 / 30-593333 &middot;{" "}
          <a
            href="https://www.statistics.sl"
            target="_blank"
            rel="noreferrer"
            className="text-brand-600 hover:underline"
          >
            www.statistics.sl
          </a>
        </p>
      </footer>
    </div>
  );
}
