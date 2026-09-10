import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus } from "lucide-react";
import { useState } from "react";
import { useForm } from "react-hook-form";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { z } from "zod";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Dialog } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { Spinner } from "@/components/ui/spinner";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeaderCell,
  TableRow,
} from "@/components/ui/table";
import { useWarehouseOptions } from "@/hooks/useWarehouseOptions";
import { ApiError, api } from "@/lib/api";
import {
  REQUEST_STATUS_BADGE_VARIANT,
  REQUEST_STATUS_LABEL,
  VOUCHER_STATUS_BADGE_VARIANT,
  VOUCHER_STATUS_LABEL,
} from "@/lib/fuelStatus";
import { cn } from "@/lib/utils";
import { useAuthStore } from "@/store/authStore";
import type {
  CensusActivity,
  District,
  FuelAllocation,
  FuelDashboardSummary,
  FuelGenerator,
  FuelRequest,
  FuelRequestStatus,
  FuelStation,
  FuelStockBalance,
  FuelVehicle,
  FuelVoucher,
  FuelVoucherStatus,
  Page,
  Region,
  StarlinkKit,
  Supplier,
} from "@/types";

const TABS = ["dashboard", "requests", "vehicles", "generators", "stations", "allocations", "vouchers", "stock"] as const;
type Tab = (typeof TABS)[number];
const TAB_LABELS: Record<Tab, string> = {
  dashboard: "Dashboard",
  requests: "Requests & Approvals",
  vehicles: "Vehicles",
  generators: "Generators",
  stations: "Fuel Stations",
  allocations: "Allocations",
  vouchers: "Vouchers",
  stock: "Stock",
};

export function FuelPage() {
  const [tab, setTab] = useState<Tab>("dashboard");
  const hasPermission = useAuthStore((s) => s.hasPermission);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-slate-900">Fuel Management</h1>
        <p className="text-sm text-slate-500">
          Allocation, request, approval, issuance, receipt and reconciliation for vehicle,
          generator and Starlink field fuel use.
        </p>
      </div>

      <div className="flex flex-wrap gap-1 border-b border-slate-200">
        {TABS.map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={cn(
              "px-4 py-2 text-sm font-medium",
              tab === t ? "border-b-2 border-brand-700 text-brand-700" : "text-slate-500 hover:text-slate-700",
            )}
          >
            {TAB_LABELS[t]}
          </button>
        ))}
      </div>

      {tab === "dashboard" && <DashboardTab />}
      {tab === "requests" && (
        <RequestsTab
          canRequest={hasPermission("fuel.request")}
          canReview={hasPermission("fuel.approve_review")}
          canApprove={hasPermission("fuel.approve_final")}
          canIssue={hasPermission("fuel.issue")}
          canReceive={hasPermission("fuel.receive")}
          canReconcile={hasPermission("fuel.reconcile")}
        />
      )}
      {tab === "vehicles" && <VehiclesTab canManage={hasPermission("fuel.manage")} />}
      {tab === "generators" && <GeneratorsTab canManage={hasPermission("fuel.manage")} />}
      {tab === "stations" && <StationsTab canManage={hasPermission("fuel.manage")} />}
      {tab === "allocations" && <AllocationsTab canManage={hasPermission("fuel.manage")} />}
      {tab === "vouchers" && <VouchersTab canManage={hasPermission("fuel.manage")} />}
      {tab === "stock" && <StockTab canManage={hasPermission("fuel.manage")} />}
    </div>
  );
}

function Kpi({ label, value, tone }: { label: string; value: string | number; tone?: "warn" | "danger" | "good" }) {
  return (
    <div className="rounded-lg border border-slate-200 bg-white p-4">
      <p
        className={cn(
          "text-2xl font-semibold",
          tone === "danger" ? "text-red-600" : tone === "warn" ? "text-amber-600" : tone === "good" ? "text-emerald-600" : "text-slate-900",
        )}
      >
        {value}
      </p>
      <p className="mt-1 text-xs text-slate-500">{label}</p>
    </div>
  );
}

function DashboardTab() {
  const q = useQuery({
    queryKey: ["fuel-dashboard"],
    queryFn: () => api.get<FuelDashboardSummary>("/fuel/dashboard"),
  });

  if (q.isLoading) {
    return (
      <div className="flex items-center gap-2 text-sm text-slate-500">
        <Spinner /> Loading fuel dashboard...
      </div>
    );
  }
  const d = q.data;
  if (!d) return null;

  return (
    <div className="space-y-6">
      <div>
        <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">Fuel Movement (Litres)</p>
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          <Kpi label="Allocated" value={d.total_allocated_litres.toLocaleString()} />
          <Kpi label="Requested" value={d.total_requested_litres.toLocaleString()} />
          <Kpi label="Approved" value={d.total_approved_litres.toLocaleString()} tone="good" />
          <Kpi label="Issued" value={d.total_issued_litres.toLocaleString()} />
          <Kpi label="Received" value={d.total_received_litres.toLocaleString()} />
          <Kpi label="Consumed" value={d.total_consumed_litres.toLocaleString()} />
          <Kpi label="Remaining Balance" value={d.remaining_balance_litres.toLocaleString()} tone="good" />
          <Kpi label="Total Expenditure" value={`$${d.total_expenditure.toLocaleString()}`} />
        </div>
      </div>

      <div>
        <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">Accountability</p>
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          <Kpi label="Pending Requests" value={d.pending_requests} tone="warn" />
          <Kpi label="Pending Approvals" value={d.pending_approvals} tone="warn" />
          <Kpi label="Unreconciled" value={d.unreconciled_transactions} tone="danger" />
          <Kpi label="Active Vehicles" value={d.active_vehicles} />
          <Kpi label="Active Generators" value={d.active_generators} />
          <Kpi label="Active Starlink Teams" value={d.active_starlink_teams} />
        </div>
      </div>

      {d.consumption_by_region.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Fuel Consumption by Region</CardTitle>
          </CardHeader>
          <CardContent style={{ height: 280 }}>
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={d.consumption_by_region}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                <XAxis dataKey="region" tick={{ fontSize: 12 }} />
                <YAxis tick={{ fontSize: 12 }} />
                <Tooltip />
                <Bar dataKey="litres_issued" name="Litres Issued" fill="#1d4ed8" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>
      )}

      {d.allocation_vs_consumption.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Allocation vs. Consumption (Most Recent 10)</CardTitle>
          </CardHeader>
          <CardContent style={{ height: 300 }}>
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={d.allocation_vs_consumption}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                <XAxis dataKey="allocation_reference" tick={{ fontSize: 10 }} interval={0} angle={-20} textAnchor="end" height={60} />
                <YAxis tick={{ fontSize: 12 }} />
                <Tooltip />
                <Legend />
                <Bar dataKey="allocated" name="Allocated" fill="#94a3b8" radius={[4, 4, 0, 0]} />
                <Bar dataKey="issued" name="Issued" fill="#1d4ed8" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>
      )}
    </div>
  );
}

const requestSchema = z.object({
  region_id: z.string().optional(),
  district_id: z.string().optional(),
  activity_id: z.string().optional(),
  allocation_id: z.string().optional(),
  asset_type: z.enum(["VEHICLE", "GENERATOR", "STARLINK", "OTHER"]),
  vehicle_id: z.string().optional(),
  generator_id: z.string().optional(),
  starlink_kit_id: z.string().optional(),
  fuel_type: z.enum(["PETROL", "DIESEL"]),
  quantity_requested: z.coerce.number().positive("Must be greater than 0"),
  purpose: z.string().optional(),
  destination: z.string().optional(),
  date_required: z.string().optional(),
  current_odometer: z.coerce.number().optional(),
  expected_distance: z.coerce.number().optional(),
  operating_hours: z.coerce.number().optional(),
});
type RequestValues = z.infer<typeof requestSchema>;

