import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, Plus, Radio, Wrench } from "lucide-react";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { Link } from "react-router-dom";
import { z } from "zod";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
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
import { ApiError, api } from "@/lib/api";
import { cn } from "@/lib/utils";
import { useAuthStore } from "@/store/authStore";
import type {
  District,
  FieldTeam,
  HardToReachArea,
  LocationRecord,
  Page,
  Region,
  StarlinkDashboardSummary,
  StarlinkFault,
  StarlinkKit,
} from "@/types";

const TABS = ["dashboard", "inventory", "field-teams", "hard-to-reach", "faults"] as const;
type Tab = (typeof TABS)[number];

const TAB_LABELS: Record<Tab, string> = {
  dashboard: "Dashboard",
  inventory: "Starlink Inventory",
  "field-teams": "Field Teams",
  "hard-to-reach": "Hard-to-Reach Areas",
  faults: "Maintenance & Faults",
};

const OPERATIONAL_STATUS_VARIANT: Record<string, "success" | "warning" | "destructive" | "neutral" | "default"> = {
  NOT_DEPLOYED: "neutral",
  INSTALLED_OPERATIONAL: "success",
  INSTALLED_OFFLINE: "destructive",
  FIELD_OPERATIONAL: "success",
  FIELD_OFFLINE: "destructive",
  UNDER_MAINTENANCE: "warning",
  RETIRED: "neutral",
};

const SUBSCRIPTION_STATUS_VARIANT: Record<string, "success" | "warning" | "destructive" | "neutral"> = {
  ACTIVE: "success",
  PENDING_ACTIVATION: "neutral",
  EXPIRING_SOON: "warning",
  PAYMENT_DUE: "warning",
  PAYMENT_OVERDUE: "destructive",
  SUSPENDED: "destructive",
  EXPIRED: "destructive",
  CANCELLED: "neutral",
};

export function StarlinkPage() {
  const [tab, setTab] = useState<Tab>("dashboard");
  const hasPermission = useAuthStore((s) => s.hasPermission);

  return (
    <div className="space-y-6">
      <div>
        <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
          ICT &amp; Connectivity Assets
        </p>
        <h1 className="text-2xl font-semibold text-slate-900">Starlink Management</h1>
        <p className="text-sm text-slate-500">
          Fixed and roaming Starlink kits — inventory, installation, subscriptions, field team
          deployment and connectivity monitoring.
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
      {tab === "inventory" && <InventoryTab canManage={hasPermission("starlink.manage")} />}
      {tab === "field-teams" && <FieldTeamsTab canManage={hasPermission("starlink.manage")} />}
      {tab === "hard-to-reach" && <HardToReachTab canManage={hasPermission("starlink.manage")} />}
      {tab === "faults" && <FaultsTab canManage={hasPermission("starlink.maintenance")} />}
    </div>
  );
}