const decisionSchema = z.object({
  decision: z.enum(["APPROVED", "REJECTED"]),
  approved_quantity: z.coerce.number().optional(),
  comments: z.string().optional(),
});
type DecisionValues = z.infer<typeof decisionSchema>;

const issueSchema = z.object({
  supplier_id: z.string().optional(),
  fuel_station_id: z.string().optional(),
  quantity_issued: z.coerce.number().positive(),
  price_per_litre: z.coerce.number().optional(),
  voucher_number: z.string().optional(),
  witness_name: z.string().optional(),
  issue_date: z.string().min(1, "Required"),
  odometer_reading: z.coerce.number().optional(),
  comments: z.string().optional(),
  depot_location_id: z.string().min(1, "Choose a depot"),
});
type IssueValues = z.infer<typeof issueSchema>;

const receiveSchema = z.object({
  quantity_received: z.coerce.number().positive(),
  date_received: z.string().min(1, "Required"),
  receipt_number: z.string().optional(),
  remarks: z.string().optional(),
});
type ReceiveValues = z.infer<typeof receiveSchema>;

const reconcileSchema = z.object({
  quantity_used: z.coerce.number().optional(),
  distance_travelled: z.coerce.number().optional(),
  hours_operated: z.coerce.number().optional(),
  comments: z.string().optional(),
  reconciliation_date: z.string().min(1, "Required"),
});
type ReconcileValues = z.infer<typeof reconcileSchema>;

function RequestsTab({
  canRequest, canReview, canApprove, canIssue, canReceive, canReconcile,
}: {
  canRequest: boolean; canReview: boolean; canApprove: boolean;
  canIssue: boolean; canReceive: boolean; canReconcile: boolean;
}) {
  const [createOpen, setCreateOpen] = useState(false);
  const [actionRequest, setActionRequest] = useState<FuelRequest | null>(null);
  const [action, setAction] = useState<"review" | "approve" | "issue" | "receive" | "reconcile" | null>(null);
  const queryClient = useQueryClient();

  const requestsQuery = useQuery({
    queryKey: ["fuel-requests"],
    queryFn: () => api.get<Page<FuelRequest>>("/fuel/requests", { page_size: 50 }),
  });

  function invalidate() {
    queryClient.invalidateQueries({ queryKey: ["fuel-requests"] });
    queryClient.invalidateQueries({ queryKey: ["fuel-dashboard"] });
    queryClient.invalidateQueries({ queryKey: ["fuel-stock"] });
    queryClient.invalidateQueries({ queryKey: ["fuel-allocations"] });
    setActionRequest(null);
    setAction(null);
  }

  function openAction(request: FuelRequest, act: typeof action) {
    setActionRequest(request);
    setAction(act);
  }

  function availableAction(status: FuelRequestStatus): { label: string; act: NonNullable<typeof action> } | null {
    if (status === "SUBMITTED" && canReview) return { label: "Review", act: "review" };
    if (status === "UNDER_REVIEW" && canApprove) return { label: "Final Approve", act: "approve" };
    if (status === "APPROVED" && canIssue) return { label: "Issue Fuel", act: "issue" };
    if (status === "ISSUED" && canReceive) return { label: "Acknowledge Receipt", act: "receive" };
    if (status === "RECEIVED" && canReconcile) return { label: "Reconcile", act: "reconcile" };
    return null;
  }

  return (
    <div className="space-y-4">
      {canRequest && (
        <div className="flex justify-end">
          <Button onClick={() => setCreateOpen(true)}>
            <Plus size={16} /> New fuel request
          </Button>
        </div>
      )}

      {requestsQuery.isLoading && (
        <div className="flex items-center gap-2 text-sm text-slate-500">
          <Spinner /> Loading requests...
        </div>
      )}

      {requestsQuery.data && (
        <Table>
          <TableHead>
            <TableRow>
              <TableHeaderCell>Reference</TableHeaderCell>
              <TableHeaderCell>Requester</TableHeaderCell>
              <TableHeaderCell>Asset</TableHeaderCell>
              <TableHeaderCell>Fuel</TableHeaderCell>
              <TableHeaderCell>Requested</TableHeaderCell>
              <TableHeaderCell>Status</TableHeaderCell>
              <TableHeaderCell></TableHeaderCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {requestsQuery.data.items.map((r) => {
              const next = availableAction(r.status);
              return (
                <TableRow key={r.id}>
                  <TableCell className="font-medium text-slate-900">{r.request_reference}</TableCell>
                  <TableCell>{r.requester.first_name} {r.requester.last_name}</TableCell>
                  <TableCell>
                    {r.asset_type === "VEHICLE" && r.vehicle ? r.vehicle.registration_number : r.asset_type}
                  </TableCell>
                  <TableCell>{r.fuel_type}</TableCell>
                  <TableCell>{r.quantity_requested}L</TableCell>
                  <TableCell>
                    <Badge variant={REQUEST_STATUS_BADGE_VARIANT[r.status]}>{REQUEST_STATUS_LABEL[r.status]}</Badge>
                  </TableCell>
                  <TableCell>
                    {next && (
                      <Button size="sm" variant="secondary" onClick={() => openAction(r, next.act)}>
                        {next.label}
                      </Button>
                    )}
                  </TableCell>
                </TableRow>
              );
            })}
            {requestsQuery.data.items.length === 0 && (
              <TableRow>
                <TableCell colSpan={7} className="py-8 text-center text-slate-400">
                  No fuel requests yet.
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      )}

      <Dialog open={createOpen} onClose={() => setCreateOpen(false)} title="New fuel request" className="max-w-2xl">
        <CreateRequestForm
          onCreated={() => {
            setCreateOpen(false);
            invalidate();
          }}
        />
      </Dialog>

      <Dialog
        open={action === "review" || action === "approve"}
        onClose={() => { setActionRequest(null); setAction(null); }}
        title={action === "review" ? "Director review" : "Final approval"}
      >
        {actionRequest && (
          <DecisionForm
            request={actionRequest}
            level={action === "review" ? 1 : 2}
            onDone={invalidate}
          />
        )}
      </Dialog>

      <Dialog
        open={action === "issue"}
        onClose={() => { setActionRequest(null); setAction(null); }}
        title="Issue fuel"
        className="max-w-xl"
      >
        {actionRequest && <IssueForm request={actionRequest} onDone={invalidate} />}
      </Dialog>

      <Dialog
        open={action === "receive"}
        onClose={() => { setActionRequest(null); setAction(null); }}
        title="Acknowledge receipt"
      >
        {actionRequest?.issue && <ReceiveForm issueId={actionRequest.issue.id} onDone={invalidate} />}
      </Dialog>

      <Dialog
        open={action === "reconcile"}
        onClose={() => { setActionRequest(null); setAction(null); }}
        title="Reconcile fuel usage"
      >
        {actionRequest?.issue && <ReconcileForm issueId={actionRequest.issue.id} onDone={invalidate} />}
      </Dialog>
    </div>
  );
}

function CreateRequestForm({ onCreated }: { onCreated: () => void }) {
  const {
    register, handleSubmit, watch, formState: { errors },
  } = useForm<RequestValues>({
    resolver: zodResolver(requestSchema),
    defaultValues: { asset_type: "VEHICLE", fuel_type: "DIESEL" },
  });
  const assetType = watch("asset_type");

  const regionsQuery = useQuery({ queryKey: ["regions"], queryFn: () => api.get<Region[]>("/regions") });
  const districtsQuery = useQuery({ queryKey: ["districts"], queryFn: () => api.get<District[]>("/districts") });
  const activitiesQuery = useQuery({
    queryKey: ["fuel-activities"], queryFn: () => api.get<CensusActivity[]>("/fuel/activities"),
  });
  const allocationsQuery = useQuery({
    queryKey: ["fuel-allocations"], queryFn: () => api.get<FuelAllocation[]>("/fuel/allocations"),
  });
  const vehiclesQuery = useQuery({
    queryKey: ["fuel-vehicles-for-select"],
    queryFn: () => api.get<Page<FuelVehicle>>("/fuel/vehicles", { page_size: 200 }),
    enabled: assetType === "VEHICLE",
  });
  const generatorsQuery = useQuery({
    queryKey: ["fuel-generators-for-select"],
    queryFn: () => api.get<Page<FuelGenerator>>("/fuel/generators", { page_size: 200 }),
    enabled: assetType === "GENERATOR",
  });
  const starlinkKitsQuery = useQuery({
    queryKey: ["starlink-kits-for-select"],
    queryFn: () => api.get<Page<StarlinkKit>>("/starlink", { page_size: 200 }),
    enabled: assetType === "STARLINK",
  });

  const createMutation = useMutation({
    mutationFn: (values: RequestValues) =>
      api.post("/fuel/requests", {
        ...values,
        region_id: values.region_id || undefined,
        district_id: values.district_id || undefined,
        activity_id: values.activity_id || undefined,
        allocation_id: values.allocation_id || undefined,
        vehicle_id: values.vehicle_id || undefined,
        generator_id: values.generator_id || undefined,
        starlink_kit_id: values.starlink_kit_id || undefined,
        date_required: values.date_required || undefined,
      }),
    onSuccess: onCreated,
  });

  return (
    <form onSubmit={handleSubmit((v) => createMutation.mutate(v))} className="max-h-[70vh] space-y-4 overflow-y-auto pr-1">
      <div className="grid grid-cols-2 gap-4">
        <div className="space-y-1.5">
          <Label htmlFor="asset_type">Asset type</Label>
          <Select id="asset_type" {...register("asset_type")}>
            <option value="VEHICLE">Vehicle</option>
            <option value="GENERATOR">Generator</option>
            <option value="STARLINK">Starlink kit</option>
            <option value="OTHER">Other</option>
          </Select>
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="fuel_type">Fuel type</Label>
          <Select id="fuel_type" {...register("fuel_type")}>
            <option value="DIESEL">Diesel</option>
            <option value="PETROL">Petrol</option>
          </Select>
        </div>
      </div>

      {assetType === "VEHICLE" && (
        <div className="space-y-1.5">
          <Label htmlFor="vehicle_id">Vehicle</Label>
          <Select id="vehicle_id" {...register("vehicle_id")}>
            <option value="">Select a vehicle...</option>
            {vehiclesQuery.data?.items.map((v) => (
              <option key={v.id} value={v.id}>{v.registration_number} ({v.asset.asset_tag})</option>
            ))}
          </Select>
        </div>
      )}
      {assetType === "GENERATOR" && (
        <div className="space-y-1.5">
          <Label htmlFor="generator_id">Generator</Label>
          <Select id="generator_id" {...register("generator_id")}>
            <option value="">Select a generator...</option>
            {generatorsQuery.data?.items.map((g) => (
              <option key={g.id} value={g.id}>{g.asset.asset_tag}</option>
            ))}
          </Select>
        </div>
      )}
      {assetType === "STARLINK" && (
        <div className="space-y-1.5">
          <Label htmlFor="starlink_kit_id">Starlink kit</Label>
          <Select id="starlink_kit_id" {...register("starlink_kit_id")}>
            <option value="">Select a kit...</option>
            {starlinkKitsQuery.data?.items.map((k) => (
              <option key={k.id} value={k.id}>{k.asset.asset_tag}</option>
            ))}
          </Select>
        </div>
      )}

      <div className="grid grid-cols-2 gap-4">
        <div className="space-y-1.5">
          <Label htmlFor="quantity_requested">Quantity (Litres)</Label>
          <Input id="quantity_requested" type="number" step="0.01" {...register("quantity_requested")} />
          {errors.quantity_requested && <p className="text-xs text-red-600">{errors.quantity_requested.message}</p>}
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="date_required">Date required</Label>
          <Input id="date_required" type="date" {...register("date_required")} />
        </div>
      </div>

      {assetType === "VEHICLE" && (
        <div className="grid grid-cols-2 gap-4">
          <div className="space-y-1.5">
            <Label htmlFor="current_odometer">Current odometer</Label>
            <Input id="current_odometer" type="number" {...register("current_odometer")} />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="expected_distance">Expected distance (km)</Label>
            <Input id="expected_distance" type="number" {...register("expected_distance")} />
          </div>
        </div>
      )}
      {assetType === "GENERATOR" && (
        <div className="space-y-1.5">
          <Label htmlFor="operating_hours">Expected operating hours</Label>
          <Input id="operating_hours" type="number" step="0.1" {...register("operating_hours")} />
        </div>
      )}

      <div className="space-y-1.5">
        <Label htmlFor="allocation_id">Draw against allocation (optional)</Label>
        <Select id="allocation_id" {...register("allocation_id")}>
          <option value="">Unspecified</option>
          {allocationsQuery.data?.map((a) => (
            <option key={a.id} value={a.id}>
              {a.allocation_reference} — {a.litres_remaining.toFixed(0)}L remaining
            </option>
          ))}
        </Select>
      </div>

      <div className="grid grid-cols-3 gap-4">
        <div className="space-y-1.5">
          <Label htmlFor="region_id">Region</Label>
          <Select id="region_id" {...register("region_id")}>
            <option value="">Unspecified</option>
            {regionsQuery.data?.map((r) => <option key={r.id} value={r.id}>{r.name}</option>)}
          </Select>
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="district_id">District</Label>
          <Select id="district_id" {...register("district_id")}>
            <option value="">Unspecified</option>
            {districtsQuery.data?.map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}
          </Select>
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="activity_id">Activity</Label>
          <Select id="activity_id" {...register("activity_id")}>
            <option value="">Unspecified</option>
            {activitiesQuery.data?.map((a) => <option key={a.id} value={a.id}>{a.name}</option>)}
          </Select>
        </div>
      </div>

      <div className="space-y-1.5">
        <Label htmlFor="purpose">Purpose</Label>
        <Input id="purpose" {...register("purpose")} />
      </div>
      <div className="space-y-1.5">
        <Label htmlFor="destination">Destination</Label>
        <Input id="destination" {...register("destination")} />
      </div>

      {createMutation.error instanceof ApiError && (
        <p className="text-xs text-red-600">{createMutation.error.message}</p>
      )}
      <Button type="submit" className="w-full" disabled={createMutation.isPending}>
        {createMutation.isPending ? "Submitting..." : "Submit request"}
      </Button>
    </form>
  );
}

function DecisionForm({ request, level, onDone }: { request: FuelRequest; level: 1 | 2; onDone: () => void }) {
  const {
    register, handleSubmit, watch,
  } = useForm<DecisionValues>({ resolver: zodResolver(decisionSchema), defaultValues: { decision: "APPROVED" } });
  const decision = watch("decision");

  const mutation = useMutation({
    mutationFn: (values: DecisionValues) =>
      api.post(`/fuel/requests/${request.id}/${level === 1 ? "review" : "approve"}`, {
        ...values,
        approved_quantity: values.decision === "APPROVED" ? values.approved_quantity : undefined,
      }),
    onSuccess: onDone,
  });

  return (
    <form onSubmit={handleSubmit((v) => mutation.mutate(v))} className="space-y-4">
      <p className="text-sm text-slate-600">
        {request.request_reference} — <strong>{request.quantity_requested}L</strong> {request.fuel_type} requested by{" "}
        {request.requester.first_name} {request.requester.last_name}.
      </p>
      <div className="space-y-1.5">
        <Label htmlFor="decision">Decision</Label>
        <Select id="decision" {...register("decision")}>
          <option value="APPROVED">Approve</option>
          <option value="REJECTED">Reject</option>
        </Select>
      </div>
      {decision === "APPROVED" && (
        <div className="space-y-1.5">
          <Label htmlFor="approved_quantity">Approved quantity (Litres)</Label>
          <Input
            id="approved_quantity" type="number" step="0.01"
            defaultValue={request.quantity_requested}
            {...register("approved_quantity")}
          />
        </div>
      )}
      <div className="space-y-1.5">
        <Label htmlFor="comments">Comments</Label>
        <Input id="comments" {...register("comments")} />
      </div>
      {mutation.error instanceof ApiError && <p className="text-xs text-red-600">{mutation.error.message}</p>}
      <Button type="submit" className="w-full" disabled={mutation.isPending}>
        {mutation.isPending ? "Saving..." : decision === "APPROVED" ? "Approve" : "Reject"}
      </Button>
    </form>
  );
}

function IssueForm({ request, onDone }: { request: FuelRequest; onDone: () => void }) {
  const { register, handleSubmit } = useForm<IssueValues>({
    resolver: zodResolver(issueSchema),
    defaultValues: { issue_date: new Date().toISOString().slice(0, 10) },
  });
  const suppliersQuery = useQuery({ queryKey: ["suppliers"], queryFn: () => api.get<Page<Supplier>>("/suppliers", { page_size: 100 }) });
  const stationsQuery = useQuery({ queryKey: ["fuel-stations"], queryFn: () => api.get<FuelStation[]>("/fuel/stations") });
  const { options: warehouseOptions } = useWarehouseOptions();

  const mutation = useMutation({
    mutationFn: (values: IssueValues) =>
      api.post(`/fuel/requests/${request.id}/issue`, {
        ...values,
        fuel_request_id: request.id,
        supplier_id: values.supplier_id || undefined,
        fuel_station_id: values.fuel_station_id || undefined,
      }),
    onSuccess: onDone,
  });

  return (
    <form onSubmit={handleSubmit((v) => mutation.mutate(v))} className="space-y-4">
      <p className="text-sm text-slate-600">
        Approved: <strong>{request.approvals.find((a) => a.approval_level === 2)?.approved_quantity ?? "-"}L</strong>
      </p>
      <div className="grid grid-cols-2 gap-4">
        <div className="space-y-1.5">
          <Label htmlFor="quantity_issued">Quantity to issue (L)</Label>
          <Input id="quantity_issued" type="number" step="0.01" {...register("quantity_issued")} />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="price_per_litre">Price per litre</Label>
          <Input id="price_per_litre" type="number" step="0.01" {...register("price_per_litre")} />
        </div>
      </div>
      <div className="space-y-1.5">
        <Label htmlFor="depot_location_id">Depot</Label>
        <Select id="depot_location_id" {...register("depot_location_id")}>
          <option value="">Select a depot...</option>
          {warehouseOptions.map((w) => <option key={w.id} value={w.id}>{w.name}</option>)}
        </Select>
      </div>
      <div className="grid grid-cols-2 gap-4">
        <div className="space-y-1.5">
          <Label htmlFor="supplier_id">Supplier (optional)</Label>
          <Select id="supplier_id" {...register("supplier_id")}>
            <option value="">Unspecified</option>
            {suppliersQuery.data?.items.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
          </Select>
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="fuel_station_id">Fuel station (optional)</Label>
          <Select id="fuel_station_id" {...register("fuel_station_id")}>
            <option value="">Unspecified</option>
            {stationsQuery.data?.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
          </Select>
        </div>
      </div>
      <div className="grid grid-cols-2 gap-4">
        <div className="space-y-1.5">
          <Label htmlFor="issue_date">Issue date</Label>
          <Input id="issue_date" type="date" {...register("issue_date")} />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="odometer_reading">Odometer / hour-meter reading</Label>
          <Input id="odometer_reading" type="number" {...register("odometer_reading")} />
        </div>
      </div>
      <div className="space-y-1.5">
        <Label htmlFor="witness_name">Witness (optional)</Label>
        <Input id="witness_name" {...register("witness_name")} />
      </div>
      {mutation.error instanceof ApiError && <p className="text-xs text-red-600">{mutation.error.message}</p>}
      <Button type="submit" className="w-full" disabled={mutation.isPending}>
        {mutation.isPending ? "Issuing..." : "Issue fuel"}
      </Button>
    </form>
  );
}

function ReceiveForm({ issueId, onDone }: { issueId: string; onDone: () => void }) {
  const { register, handleSubmit } = useForm<ReceiveValues>({
    resolver: zodResolver(receiveSchema),
    defaultValues: { date_received: new Date().toISOString().slice(0, 10) },
  });
  const mutation = useMutation({
    mutationFn: (values: ReceiveValues) => api.post(`/fuel/issues/${issueId}/receive`, values),
    onSuccess: onDone,
  });

  return (
    <form onSubmit={handleSubmit((v) => mutation.mutate(v))} className="space-y-4">
      <div className="space-y-1.5">
        <Label htmlFor="quantity_received">Quantity received (L)</Label>
        <Input id="quantity_received" type="number" step="0.01" {...register("quantity_received")} />
      </div>
      <div className="space-y-1.5">
        <Label htmlFor="date_received">Date received</Label>
        <Input id="date_received" type="date" {...register("date_received")} />
      </div>
      <div className="space-y-1.5">
        <Label htmlFor="receipt_number">Receipt number (optional)</Label>
        <Input id="receipt_number" {...register("receipt_number")} />
      </div>
      <div className="space-y-1.5">
        <Label htmlFor="remarks">Remarks</Label>
        <Input id="remarks" {...register("remarks")} />
      </div>
      {mutation.error instanceof ApiError && <p className="text-xs text-red-600">{mutation.error.message}</p>}
      <Button type="submit" className="w-full" disabled={mutation.isPending}>
        {mutation.isPending ? "Confirming..." : "Confirm receipt"}
      </Button>
    </form>
  );
}

function ReconcileForm({ issueId, onDone }: { issueId: string; onDone: () => void }) {
  const { register, handleSubmit } = useForm<ReconcileValues>({
    resolver: zodResolver(reconcileSchema),
    defaultValues: { reconciliation_date: new Date().toISOString().slice(0, 10) },
  });
  const mutation = useMutation({
    mutationFn: (values: ReconcileValues) => api.post(`/fuel/issues/${issueId}/reconcile`, values),
    onSuccess: onDone,
  });

  return (
    <form onSubmit={handleSubmit((v) => mutation.mutate(v))} className="space-y-4">
      <div className="space-y-1.5">
        <Label htmlFor="quantity_used">Quantity actually used (L)</Label>
        <Input id="quantity_used" type="number" step="0.01" {...register("quantity_used")} />
      </div>
      <div className="grid grid-cols-2 gap-4">
        <div className="space-y-1.5">
          <Label htmlFor="distance_travelled">Distance travelled (km)</Label>
          <Input id="distance_travelled" type="number" {...register("distance_travelled")} />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="hours_operated">Hours operated</Label>
          <Input id="hours_operated" type="number" step="0.1" {...register("hours_operated")} />
        </div>
      </div>
      <div className="space-y-1.5">
        <Label htmlFor="reconciliation_date">Reconciliation date</Label>
        <Input id="reconciliation_date" type="date" {...register("reconciliation_date")} />
      </div>
      <div className="space-y-1.5">
        <Label htmlFor="comments">Comments</Label>
        <Input id="comments" {...register("comments")} />
      </div>
      {mutation.error instanceof ApiError && <p className="text-xs text-red-600">{mutation.error.message}</p>}
      <Button type="submit" className="w-full" disabled={mutation.isPending}>
        {mutation.isPending ? "Saving..." : "Reconcile"}
      </Button>
    </form>
  );
}

const vehicleSchema = z.object({
  registration_number: z.string().min(1, "Required"),
  vehicle_type: z.enum(["CAR", "PICKUP", "SUV", "TRUCK", "BUS", "MOTORCYCLE", "OTHER"]),
  make: z.string().optional(),
  model: z.string().optional(),
  fuel_type: z.enum(["PETROL", "DIESEL"]),
  tank_capacity: z.coerce.number().optional(),
  assigned_driver_name: z.string().optional(),
  current_odometer: z.coerce.number().default(0),
  current_location_id: z.string().optional(),
});
type VehicleValues = z.infer<typeof vehicleSchema>;

function VehiclesTab({ canManage }: { canManage: boolean }) {
  const [dialogOpen, setDialogOpen] = useState(false);
  const queryClient = useQueryClient();
  const { options: warehouseOptions } = useWarehouseOptions();

  const vehiclesQuery = useQuery({
    queryKey: ["fuel-vehicles"],
    queryFn: () => api.get<Page<FuelVehicle>>("/fuel/vehicles", { page_size: 50 }),
  });

  const { register, handleSubmit, reset } = useForm<VehicleValues>({
    resolver: zodResolver(vehicleSchema),
    defaultValues: { vehicle_type: "CAR", fuel_type: "DIESEL", current_odometer: 0 },
  });

  const createMutation = useMutation({
    mutationFn: (values: VehicleValues) =>
      api.post("/fuel/vehicles", { ...values, current_location_id: values.current_location_id || undefined, condition: "NEW" }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["fuel-vehicles"] });
      setDialogOpen(false);
      reset();
    },
  });

  return (
    <div className="space-y-4">
      {canManage && (
        <div className="flex justify-end">
          <Button onClick={() => setDialogOpen(true)}><Plus size={16} /> Register vehicle</Button>
        </div>
      )}
      {vehiclesQuery.isLoading && (
        <div className="flex items-center gap-2 text-sm text-slate-500"><Spinner /> Loading vehicles...</div>
      )}
      {vehiclesQuery.data && (
        <Table>
          <TableHead>
            <TableRow>
              <TableHeaderCell>Asset Tag</TableHeaderCell>
              <TableHeaderCell>Registration</TableHeaderCell>
              <TableHeaderCell>Type</TableHeaderCell>
              <TableHeaderCell>Make / Model</TableHeaderCell>
              <TableHeaderCell>Fuel</TableHeaderCell>
              <TableHeaderCell>Driver</TableHeaderCell>
              <TableHeaderCell>Odometer</TableHeaderCell>
              <TableHeaderCell>Status</TableHeaderCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {vehiclesQuery.data.items.map((v) => (
              <TableRow key={v.id}>
                <TableCell className="font-medium text-slate-900">{v.asset.asset_tag}</TableCell>
                <TableCell>{v.registration_number}</TableCell>
                <TableCell>{v.vehicle_type}</TableCell>
                <TableCell>{[v.make, v.model].filter(Boolean).join(" ") || "-"}</TableCell>
                <TableCell>{v.fuel_type}</TableCell>
                <TableCell>{v.assigned_driver_name ?? "-"}</TableCell>
                <TableCell>{v.current_odometer.toLocaleString()} km</TableCell>
                <TableCell><Badge variant="neutral">{v.asset.status}</Badge></TableCell>
              </TableRow>
            ))}
            {vehiclesQuery.data.items.length === 0 && (
              <TableRow><TableCell colSpan={8} className="py-8 text-center text-slate-400">No vehicles registered yet.</TableCell></TableRow>
            )}
          </TableBody>
        </Table>
      )}
      <Dialog open={dialogOpen} onClose={() => setDialogOpen(false)} title="Register vehicle" className="max-w-xl">
        <form onSubmit={handleSubmit((v) => createMutation.mutate(v))} className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-1.5">
              <Label htmlFor="registration_number">Registration number</Label>
              <Input id="registration_number" {...register("registration_number")} />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="vehicle_type">Type</Label>
              <Select id="vehicle_type" {...register("vehicle_type")}>
                {["CAR", "PICKUP", "SUV", "TRUCK", "BUS", "MOTORCYCLE", "OTHER"].map((t) => (
                  <option key={t} value={t}>{t}</option>
                ))}
              </Select>
            </div>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-1.5"><Label htmlFor="make">Make</Label><Input id="make" {...register("make")} /></div>
            <div className="space-y-1.5"><Label htmlFor="model">Model</Label><Input id="model" {...register("model")} /></div>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-1.5">
              <Label htmlFor="fuel_type">Fuel type</Label>
              <Select id="fuel_type" {...register("fuel_type")}>
                <option value="DIESEL">Diesel</option>
                <option value="PETROL">Petrol</option>
              </Select>
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="tank_capacity">Tank capacity (L)</Label>
              <Input id="tank_capacity" type="number" {...register("tank_capacity")} />
            </div>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-1.5">
              <Label htmlFor="assigned_driver_name">Assigned driver</Label>
              <Input id="assigned_driver_name" {...register("assigned_driver_name")} />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="current_odometer">Current odometer</Label>
              <Input id="current_odometer" type="number" {...register("current_odometer")} />
            </div>
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="current_location_id">Current location</Label>
            <Select id="current_location_id" {...register("current_location_id")}>
              <option value="">Unassigned</option>
              {warehouseOptions.map((w) => <option key={w.id} value={w.id}>{w.name}</option>)}
            </Select>
          </div>
          {createMutation.error instanceof ApiError && <p className="text-xs text-red-600">{createMutation.error.message}</p>}
          <Button type="submit" className="w-full" disabled={createMutation.isPending}>
            {createMutation.isPending ? "Registering..." : "Register vehicle"}
          </Button>
        </form>
      </Dialog>
    </div>
  );
}

const generatorSchema = z.object({
  capacity_kva: z.coerce.number().optional(),
  fuel_type: z.enum(["PETROL", "DIESEL"]),
  current_hour_meter: z.coerce.number().default(0),
  current_location_id: z.string().optional(),
});
type GeneratorValues = z.infer<typeof generatorSchema>;

function GeneratorsTab({ canManage }: { canManage: boolean }) {
  const [dialogOpen, setDialogOpen] = useState(false);
  const queryClient = useQueryClient();
  const { options: warehouseOptions } = useWarehouseOptions();

  const generatorsQuery = useQuery({
    queryKey: ["fuel-generators"],
    queryFn: () => api.get<Page<FuelGenerator>>("/fuel/generators", { page_size: 50 }),
  });

  const { register, handleSubmit, reset } = useForm<GeneratorValues>({
    resolver: zodResolver(generatorSchema),
    defaultValues: { fuel_type: "DIESEL", current_hour_meter: 0 },
  });

  const createMutation = useMutation({
    mutationFn: (values: GeneratorValues) =>
      api.post("/fuel/generators", { ...values, current_location_id: values.current_location_id || undefined, condition: "NEW" }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["fuel-generators"] });
      setDialogOpen(false);
      reset();
    },
  });

  return (
    <div className="space-y-4">
      {canManage && (
        <div className="flex justify-end">
          <Button onClick={() => setDialogOpen(true)}><Plus size={16} /> Register generator</Button>
        </div>
      )}
      {generatorsQuery.isLoading && (
        <div className="flex items-center gap-2 text-sm text-slate-500"><Spinner /> Loading generators...</div>
      )}
      {generatorsQuery.data && (
        <Table>
          <TableHead>
            <TableRow>
              <TableHeaderCell>Asset Tag</TableHeaderCell>
              <TableHeaderCell>Capacity (kVA)</TableHeaderCell>
              <TableHeaderCell>Fuel</TableHeaderCell>
              <TableHeaderCell>Hour Meter</TableHeaderCell>
              <TableHeaderCell>Status</TableHeaderCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {generatorsQuery.data.items.map((g) => (
              <TableRow key={g.id}>
                <TableCell className="font-medium text-slate-900">{g.asset.asset_tag}</TableCell>
                <TableCell>{g.capacity_kva ?? "-"}</TableCell>
                <TableCell>{g.fuel_type}</TableCell>
                <TableCell>{g.current_hour_meter.toLocaleString()} hrs</TableCell>
                <TableCell><Badge variant="neutral">{g.asset.status}</Badge></TableCell>
              </TableRow>
            ))}
            {generatorsQuery.data.items.length === 0 && (
              <TableRow><TableCell colSpan={5} className="py-8 text-center text-slate-400">No generators registered yet.</TableCell></TableRow>
            )}
          </TableBody>
        </Table>
      )}
      <Dialog open={dialogOpen} onClose={() => setDialogOpen(false)} title="Register generator" className="max-w-lg">
        <form onSubmit={handleSubmit((v) => createMutation.mutate(v))} className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-1.5">
              <Label htmlFor="capacity_kva">Capacity (kVA)</Label>
              <Input id="capacity_kva" type="number" {...register("capacity_kva")} />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="fuel_type">Fuel type</Label>
              <Select id="fuel_type" {...register("fuel_type")}>
                <option value="DIESEL">Diesel</option>
                <option value="PETROL">Petrol</option>
              </Select>
            </div>
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="current_hour_meter">Current hour meter</Label>
            <Input id="current_hour_meter" type="number" step="0.1" {...register("current_hour_meter")} />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="current_location_id">Current location</Label>
            <Select id="current_location_id" {...register("current_location_id")}>
              <option value="">Unassigned</option>
              {warehouseOptions.map((w) => <option key={w.id} value={w.id}>{w.name}</option>)}
            </Select>
          </div>
          {createMutation.error instanceof ApiError && <p className="text-xs text-red-600">{createMutation.error.message}</p>}
          <Button type="submit" className="w-full" disabled={createMutation.isPending}>
            {createMutation.isPending ? "Registering..." : "Register generator"}
          </Button>
        </form>
      </Dialog>
    </div>
  );
}