function Kpi({ label, value, tone }: { label: string; value: number; tone?: "warn" | "danger" | "good" }) {
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
    queryKey: ["starlink-dashboard"],
    queryFn: () => api.get<StarlinkDashboardSummary>("/starlink/dashboard"),
  });

  if (q.isLoading) {
    return (
      <div className="flex items-center gap-2 text-sm text-slate-500">
        <Spinner /> Loading Starlink dashboard...
      </div>
    );
  }
  const d = q.data;
  if (!d) return null;

  return (
    <div className="space-y-6">
      {d.hard_to_reach_gap > 0 && (
        <div className="flex items-start gap-3 rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">
          <AlertTriangle size={18} className="mt-0.5 flex-none" />
          <div>
            <strong>{d.hard_to_reach_gap}</strong> Starlink-required area
            {d.hard_to_reach_gap === 1 ? " has" : "s have"} no field team currently assigned a Starlink
            kit. See Hard-to-Reach Areas.
          </div>
        </div>
      )}

      <div>
        <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">Inventory</p>
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          <Kpi label="Total kits" value={d.total_kits} />
          <Kpi label="Fixed" value={d.fixed_kits} />
          <Kpi label="Roaming" value={d.roaming_kits} />
          <Kpi label="Available" value={d.available_kits} tone="good" />
          <Kpi label="Deployed" value={d.deployed_kits} />
          <Kpi label="Under maintenance" value={d.under_maintenance_kits} tone="warn" />
          <Kpi label="Damaged / lost" value={d.damaged_or_lost_kits} tone="danger" />
        </div>
      </div>

      <div>
        <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">Installation</p>
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          <Kpi label="Installed" value={d.installed} />
          <Kpi label="Awaiting installation" value={d.awaiting_installation} tone="warn" />
          <Kpi label="Installed & operational" value={d.installed_and_operational} tone="good" />
          <Kpi label="Installed but offline" value={d.installed_but_offline} tone="danger" />
        </div>
      </div>

      <div>
        <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">Subscription</p>
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          <Kpi label="Active" value={d.subscriptions_active} tone="good" />
          <Kpi label="Expiring in 30 days" value={d.subscriptions_expiring_30d} tone="warn" />
          <Kpi label="Expiring in 14 days" value={d.subscriptions_expiring_14d} tone="warn" />
          <Kpi label="Expiring in 7 days" value={d.subscriptions_expiring_7d} tone="danger" />
          <Kpi label="Expired" value={d.subscriptions_expired} tone="danger" />
          <Kpi label="Payments overdue" value={d.payments_overdue} tone="danger" />
        </div>
      </div>

      <div>
        <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">Field operations</p>
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          <Kpi label="Roaming kits with teams" value={d.roaming_assigned_to_teams} />
          <Kpi label="Teams in hard-to-reach areas" value={d.teams_in_hard_to_reach_areas} />
          <Kpi label="...with connectivity" value={d.hard_to_reach_with_connectivity} tone="good" />
          <Kpi label="...without connectivity" value={d.hard_to_reach_without_connectivity} tone="danger" />
          <Kpi label="Overdue for return" value={d.kits_overdue_for_return} tone="warn" />
        </div>
      </div>

      <div>
        <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">Connectivity</p>
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          <Kpi label="Online" value={d.online_kits} tone="good" />
          <Kpi label="Offline" value={d.offline_kits} tone="danger" />
          <Kpi label="Support requested" value={d.support_requested} tone="warn" />
        </div>
      </div>
    </div>
  );
}

const kitSchema = z.object({
  kit_type: z.enum(["FIXED", "ROAMING"]),
  serial_number: z.string().optional(),
  terminal_id: z.string().optional(),
  router_serial_number: z.string().optional(),
  supplier_or_donor: z.string().optional(),
  purchase_order_ref: z.string().optional(),
  date_acquired: z.string().optional(),
  unit_cost: z.string().optional(),
  currency: z.string().optional(),
  warranty_start: z.string().optional(),
  warranty_end: z.string().optional(),
  current_location_id: z.string().optional(),
  condition: z.string().default("NEW"),
  remarks: z.string().optional(),
});
type KitValues = z.infer<typeof kitSchema>;