const stationSchema = z.object({
  supplier_id: z.string().min(1, "Choose a supplier"),
  name: z.string().min(1, "Required"),
  location_id: z.string().optional(),
});
type StationValues = z.infer<typeof stationSchema>;

function StationsTab({ canManage }: { canManage: boolean }) {
  const [dialogOpen, setDialogOpen] = useState(false);
  const queryClient = useQueryClient();
  const { options: warehouseOptions } = useWarehouseOptions();
  const suppliersQuery = useQuery({ queryKey: ["suppliers"], queryFn: () => api.get<Page<Supplier>>("/suppliers", { page_size: 100 }) });

  const stationsQuery = useQuery({ queryKey: ["fuel-stations"], queryFn: () => api.get<FuelStation[]>("/fuel/stations") });

  const { register, handleSubmit, reset } = useForm<StationValues>({ resolver: zodResolver(stationSchema) });

  const createMutation = useMutation({
    mutationFn: (values: StationValues) =>
      api.post("/fuel/stations", { ...values, location_id: values.location_id || undefined }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["fuel-stations"] });
      setDialogOpen(false);
      reset();
    },
  });

  return (
    <div className="space-y-4">
      {canManage && (
        <div className="flex justify-end">
          <Button onClick={() => setDialogOpen(true)}><Plus size={16} /> New fuel station</Button>
        </div>
      )}
      {stationsQuery.data && (
        <Table>
          <TableHead>
            <TableRow>
              <TableHeaderCell>Name</TableHeaderCell>
              <TableHeaderCell>Location</TableHeaderCell>
              <TableHeaderCell>Status</TableHeaderCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {stationsQuery.data.map((s) => (
              <TableRow key={s.id}>
                <TableCell className="font-medium text-slate-900">{s.name}</TableCell>
                <TableCell>{s.location?.name ?? "-"}</TableCell>
                <TableCell><Badge variant={s.is_active ? "success" : "neutral"}>{s.is_active ? "Active" : "Inactive"}</Badge></TableCell>
              </TableRow>
            ))}
            {stationsQuery.data.length === 0 && (
              <TableRow><TableCell colSpan={3} className="py-8 text-center text-slate-400">No fuel stations yet.</TableCell></TableRow>
            )}
          </TableBody>
        </Table>
      )}
      <Dialog open={dialogOpen} onClose={() => setDialogOpen(false)} title="New fuel station">
        <form onSubmit={handleSubmit((v) => createMutation.mutate(v))} className="space-y-4">
          <div className="space-y-1.5">
            <Label htmlFor="supplier_id">Supplier / vendor</Label>
            <Select id="supplier_id" {...register("supplier_id")}>
              <option value="">Select a supplier...</option>
              {suppliersQuery.data?.items.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
            </Select>
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="name">Station name</Label>
            <Input id="name" {...register("name")} />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="location_id">Location (optional)</Label>
            <Select id="location_id" {...register("location_id")}>
              <option value="">Unspecified</option>
              {warehouseOptions.map((w) => <option key={w.id} value={w.id}>{w.name}</option>)}
            </Select>
          </div>
          {createMutation.error instanceof ApiError && <p className="text-xs text-red-600">{createMutation.error.message}</p>}
          <Button type="submit" className="w-full" disabled={createMutation.isPending}>
            {createMutation.isPending ? "Saving..." : "Save station"}
          </Button>
        </form>
      </Dialog>
    </div>
  );
}

const allocationSchema = z.object({
  region_id: z.string().optional(),
  district_id: z.string().optional(),
  activity_id: z.string().optional(),
  fuel_type: z.enum(["PETROL", "DIESEL"]),
  allocated_litres: z.coerce.number().positive(),
  allocated_budget: z.coerce.number().optional(),
  start_date: z.string().min(1, "Required"),
  end_date: z.string().min(1, "Required"),
});
type AllocationValues = z.infer<typeof allocationSchema>;

function AllocationsTab({ canManage }: { canManage: boolean }) {
  const [dialogOpen, setDialogOpen] = useState(false);
  const queryClient = useQueryClient();
  const regionsQuery = useQuery({ queryKey: ["regions"], queryFn: () => api.get<Region[]>("/regions") });
  const districtsQuery = useQuery({ queryKey: ["districts"], queryFn: () => api.get<District[]>("/districts") });
  const activitiesQuery = useQuery({
    queryKey: ["fuel-activities"], queryFn: () => api.get<CensusActivity[]>("/fuel/activities"),
  });

  const allocationsQuery = useQuery({
    queryKey: ["fuel-allocations"], queryFn: () => api.get<FuelAllocation[]>("/fuel/allocations"),
  });

  const { register, handleSubmit, reset } = useForm<AllocationValues>({
    resolver: zodResolver(allocationSchema), defaultValues: { fuel_type: "DIESEL" },
  });

  const createMutation = useMutation({
    mutationFn: (values: AllocationValues) =>
      api.post("/fuel/allocations", {
        ...values,
        region_id: values.region_id || undefined,
        district_id: values.district_id || undefined,
        activity_id: values.activity_id || undefined,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["fuel-allocations"] });
      setDialogOpen(false);
      reset();
    },
  });

  return (
    <div className="space-y-4">
      {canManage && (
        <div className="flex justify-end">
          <Button onClick={() => setDialogOpen(true)}><Plus size={16} /> New allocation</Button>
        </div>
      )}
      {allocationsQuery.data && (
        <Table>
          <TableHead>
            <TableRow>
              <TableHeaderCell>Reference</TableHeaderCell>
              <TableHeaderCell>Region / District</TableHeaderCell>
              <TableHeaderCell>Activity</TableHeaderCell>
              <TableHeaderCell>Fuel</TableHeaderCell>
              <TableHeaderCell>Allocated</TableHeaderCell>
              <TableHeaderCell>Requested</TableHeaderCell>
              <TableHeaderCell>Remaining</TableHeaderCell>
              <TableHeaderCell>Status</TableHeaderCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {allocationsQuery.data.map((a) => (
              <TableRow key={a.id}>
                <TableCell className="font-medium text-slate-900">{a.allocation_reference}</TableCell>
                <TableCell>{[a.region?.name, a.district?.name].filter(Boolean).join(" / ") || "National"}</TableCell>
                <TableCell>{a.activity?.name ?? "-"}</TableCell>
                <TableCell>{a.fuel_type}</TableCell>
                <TableCell>{a.allocated_litres.toLocaleString()}L</TableCell>
                <TableCell>{a.litres_requested.toLocaleString()}L</TableCell>
                <TableCell className={a.litres_remaining < a.allocated_litres * 0.1 ? "font-medium text-red-600" : ""}>
                  {a.litres_remaining.toLocaleString()}L
                </TableCell>
                <TableCell><Badge variant={a.status === "ACTIVE" ? "success" : "neutral"}>{a.status}</Badge></TableCell>
              </TableRow>
            ))}
            {allocationsQuery.data.length === 0 && (
              <TableRow><TableCell colSpan={8} className="py-8 text-center text-slate-400">No fuel allocations yet.</TableCell></TableRow>
            )}
          </TableBody>
        </Table>
      )}
      <Dialog open={dialogOpen} onClose={() => setDialogOpen(false)} title="New fuel allocation" className="max-w-xl">
        <form onSubmit={handleSubmit((v) => createMutation.mutate(v))} className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-1.5">
              <Label htmlFor="allocated_litres">Allocated litres</Label>
              <Input id="allocated_litres" type="number" step="0.01" {...register("allocated_litres")} />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="fuel_type">Fuel type</Label>
              <Select id="fuel_type" {...register("fuel_type")}>
                <option value="DIESEL">Diesel</option>
                <option value="PETROL">Petrol</option>
              </Select>
            </div>
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="allocated_budget">Budget (optional)</Label>
            <Input id="allocated_budget" type="number" step="0.01" {...register("allocated_budget")} />
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-1.5"><Label htmlFor="start_date">Start date</Label><Input id="start_date" type="date" {...register("start_date")} /></div>
            <div className="space-y-1.5"><Label htmlFor="end_date">End date</Label><Input id="end_date" type="date" {...register("end_date")} /></div>
          </div>
          <div className="grid grid-cols-3 gap-4">
            <div className="space-y-1.5">
              <Label htmlFor="region_id">Region</Label>
              <Select id="region_id" {...register("region_id")}>
                <option value="">National</option>
                {regionsQuery.data?.map((r) => <option key={r.id} value={r.id}>{r.name}</option>)}
              </Select>
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="district_id">District</Label>
              <Select id="district_id" {...register("district_id")}>
                <option value="">Unspecified</option>
                {districtsQuery.data?.map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}
              </Select>
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="activity_id">Activity</Label>
              <Select id="activity_id" {...register("activity_id")}>
                <option value="">Unspecified</option>
                {activitiesQuery.data?.map((a) => <option key={a.id} value={a.id}>{a.name}</option>)}
              </Select>
            </div>
          </div>
          {createMutation.error instanceof ApiError && <p className="text-xs text-red-600">{createMutation.error.message}</p>}
          <Button type="submit" className="w-full" disabled={createMutation.isPending}>
            {createMutation.isPending ? "Saving..." : "Create allocation"}
          </Button>
        </form>
      </Dialog>
    </div>
  );
}