function InventoryTab({ canManage }: { canManage: boolean }) {
  const [dialogOpen, setDialogOpen] = useState(false);
  const [kitTypeFilter, setKitTypeFilter] = useState("");
  const queryClient = useQueryClient();

  const kitsQuery = useQuery({
    queryKey: ["starlink-kits", kitTypeFilter],
    queryFn: () =>
      api.get<Page<StarlinkKit>>("/starlink", { kit_type: kitTypeFilter || undefined, page_size: 50 }),
  });
  const locationsQuery = useQuery({
    queryKey: ["locations-for-select"],
    queryFn: () => api.get<Page<LocationRecord>>("/locations", { page_size: 100 }),
  });
  const locationsById = new Map((locationsQuery.data?.items ?? []).map((l) => [l.id, l]));

  const {
    register,
    handleSubmit,
    reset,
  } = useForm<KitValues>({ resolver: zodResolver(kitSchema), defaultValues: { kit_type: "FIXED", condition: "NEW" } });

  const createKit = useMutation({
    mutationFn: (values: KitValues) =>
      api.post("/starlink", {
        ...values,
        unit_cost: values.unit_cost ? Number(values.unit_cost) : undefined,
        current_location_id: values.current_location_id || undefined,
        date_acquired: values.date_acquired || undefined,
        warranty_start: values.warranty_start || undefined,
        warranty_end: values.warranty_end || undefined,
        components: [],
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["starlink-kits"] });
      queryClient.invalidateQueries({ queryKey: ["starlink-dashboard"] });
      setDialogOpen(false);
      reset();
    },
  });

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <Select value={kitTypeFilter} onChange={(e) => setKitTypeFilter(e.target.value)} className="max-w-xs">
          <option value="">All kit types</option>
          <option value="FIXED">Fixed</option>
          <option value="ROAMING">Roaming</option>
        </Select>
        {canManage && (
          <Button onClick={() => setDialogOpen(true)}>
            <Plus size={16} /> Register Starlink kit
          </Button>
        )}
      </div>

      {kitsQuery.isLoading && (
        <div className="flex items-center gap-2 text-sm text-slate-500">
          <Spinner /> Loading kits...
        </div>
      )}

      {kitsQuery.data && (
        <Table>
          <TableHead>
            <TableRow>
              <TableHeaderCell>Asset Tag</TableHeaderCell>
              <TableHeaderCell>Type</TableHeaderCell>
              <TableHeaderCell>Location</TableHeaderCell>
              <TableHeaderCell>Operational Status</TableHeaderCell>
              <TableHeaderCell>Subscription</TableHeaderCell>
              <TableHeaderCell>Connectivity</TableHeaderCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {kitsQuery.data.items.map((kit) => (
              <TableRow key={kit.id}>
                <TableCell className="font-medium text-brand-700">
                  <Link to={`/starlink/${kit.id}`} className="hover:underline">
                    {kit.asset.asset_tag}
                  </Link>
                </TableCell>
                <TableCell>
                  <Badge variant={kit.kit_type === "FIXED" ? "default" : "neutral"}>
                    {kit.kit_type === "FIXED" ? "Fixed" : "Roaming"}
                  </Badge>
                </TableCell>
                <TableCell>{kit.asset.current_location_id ? locationsById.get(kit.asset.current_location_id)?.name ?? "-" : "-"}</TableCell>
                <TableCell>
                  <Badge variant={OPERATIONAL_STATUS_VARIANT[kit.operational_status] ?? "neutral"}>
                    {kit.operational_status.replaceAll("_", " ")}
                  </Badge>
                </TableCell>
                <TableCell>
                  <Badge variant={SUBSCRIPTION_STATUS_VARIANT[kit.subscription_status] ?? "neutral"}>
                    {kit.subscription_status.replaceAll("_", " ")}
                  </Badge>
                </TableCell>
                <TableCell>{kit.last_connectivity_quality ?? "-"}</TableCell>
              </TableRow>
            ))}
            {kitsQuery.data.items.length === 0 && (
              <TableRow>
                <TableCell colSpan={6} className="py-8 text-center text-slate-400">
                  No Starlink kits registered yet.
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      )}

      <Dialog open={dialogOpen} onClose={() => setDialogOpen(false)} title="Register Starlink kit" className="max-w-xl">
        <form onSubmit={handleSubmit((v) => createKit.mutate(v))} className="max-h-[70vh] space-y-4 overflow-y-auto pr-1">
          <div className="space-y-1.5">
            <Label htmlFor="kit_type">Fixed or Roaming</Label>
            <Select id="kit_type" {...register("kit_type")}>
              <option value="FIXED">Fixed</option>
              <option value="ROAMING">Roaming</option>
            </Select>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-1.5">
              <Label htmlFor="serial_number">Serial number</Label>
              <Input id="serial_number" {...register("serial_number")} />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="terminal_id">Terminal ID</Label>
              <Input id="terminal_id" {...register("terminal_id")} />
            </div>
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="router_serial_number">Router serial number</Label>
            <Input id="router_serial_number" {...register("router_serial_number")} />
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-1.5">
              <Label htmlFor="supplier_or_donor">Supplier / donor</Label>
              <Input id="supplier_or_donor" {...register("supplier_or_donor")} />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="purchase_order_ref">Purchase order #</Label>
              <Input id="purchase_order_ref" {...register("purchase_order_ref")} />
            </div>
          </div>
          <div className="grid grid-cols-3 gap-4">
            <div className="space-y-1.5">
              <Label htmlFor="date_acquired">Date acquired</Label>
              <Input id="date_acquired" type="date" {...register("date_acquired")} />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="unit_cost">Purchase cost</Label>
              <Input id="unit_cost" type="number" step="0.01" {...register("unit_cost")} />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="currency">Currency</Label>
              <Input id="currency" placeholder="USD" {...register("currency")} />
            </div>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-1.5">
              <Label htmlFor="warranty_start">Warranty start</Label>
              <Input id="warranty_start" type="date" {...register("warranty_start")} />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="warranty_end">Warranty end</Label>
              <Input id="warranty_end" type="date" {...register("warranty_end")} />
            </div>
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="current_location_id">Current location</Label>
            <Select id="current_location_id" {...register("current_location_id")}>
              <option value="">Unassigned</option>
              {locationsQuery.data?.items.map((loc) => (
                <option key={loc.id} value={loc.id}>
                  {loc.name}
                </option>
              ))}
            </Select>
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="remarks">Remarks</Label>
            <Input id="remarks" {...register("remarks")} />
          </div>
          {createKit.error instanceof ApiError && (
            <p className="text-xs text-red-600">{createKit.error.message}</p>
          )}
          <Button type="submit" className="w-full" disabled={createKit.isPending}>
            {createKit.isPending ? "Registering..." : "Register kit"}
          </Button>
        </form>
      </Dialog>
    </div>
  );
}