const voucherSchema = z.object({
  voucher_number: z.string().min(1, "Required"),
  value: z.coerce.number().optional(),
  litres: z.coerce.number().optional(),
  assigned_asset_description: z.string().optional(),
  date_issued: z.string().optional(),
  remarks: z.string().optional(),
});
type VoucherValues = z.infer<typeof voucherSchema>;

function VouchersTab({ canManage }: { canManage: boolean }) {
  const [dialogOpen, setDialogOpen] = useState(false);
  const queryClient = useQueryClient();

  const vouchersQuery = useQuery({ queryKey: ["fuel-vouchers"], queryFn: () => api.get<FuelVoucher[]>("/fuel/vouchers") });

  const { register, handleSubmit, reset } = useForm<VoucherValues>({ resolver: zodResolver(voucherSchema) });

  const createMutation = useMutation({
    mutationFn: (values: VoucherValues) => api.post("/fuel/vouchers", { ...values, date_issued: values.date_issued || undefined }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["fuel-vouchers"] });
      setDialogOpen(false);
      reset();
    },
  });

  const statusMutation = useMutation({
    mutationFn: ({ id, status }: { id: string; status: FuelVoucherStatus }) =>
      api.put(`/fuel/vouchers/${id}/status`, { status }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["fuel-vouchers"] }),
  });

  return (
    <div className="space-y-4">
      {canManage && (
        <div className="flex justify-end">
          <Button onClick={() => setDialogOpen(true)}><Plus size={16} /> New voucher</Button>
        </div>
      )}
      {vouchersQuery.data && (
        <Table>
          <TableHead>
            <TableRow>
              <TableHeaderCell>Voucher #</TableHeaderCell>
              <TableHeaderCell>Value</TableHeaderCell>
              <TableHeaderCell>Litres</TableHeaderCell>
              <TableHeaderCell>Assigned Asset</TableHeaderCell>
              <TableHeaderCell>Status</TableHeaderCell>
              {canManage && <TableHeaderCell></TableHeaderCell>}
            </TableRow>
          </TableHead>
          <TableBody>
            {vouchersQuery.data.map((v) => (
              <TableRow key={v.id}>
                <TableCell className="font-medium text-slate-900">{v.voucher_number}</TableCell>
                <TableCell>{v.value ?? "-"}</TableCell>
                <TableCell>{v.litres ?? "-"}</TableCell>
                <TableCell>{v.assigned_asset_description ?? "-"}</TableCell>
                <TableCell><Badge variant={VOUCHER_STATUS_BADGE_VARIANT[v.status]}>{VOUCHER_STATUS_LABEL[v.status]}</Badge></TableCell>
                {canManage && (
                  <TableCell>
                    <Select
                      value={v.status}
                      onChange={(e) => statusMutation.mutate({ id: v.id, status: e.target.value as FuelVoucherStatus })}
                      className="max-w-[140px]"
                    >
                      {(["AVAILABLE", "ISSUED", "REDEEMED", "CANCELLED", "LOST", "RECONCILED"] as const).map((s) => (
                        <option key={s} value={s}>{VOUCHER_STATUS_LABEL[s]}</option>
                      ))}
                    </Select>
                  </TableCell>
                )}
              </TableRow>
            ))}
            {vouchersQuery.data.length === 0 && (
              <TableRow><TableCell colSpan={canManage ? 6 : 5} className="py-8 text-center text-slate-400">No fuel vouchers yet.</TableCell></TableRow>
            )}
          </TableBody>
        </Table>
      )}
      <Dialog open={dialogOpen} onClose={() => setDialogOpen(false)} title="New fuel voucher">
        <form onSubmit={handleSubmit((v) => createMutation.mutate(v))} className="space-y-4">
          <div className="space-y-1.5">
            <Label htmlFor="voucher_number">Voucher number</Label>
            <Input id="voucher_number" {...register("voucher_number")} />
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-1.5"><Label htmlFor="value">Value</Label><Input id="value" type="number" step="0.01" {...register("value")} /></div>
            <div className="space-y-1.5"><Label htmlFor="litres">Litres</Label><Input id="litres" type="number" step="0.01" {...register("litres")} /></div>
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="assigned_asset_description">Assigned to (asset / person)</Label>
            <Input id="assigned_asset_description" placeholder="e.g. Vehicle SLG-1234" {...register("assigned_asset_description")} />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="date_issued">Date issued</Label>
            <Input id="date_issued" type="date" {...register("date_issued")} />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="remarks">Remarks</Label>
            <Input id="remarks" {...register("remarks")} />
          </div>
          {createMutation.error instanceof ApiError && <p className="text-xs text-red-600">{createMutation.error.message}</p>}
          <Button type="submit" className="w-full" disabled={createMutation.isPending}>
            {createMutation.isPending ? "Saving..." : "Save voucher"}
          </Button>
        </form>
      </Dialog>
    </div>
  );
}

const stockReceiptSchema = z.object({
  depot_location_id: z.string().min(1, "Choose a depot"),
  fuel_type: z.enum(["PETROL", "DIESEL"]),
  quantity: z.coerce.number().positive(),
  remarks: z.string().optional(),
});
type StockReceiptValues = z.infer<typeof stockReceiptSchema>;

const stockAdjustSchema = z.object({
  depot_location_id: z.string().min(1, "Choose a depot"),
  fuel_type: z.enum(["PETROL", "DIESEL"]),
  quantity_delta: z.coerce.number(),
  reason: z.string().min(1, "Required"),
});
type StockAdjustValues = z.infer<typeof stockAdjustSchema>;

function StockTab({ canManage }: { canManage: boolean }) {
  const [openDialog, setOpenDialog] = useState<"receipt" | "adjust" | null>(null);
  const queryClient = useQueryClient();
  const { options: warehouseOptions } = useWarehouseOptions();

  const stockQuery = useQuery({ queryKey: ["fuel-stock"], queryFn: () => api.get<FuelStockBalance[]>("/fuel/stock") });

  const receiptForm = useForm<StockReceiptValues>({ resolver: zodResolver(stockReceiptSchema), defaultValues: { fuel_type: "DIESEL" } });
  const adjustForm = useForm<StockAdjustValues>({ resolver: zodResolver(stockAdjustSchema), defaultValues: { fuel_type: "DIESEL" } });

  function invalidate() {
    queryClient.invalidateQueries({ queryKey: ["fuel-stock"] });
    setOpenDialog(null);
    receiptForm.reset();
    adjustForm.reset();
  }

  const receiptMutation = useMutation({
    mutationFn: (values: StockReceiptValues) => api.post("/fuel/stock/receipts", values),
    onSuccess: invalidate,
  });
  const adjustMutation = useMutation({
    mutationFn: (values: StockAdjustValues) => api.post("/fuel/stock/adjustments", values),
    onSuccess: invalidate,
  });

  return (
    <div className="space-y-4">
      {canManage && (
        <div className="flex justify-end gap-2">
          <Button variant="secondary" onClick={() => setOpenDialog("adjust")}>Adjust stock</Button>
          <Button onClick={() => setOpenDialog("receipt")}><Plus size={16} /> Receive stock</Button>
        </div>
      )}
      {stockQuery.data && (
        <Table>
          <TableHead>
            <TableRow>
              <TableHeaderCell>Depot</TableHeaderCell>
              <TableHeaderCell>Fuel Type</TableHeaderCell>
              <TableHeaderCell>Quantity on Hand</TableHeaderCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {stockQuery.data.map((s) => (
              <TableRow key={`${s.depot_location_id}-${s.fuel_type}`}>
                <TableCell className="font-medium text-slate-900">{s.depot_name}</TableCell>
                <TableCell>{s.fuel_type}</TableCell>
                <TableCell className={s.quantity_on_hand < 0 ? "font-medium text-red-600" : ""}>
                  {s.quantity_on_hand.toLocaleString()}L
                </TableCell>
              </TableRow>
            ))}
            {stockQuery.data.length === 0 && (
              <TableRow><TableCell colSpan={3} className="py-8 text-center text-slate-400">No fuel stock movements recorded yet.</TableCell></TableRow>
            )}
          </TableBody>
        </Table>
      )}

      <Dialog open={openDialog === "receipt"} onClose={() => setOpenDialog(null)} title="Receive fuel stock">
        <form onSubmit={receiptForm.handleSubmit((v) => receiptMutation.mutate(v))} className="space-y-4">
          <div className="space-y-1.5">
            <Label htmlFor="rs_depot">Depot</Label>
            <Select id="rs_depot" {...receiptForm.register("depot_location_id")}>
              <option value="">Select...</option>
              {warehouseOptions.map((w) => <option key={w.id} value={w.id}>{w.name}</option>)}
            </Select>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-1.5">
              <Label htmlFor="rs_fuel_type">Fuel type</Label>
              <Select id="rs_fuel_type" {...receiptForm.register("fuel_type")}>
                <option value="DIESEL">Diesel</option>
                <option value="PETROL">Petrol</option>
              </Select>
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="rs_quantity">Quantity (L)</Label>
              <Input id="rs_quantity" type="number" step="0.01" {...receiptForm.register("quantity")} />
            </div>
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="rs_remarks">Remarks</Label>
            <Input id="rs_remarks" {...receiptForm.register("remarks")} />
          </div>
          {receiptMutation.error instanceof ApiError && <p className="text-xs text-red-600">{receiptMutation.error.message}</p>}
          <Button type="submit" className="w-full" disabled={receiptMutation.isPending}>
            {receiptMutation.isPending ? "Recording..." : "Record receipt"}
          </Button>
        </form>
      </Dialog>

      <Dialog open={openDialog === "adjust"} onClose={() => setOpenDialog(null)} title="Adjust fuel stock">
        <form onSubmit={adjustForm.handleSubmit((v) => adjustMutation.mutate(v))} className="space-y-4">
          <div className="space-y-1.5">
            <Label htmlFor="adj_depot">Depot</Label>
            <Select id="adj_depot" {...adjustForm.register("depot_location_id")}>
              <option value="">Select...</option>
              {warehouseOptions.map((w) => <option key={w.id} value={w.id}>{w.name}</option>)}
            </Select>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-1.5">
              <Label htmlFor="adj_fuel_type">Fuel type</Label>
              <Select id="adj_fuel_type" {...adjustForm.register("fuel_type")}>
                <option value="DIESEL">Diesel</option>
                <option value="PETROL">Petrol</option>
              </Select>
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="adj_quantity_delta">Signed correction (e.g. -5 or 10)</Label>
              <Input id="adj_quantity_delta" type="number" step="0.01" {...adjustForm.register("quantity_delta")} />
            </div>
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="adj_reason">Reason</Label>
            <Input id="adj_reason" {...adjustForm.register("reason")} />
          </div>
          {adjustMutation.error instanceof ApiError && <p className="text-xs text-red-600">{adjustMutation.error.message}</p>}
          <Button type="submit" className="w-full" disabled={adjustMutation.isPending}>
            {adjustMutation.isPending ? "Saving..." : "Post adjustment"}
          </Button>
        </form>
      </Dialog>
    </div>
  );
}