const fieldTeamSchema = z.object({
  name: z.string().min(1, "Required"),
  team_type: z.string().optional(),
  team_leader_name: z.string().optional(),
  team_leader_phone: z.string().optional(),
  region_id: z.string().optional(),
  district_id: z.string().optional(),
});
type FieldTeamValues = z.infer<typeof fieldTeamSchema>;

function FieldTeamsTab({ canManage }: { canManage: boolean }) {
  const [dialogOpen, setDialogOpen] = useState(false);
  const queryClient = useQueryClient();

  const teamsQuery = useQuery({ queryKey: ["field-teams"], queryFn: () => api.get<FieldTeam[]>("/starlink/field-teams") });
  const regionsQuery = useQuery({ queryKey: ["regions"], queryFn: () => api.get<Region[]>("/regions") });
  const districtsQuery = useQuery({ queryKey: ["districts"], queryFn: () => api.get<District[]>("/districts") });
  const regionsById = new Map((regionsQuery.data ?? []).map((r) => [r.id, r]));
  const districtsById = new Map((districtsQuery.data ?? []).map((d) => [d.id, d]));

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<FieldTeamValues>({ resolver: zodResolver(fieldTeamSchema) });

  const createTeam = useMutation({
    mutationFn: (values: FieldTeamValues) =>
      api.post("/starlink/field-teams", {
        ...values,
        region_id: values.region_id || undefined,
        district_id: values.district_id || undefined,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["field-teams"] });
      setDialogOpen(false);
      reset();
    },
  });

  return (
    <div className="space-y-4">
      {canManage && (
        <div className="flex justify-end">
          <Button onClick={() => setDialogOpen(true)}>
            <Plus size={16} /> New field team
          </Button>
        </div>
      )}

      {teamsQuery.data && (
        <Table>
          <TableHead>
            <TableRow>
              <TableHeaderCell>Team</TableHeaderCell>
              <TableHeaderCell>Type</TableHeaderCell>
              <TableHeaderCell>Leader</TableHeaderCell>
              <TableHeaderCell>Region / District</TableHeaderCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {teamsQuery.data.map((team) => (
              <TableRow key={team.id}>
                <TableCell className="font-medium text-slate-900">
                  {team.team_code} — {team.name}
                </TableCell>
                <TableCell>{team.team_type ?? "-"}</TableCell>
                <TableCell>
                  {team.team_leader_name ?? "-"}
                  {team.team_leader_phone ? ` (${team.team_leader_phone})` : ""}
                </TableCell>
                <TableCell>
                  {team.region_id ? regionsById.get(team.region_id)?.name ?? "-" : "-"}
                  {team.district_id ? ` / ${districtsById.get(team.district_id)?.name ?? "-"}` : ""}
                </TableCell>
              </TableRow>
            ))}
            {teamsQuery.data.length === 0 && (
              <TableRow>
                <TableCell colSpan={4} className="py-8 text-center text-slate-400">
                  No field teams yet.
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      )}

      <Dialog open={dialogOpen} onClose={() => setDialogOpen(false)} title="New field team">
        <form onSubmit={handleSubmit((v) => createTeam.mutate(v))} className="space-y-4">
          <div className="space-y-1.5">
            <Label htmlFor="ft_name">Team name</Label>
            <Input id="ft_name" {...register("name")} />
            {errors.name && <p className="text-xs text-red-600">{errors.name.message}</p>}
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="ft_type">Team type</Label>
            <Input id="ft_type" placeholder="e.g. Data Quality Monitoring" {...register("team_type")} />
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-1.5">
              <Label htmlFor="ft_leader">Team leader</Label>
              <Input id="ft_leader" {...register("team_leader_name")} />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="ft_phone">Leader phone</Label>
              <Input id="ft_phone" {...register("team_leader_phone")} />
            </div>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-1.5">
              <Label htmlFor="ft_region">Region</Label>
              <Select id="ft_region" {...register("region_id")}>
                <option value="">Unspecified</option>
                {regionsQuery.data?.map((r) => (
                  <option key={r.id} value={r.id}>{r.name}</option>
                ))}
              </Select>
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="ft_district">District</Label>
              <Select id="ft_district" {...register("district_id")}>
                <option value="">Unspecified</option>
                {districtsQuery.data?.map((d) => (
                  <option key={d.id} value={d.id}>{d.name}</option>
                ))}
              </Select>
            </div>
          </div>
          {createTeam.error instanceof ApiError && <p className="text-xs text-red-600">{createTeam.error.message}</p>}
          <Button type="submit" className="w-full" disabled={createTeam.isPending}>
            {createTeam.isPending ? "Saving..." : "Save field team"}
          </Button>
        </form>
      </Dialog>
    </div>
  );
}

const areaSchema = z.object({
  name: z.string().min(1, "Required"),
  district_id: z.string().min(1, "Required"),
  chiefdom: z.string().optional(),
  classification: z.string().default("HARD_TO_REACH"),
  starlink_required: z.boolean().default(false),
  notes: z.string().optional(),
});
type AreaValues = z.infer<typeof areaSchema>;

const CLASSIFICATIONS = [
  "GOOD_COVERAGE", "MODERATE_COVERAGE", "WEAK_COVERAGE", "INTERMITTENT_COVERAGE",
  "NO_COVERAGE", "HARD_TO_REACH", "STARLINK_RECOMMENDED", "STARLINK_REQUIRED",
];

function HardToReachTab({ canManage }: { canManage: boolean }) {
  const [dialogOpen, setDialogOpen] = useState(false);
  const queryClient = useQueryClient();

  const areasQuery = useQuery({ queryKey: ["hard-to-reach-areas"], queryFn: () => api.get<HardToReachArea[]>("/starlink/hard-to-reach-areas") });
  const districtsQuery = useQuery({ queryKey: ["districts"], queryFn: () => api.get<District[]>("/districts") });
  const districtsById = new Map((districtsQuery.data ?? []).map((d) => [d.id, d]));

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<AreaValues>({ resolver: zodResolver(areaSchema), defaultValues: { classification: "HARD_TO_REACH", starlink_required: false } });

  const createArea = useMutation({
    mutationFn: (values: AreaValues) => api.post("/starlink/hard-to-reach-areas", values),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["hard-to-reach-areas"] });
      setDialogOpen(false);
      reset();
    },
  });

  return (
    <div className="space-y-4">
      {canManage && (
        <div className="flex justify-end">
          <Button onClick={() => setDialogOpen(true)}>
            <Plus size={16} /> New area
          </Button>
        </div>
      )}

      {areasQuery.data && (
        <Table>
          <TableHead>
            <TableRow>
              <TableHeaderCell>Area</TableHeaderCell>
              <TableHeaderCell>District</TableHeaderCell>
              <TableHeaderCell>Classification</TableHeaderCell>
              <TableHeaderCell>Starlink Required</TableHeaderCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {areasQuery.data.map((area) => (
              <TableRow key={area.id}>
                <TableCell className="font-medium text-slate-900">{area.name}</TableCell>
                <TableCell>{districtsById.get(area.district_id)?.name ?? "-"}</TableCell>
                <TableCell>{area.classification.replaceAll("_", " ")}</TableCell>
                <TableCell>
                  {area.starlink_required ? <Badge variant="destructive">Required</Badge> : <Badge variant="neutral">No</Badge>}
                </TableCell>
              </TableRow>
            ))}
            {areasQuery.data.length === 0 && (
              <TableRow>
                <TableCell colSpan={4} className="py-8 text-center text-slate-400">
                  No hard-to-reach areas classified yet.
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      )}

      <Dialog open={dialogOpen} onClose={() => setDialogOpen(false)} title="New hard-to-reach area">
        <form onSubmit={handleSubmit((v) => createArea.mutate(v))} className="space-y-4">
          <div className="space-y-1.5">
            <Label htmlFor="area_name">Area name</Label>
            <Input id="area_name" {...register("name")} />
            {errors.name && <p className="text-xs text-red-600">{errors.name.message}</p>}
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="area_district">District</Label>
            <Select id="area_district" {...register("district_id")}>
              <option value="">Select...</option>
              {districtsQuery.data?.map((d) => (
                <option key={d.id} value={d.id}>{d.name}</option>
              ))}
            </Select>
            {errors.district_id && <p className="text-xs text-red-600">{errors.district_id.message}</p>}
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="area_chiefdom">Chiefdom (optional)</Label>
            <Input id="area_chiefdom" {...register("chiefdom")} />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="area_classification">Classification</Label>
            <Select id="area_classification" {...register("classification")}>
              {CLASSIFICATIONS.map((c) => (
                <option key={c} value={c}>{c.replaceAll("_", " ")}</option>
              ))}
            </Select>
          </div>
          <label className="flex items-center gap-2 text-sm text-slate-700">
            <Checkbox {...register("starlink_required")} />
            Starlink required — flag if no kit is assigned to a team here
          </label>
          {createArea.error instanceof ApiError && <p className="text-xs text-red-600">{createArea.error.message}</p>}
          <Button type="submit" className="w-full" disabled={createArea.isPending}>
            {createArea.isPending ? "Saving..." : "Save area"}
          </Button>
        </form>
      </Dialog>
    </div>
  );
}

const FAULT_STATUS_VARIANT: Record<string, "success" | "warning" | "destructive" | "neutral"> = {
  REPORTED: "warning",
  ASSIGNED: "warning",
  UNDER_DIAGNOSIS: "warning",
  UNDER_REPAIR: "warning",
  AWAITING_PARTS: "warning",
  RESOLVED: "success",
  CLOSED: "neutral",
  BEYOND_REPAIR: "destructive",
};

function FaultsTab({ canManage }: { canManage: boolean }) {
  const [statusFilter, setStatusFilter] = useState("");
  const faultsQuery = useQuery({
    queryKey: ["starlink-faults", statusFilter],
    queryFn: () => api.get<StarlinkFault[]>("/starlink/faults", { status_filter: statusFilter || undefined }),
  });

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <Select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)} className="max-w-xs">
          <option value="">All statuses</option>
          {Object.keys(FAULT_STATUS_VARIANT).map((s) => (
            <option key={s} value={s}>{s.replaceAll("_", " ")}</option>
          ))}
        </Select>
        <p className="text-xs text-slate-400">
          Fault tickets are opened from a kit's profile page — go to a Starlink kit's detail view to report one.
        </p>
      </div>

      {faultsQuery.data && (
        <Table>
          <TableHead>
            <TableRow>
              <TableHeaderCell>Ticket</TableHeaderCell>
              <TableHeaderCell>Kit</TableHeaderCell>
              <TableHeaderCell>Reported</TableHeaderCell>
              <TableHeaderCell>Priority</TableHeaderCell>
              <TableHeaderCell>Status</TableHeaderCell>
              <TableHeaderCell></TableHeaderCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {faultsQuery.data.map((fault) => (
              <TableRow key={fault.id}>
                <TableCell className="font-medium text-slate-900">{fault.ticket_number}</TableCell>
                <TableCell>
                  <Link to={`/starlink/${fault.kit_id}`} className="text-brand-700 hover:underline">
                    <Radio size={14} className="mr-1 inline" />
                    View kit
                  </Link>
                </TableCell>
                <TableCell>{fault.date_reported}</TableCell>
                <TableCell>{fault.priority}</TableCell>
                <TableCell>
                  <Badge variant={FAULT_STATUS_VARIANT[fault.status] ?? "neutral"}>{fault.status.replaceAll("_", " ")}</Badge>
                </TableCell>
                <TableCell>
                  {canManage && fault.status !== "RESOLVED" && fault.status !== "CLOSED" && (
                    <ResolveFaultButton fault={fault} />
                  )}
                </TableCell>
              </TableRow>
            ))}
            {faultsQuery.data.length === 0 && (
              <TableRow>
                <TableCell colSpan={6} className="py-8 text-center text-slate-400">
                  <Wrench size={16} className="mx-auto mb-2 text-slate-300" />
                  No fault tickets.
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      )}
    </div>
  );
}

function ResolveFaultButton({ fault }: { fault: StarlinkFault }) {
  const queryClient = useQueryClient();
  const resolve = useMutation({
    mutationFn: () => api.put(`/starlink/faults/${fault.id}`, { status: "RESOLVED" }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["starlink-faults"] });
      queryClient.invalidateQueries({ queryKey: ["starlink-dashboard"] });
    },
  });
  return (
    <Button variant="secondary" onClick={() => resolve.mutate()} disabled={resolve.isPending}>
      {resolve.isPending ? "Saving..." : "Mark resolved"}
    </Button>
  );
}
