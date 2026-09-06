import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type ReactNode } from "react";
import { useForm } from "react-hook-form";
import { Link, useParams } from "react-router-dom";
import { z } from "zod";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Dialog } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { Spinner } from "@/components/ui/spinner";
import { useWarehouseOptions } from "@/hooks/useWarehouseOptions";
import { ApiError, api } from "@/lib/api";
import type {
  District,
  FieldTeam,
  HardToReachArea,
  Region,
  StarlinkCheckin,
  StarlinkFault,
  StarlinkInstallation,
  StarlinkKit,
  StarlinkMovement,
  StarlinkSubscription,
  StarlinkTeamAssignment,
} from "@/types";

function Section({ title, action, children }: { title: string; action?: ReactNode; children: ReactNode }) {
  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between space-y-0">
        <CardTitle>{title}</CardTitle>
        {action}
      </CardHeader>
      <CardContent>{children}</CardContent>
    </Card>
  );
}

function DetailRow({ label, value }: { label: string; value: string | number | null | undefined }) {
  if (value === null || value === undefined || value === "") return null;
  return (
    <div className="flex justify-between border-b border-slate-100 py-1.5 text-sm last:border-0">
      <span className="text-slate-500">{label}</span>
      <span className="font-medium text-slate-900">{value}</span>
    </div>
  );
}

export function StarlinkKitDetailPage() {
  const { kitId } = useParams<{ kitId: string }>();
  const [showInstall, setShowInstall] = useState(false);
  const [showSubscription, setShowSubscription] = useState(false);
  const [showAssign, setShowAssign] = useState(false);
  const [showReturn, setShowReturn] = useState<StarlinkTeamAssignment | null>(null);
  const [showMovement, setShowMovement] = useState(false);
  const [showFault, setShowFault] = useState(false);
  const [showCheckin, setShowCheckin] = useState(false);
  const queryClient = useQueryClient();

  const kitQuery = useQuery({ queryKey: ["starlink-kit", kitId], queryFn: () => api.get<StarlinkKit>(`/starlink/${kitId}`) });
  const installationsQuery = useQuery({
    queryKey: ["starlink-installations", kitId],
    queryFn: () => api.get<StarlinkInstallation[]>(`/starlink/${kitId}/installations`),
  });
  const subscriptionsQuery = useQuery({
    queryKey: ["starlink-subscriptions", kitId],
    queryFn: () => api.get<StarlinkSubscription[]>(`/starlink/${kitId}/subscriptions`),
  });
  const assignmentsQuery = useQuery({
    queryKey: ["starlink-assignments", kitId],
    queryFn: () => api.get<StarlinkTeamAssignment[]>(`/starlink/${kitId}/assignments`),
  });
  const movementsQuery = useQuery({
    queryKey: ["starlink-movements", kitId],
    queryFn: () => api.get<StarlinkMovement[]>(`/starlink/${kitId}/movements`),
  });
  const checkinsQuery = useQuery({
    queryKey: ["starlink-checkins", kitId],
    queryFn: () => api.get<StarlinkCheckin[]>(`/starlink/${kitId}/checkins`),
  });
  const fieldTeamsQuery = useQuery({ queryKey: ["field-teams"], queryFn: () => api.get<FieldTeam[]>("/starlink/field-teams") });
  const fieldTeamsById = new Map((fieldTeamsQuery.data ?? []).map((t) => [t.id, t]));

  function invalidateAll() {
    queryClient.invalidateQueries({ queryKey: ["starlink-kit", kitId] });
    queryClient.invalidateQueries({ queryKey: ["starlink-installations", kitId] });
    queryClient.invalidateQueries({ queryKey: ["starlink-subscriptions", kitId] });
    queryClient.invalidateQueries({ queryKey: ["starlink-assignments", kitId] });
    queryClient.invalidateQueries({ queryKey: ["starlink-movements", kitId] });
    queryClient.invalidateQueries({ queryKey: ["starlink-checkins", kitId] });
    queryClient.invalidateQueries({ queryKey: ["starlink-kits"] });
    queryClient.invalidateQueries({ queryKey: ["starlink-dashboard"] });
    queryClient.invalidateQueries({ queryKey: ["starlink-faults"] });
  }

  if (kitQuery.isLoading || !kitQuery.data) {
    return (
      <div className="flex items-center gap-2 text-sm text-slate-500">
        <Spinner /> Loading Starlink kit...
      </div>
    );
  }
  const kit = kitQuery.data;
  const currentSubscription = subscriptionsQuery.data?.find((s) => s.is_current);
  const activeAssignment = assignmentsQuery.data?.find((a) => a.status === "ACTIVE");

  return (
    <div className="space-y-6">
      <div>
        <Link to="/starlink" className="text-xs text-brand-700 hover:underline">
          &larr; Back to Starlink Management
        </Link>
        <div className="mt-1 flex flex-wrap items-center gap-3">
          <h1 className="text-2xl font-semibold text-slate-900">{kit.asset.asset_tag}</h1>
          <Badge variant={kit.kit_type === "FIXED" ? "default" : "neutral"}>{kit.kit_type === "FIXED" ? "Fixed" : "Roaming"}</Badge>
          <Badge variant="success">{kit.operational_status.replaceAll("_", " ")}</Badge>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Section title="Asset Summary">
          <DetailRow label="Asset tag" value={kit.asset.asset_tag} />
          <DetailRow label="Serial number" value={kit.asset.serial_number} />
          <DetailRow label="Terminal ID" value={kit.terminal_id} />
          <DetailRow label="Router serial number" value={kit.router_serial_number} />
          <DetailRow label="Status" value={kit.asset.status} />
          <DetailRow label="Condition" value={kit.asset.condition} />
          <DetailRow label="Purchase cost" value={kit.asset.unit_cost ? `${kit.asset.currency ?? ""} ${kit.asset.unit_cost}` : null} />
          <DetailRow label="Warranty" value={kit.asset.warranty_start && kit.asset.warranty_end ? `${kit.asset.warranty_start} — ${kit.asset.warranty_end}` : null} />
        </Section>

        <Section title="Current Deployment">
          <DetailRow label="Installation status" value={kit.installation_status.replaceAll("_", " ")} />
          <DetailRow label="Subscription status" value={kit.subscription_status.replaceAll("_", " ")} />
          <DetailRow label="Current field team" value={activeAssignment ? fieldTeamsById.get(activeAssignment.field_team_id)?.name : null} />
          <DetailRow label="Last connectivity" value={kit.last_connectivity_quality} />
          <DetailRow label="Last check-in" value={kit.last_checkin_at ? new Date(kit.last_checkin_at).toLocaleString() : null} />
          {kit.components.length > 0 && (
            <div className="mt-2">
              <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-slate-500">Components</p>
              <div className="flex flex-wrap gap-1">
                {kit.components.map((c) => (
                  <Badge key={c.id} variant="neutral">{c.component_name} ({c.quantity})</Badge>
                ))}
              </div>
            </div>
          )}
        </Section>
      </div>

      <Section title="Installation History" action={<Button onClick={() => setShowInstall(true)}>Record installation</Button>}>
        {(installationsQuery.data ?? []).map((i) => (
          <DetailRow
            key={i.id}
            label={`${i.installation_date} — ${i.installation_type}`}
            value={`${i.connectivity_tested ? "Tested" : "Not tested"}${i.download_speed_mbps ? `, ${i.download_speed_mbps} Mbps down` : ""}`}
          />
        ))}
        {(installationsQuery.data ?? []).length === 0 && <p className="text-sm text-slate-400">Not installed yet.</p>}
      </Section>

      <Section
        title="Subscription"
        action={<Button onClick={() => setShowSubscription(true)}>New subscription term</Button>}
      >
        {currentSubscription ? (
          <>
            <DetailRow label="Plan" value={currentSubscription.plan_name} />
            <DetailRow label="Status" value={currentSubscription.status.replaceAll("_", " ")} />
            <DetailRow label="Monthly cost" value={currentSubscription.monthly_cost ? `${currentSubscription.currency ?? ""} ${currentSubscription.monthly_cost}` : null} />
            <DetailRow label="Next payment" value={currentSubscription.next_payment_date} />
            <DetailRow label="Expiry date" value={currentSubscription.expiry_date} />
            {currentSubscription.status !== "CANCELLED" && (
              <RecordPaymentButton subscriptionId={currentSubscription.id} onDone={invalidateAll} />
            )}
          </>
        ) : (
          <p className="text-sm text-slate-400">No subscription on record.</p>
        )}
      </Section>

      <Section
        title="Field Team Assignment"
        action={
          kit.kit_type === "ROAMING" &&
          (activeAssignment ? (
            <Button variant="secondary" onClick={() => setShowReturn(activeAssignment)}>
              Return from field
            </Button>
          ) : (
            <Button onClick={() => setShowAssign(true)}>Assign to field team</Button>
          ))
        }
      >
        {(assignmentsQuery.data ?? []).map((a) => (
          <DetailRow
            key={a.id}
            label={`${fieldTeamsById.get(a.field_team_id)?.name ?? "Team"} — ${a.deployment_start_date} to ${a.actual_return_date ?? a.expected_return_date}`}
            value={a.status}
          />
        ))}
        {(assignmentsQuery.data ?? []).length === 0 && <p className="text-sm text-slate-400">Never assigned to a field team.</p>}
      </Section>

      <Section title="Movement History" action={<Button variant="secondary" onClick={() => setShowMovement(true)}>Record movement</Button>}>
        {(movementsQuery.data ?? []).map((m) => (
          <DetailRow key={m.id} label={`${m.transfer_date} — ${m.purpose ?? "Transfer"}`} value={`${m.released_by_name ?? "-"} → ${m.received_by_name ?? "pending"}`} />
        ))}
        {(movementsQuery.data ?? []).length === 0 && <p className="text-sm text-slate-400">No recorded movements.</p>}
      </Section>

      <Section title="Connectivity Check-Ins" action={<Button variant="secondary" onClick={() => setShowCheckin(true)}>Submit check-in</Button>}>
        {(checkinsQuery.data ?? []).slice(0, 10).map((c) => (
          <DetailRow key={c.id} label={new Date(c.checkin_at).toLocaleString()} value={`${c.connectivity_quality}${c.technical_support_required ? " — support requested" : ""}`} />
        ))}
        {(checkinsQuery.data ?? []).length === 0 && <p className="text-sm text-slate-400">No check-ins submitted for this kit.</p>}
      </Section>

      <Section title="Maintenance & Faults" action={<Button variant="secondary" onClick={() => setShowFault(true)}>Report fault</Button>}>
        <FaultsList kitId={kitId!} />
      </Section>

      <p className="text-xs text-slate-400">
        Every action above also writes to the system-wide{" "}
        <Link to="/audit" className="text-brand-700 hover:underline">Audit Log</Link>.
      </p>

      {showInstall && <InstallDialog kitId={kitId!} onClose={() => setShowInstall(false)} onDone={invalidateAll} />}
      {showSubscription && <SubscriptionDialog kitId={kitId!} onClose={() => setShowSubscription(false)} onDone={invalidateAll} />}
      {showAssign && <AssignDialog kitId={kitId!} onClose={() => setShowAssign(false)} onDone={invalidateAll} />}
      {showReturn && <ReturnDialog assignment={showReturn} onClose={() => setShowReturn(null)} onDone={invalidateAll} />}
      {showMovement && <MovementDialog kitId={kitId!} onClose={() => setShowMovement(false)} onDone={invalidateAll} />}
      {showFault && <FaultDialog kitId={kitId!} onClose={() => setShowFault(false)} onDone={invalidateAll} />}
      {showCheckin && <CheckinDialog kitId={kitId!} onClose={() => setShowCheckin(false)} onDone={invalidateAll} />}
    </div>
  );
}

function RecordPaymentButton({ subscriptionId, onDone }: { subscriptionId: string; onDone: () => void }) {
  const [open, setOpen] = useState(false);
  const [amount, setAmount] = useState("");
  const [date, setDate] = useState(new Date().toISOString().slice(0, 10));
  const pay = useMutation({
    mutationFn: () =>
      api.post(`/starlink/subscriptions/${subscriptionId}/payments`, { payment_date: date, amount: Number(amount) }),
    onSuccess: () => {
      onDone();
      setOpen(false);
    },
  });
  return (
    <div className="mt-2">
      {!open ? (
        <Button variant="secondary" onClick={() => setOpen(true)}>Record payment</Button>
      ) : (
        <div className="flex flex-wrap items-end gap-2">
          <div className="space-y-1">
            <Label>Date</Label>
            <Input type="date" value={date} onChange={(e) => setDate(e.target.value)} />
          </div>
          <div className="space-y-1">
            <Label>Amount</Label>
            <Input type="number" step="0.01" value={amount} onChange={(e) => setAmount(e.target.value)} />
          </div>
          <Button onClick={() => pay.mutate()} disabled={!amount || pay.isPending}>
            {pay.isPending ? "Saving..." : "Save"}
          </Button>
        </div>
      )}
    </div>
  );
}

function FaultsList({ kitId }: { kitId: string }) {
  const faultsQuery = useQuery({ queryKey: ["starlink-faults-kit", kitId], queryFn: () => api.get<StarlinkFault[]>("/starlink/faults") });
  const kitFaults = (faultsQuery.data ?? []).filter((f) => f.kit_id === kitId);
  if (kitFaults.length === 0) return <p className="text-sm text-slate-400">No fault tickets for this kit.</p>;
  return (
    <>
      {kitFaults.map((f) => (
        <DetailRow key={f.id} label={`${f.ticket_number} — ${f.date_reported}`} value={f.status.replaceAll("_", " ")} />
      ))}
    </>
  );
}

const installSchema = z.object({
  installation_type: z.enum(["PERMANENT", "TEMPORARY", "MOBILE"]),
  installation_date: z.string().min(1),
  technician_name: z.string().optional(),
  power_source: z.string().optional(),
  backup_power_available: z.boolean().default(false),
  connectivity_tested: z.boolean().default(false),
  download_speed_mbps: z.string().optional(),
  upload_speed_mbps: z.string().optional(),
});
type InstallValues = z.infer<typeof installSchema>;

function InstallDialog({ kitId, onClose, onDone }: { kitId: string; onClose: () => void; onDone: () => void }) {
  const { options: warehouseOptions } = useWarehouseOptions();
  const [locationId, setLocationId] = useState("");
  const { register, handleSubmit } = useForm<InstallValues>({
    resolver: zodResolver(installSchema),
    defaultValues: { installation_type: "PERMANENT", installation_date: new Date().toISOString().slice(0, 10) },
  });
  const submit = useMutation({
    mutationFn: (v: InstallValues) =>
      api.post(`/starlink/${kitId}/installations`, {
        ...v,
        location_id: locationId || undefined,
        download_speed_mbps: v.download_speed_mbps ? Number(v.download_speed_mbps) : undefined,
        upload_speed_mbps: v.upload_speed_mbps ? Number(v.upload_speed_mbps) : undefined,
      }),
    onSuccess: () => {
      onDone();
      onClose();
    },
  });

  return (
    <Dialog open onClose={onClose} title="Record installation">
      <form onSubmit={handleSubmit((v) => submit.mutate(v))} className="space-y-4">
        <div className="space-y-1.5">
          <Label>Installation type</Label>
          <Select {...register("installation_type")}>
            <option value="PERMANENT">Permanent</option>
            <option value="TEMPORARY">Temporary</option>
            <option value="MOBILE">Mobile / Roaming</option>
          </Select>
        </div>
        <div className="space-y-1.5">
          <Label>Location</Label>
          <Select value={locationId} onChange={(e) => setLocationId(e.target.value)}>
            <option value="">Unspecified</option>
            {warehouseOptions.map((w) => (
              <option key={w.id} value={w.id}>{w.name}</option>
            ))}
          </Select>
        </div>
        <div className="space-y-1.5">
          <Label>Installation date</Label>
          <Input type="date" {...register("installation_date")} />
        </div>
        <div className="space-y-1.5">
          <Label>Technician</Label>
          <Input {...register("technician_name")} />
        </div>
        <div className="space-y-1.5">
          <Label>Power source</Label>
          <Input {...register("power_source")} />
        </div>
        <label className="flex items-center gap-2 text-sm text-slate-700">
          <Checkbox {...register("backup_power_available")} /> Backup power available
        </label>
        <label className="flex items-center gap-2 text-sm text-slate-700">
          <Checkbox {...register("connectivity_tested")} /> Connectivity tested
        </label>
        <div className="grid grid-cols-2 gap-4">
          <div className="space-y-1.5">
            <Label>Download (Mbps)</Label>
            <Input type="number" step="0.1" {...register("download_speed_mbps")} />
          </div>
          <div className="space-y-1.5">
            <Label>Upload (Mbps)</Label>
            <Input type="number" step="0.1" {...register("upload_speed_mbps")} />
          </div>
        </div>
        {submit.error instanceof ApiError && <p className="text-xs text-red-600">{submit.error.message}</p>}
        <Button type="submit" className="w-full" disabled={submit.isPending}>
          {submit.isPending ? "Saving..." : "Save installation"}
        </Button>
      </form>
    </Dialog>
  );
}

const subscriptionSchema = z.object({
  plan_name: z.string().optional(),
  account_reference: z.string().optional(),
  monthly_cost: z.string().optional(),
  currency: z.string().optional(),
  next_payment_date: z.string().optional(),
  renewal_date: z.string().optional(),
  expiry_date: z.string().optional(),
  status: z.string().default("ACTIVE"),
});
type SubscriptionValues = z.infer<typeof subscriptionSchema>;

function SubscriptionDialog({ kitId, onClose, onDone }: { kitId: string; onClose: () => void; onDone: () => void }) {
  const { register, handleSubmit } = useForm<SubscriptionValues>({
    resolver: zodResolver(subscriptionSchema),
    defaultValues: { status: "ACTIVE" },
  });
  const submit = useMutation({
    mutationFn: (v: SubscriptionValues) =>
      api.post(`/starlink/${kitId}/subscriptions`, {
        ...v,
        monthly_cost: v.monthly_cost ? Number(v.monthly_cost) : undefined,
      }),
    onSuccess: () => {
      onDone();
      onClose();
    },
  });

  return (
    <Dialog open onClose={onClose} title="New subscription term">
      <form onSubmit={handleSubmit((v) => submit.mutate(v))} className="space-y-4">
        <div className="space-y-1.5">
          <Label>Plan name</Label>
          <Input {...register("plan_name")} placeholder="e.g. Starlink Business" />
        </div>
        <div className="space-y-1.5">
          <Label>Account / service reference</Label>
          <Input {...register("account_reference")} />
        </div>
        <div className="grid grid-cols-2 gap-4">
          <div className="space-y-1.5">
            <Label>Monthly cost</Label>
            <Input type="number" step="0.01" {...register("monthly_cost")} />
          </div>
          <div className="space-y-1.5">
            <Label>Currency</Label>
            <Input placeholder="USD" {...register("currency")} />
          </div>
        </div>
        <div className="grid grid-cols-2 gap-4">
          <div className="space-y-1.5">
            <Label>Next payment date</Label>
            <Input type="date" {...register("next_payment_date")} />
          </div>
          <div className="space-y-1.5">
            <Label>Expiry date</Label>
            <Input type="date" {...register("expiry_date")} />
          </div>
        </div>
        <div className="space-y-1.5">
          <Label>Status</Label>
          <Select {...register("status")}>
            {["PENDING_ACTIVATION", "ACTIVE", "EXPIRING_SOON", "PAYMENT_DUE", "PAYMENT_OVERDUE", "SUSPENDED", "EXPIRED", "CANCELLED"].map(
              (s) => (
                <option key={s} value={s}>{s.replaceAll("_", " ")}</option>
              ),
            )}
          </Select>
        </div>
        {submit.error instanceof ApiError && <p className="text-xs text-red-600">{submit.error.message}</p>}
        <Button type="submit" className="w-full" disabled={submit.isPending}>
          {submit.isPending ? "Saving..." : "Save subscription"}
        </Button>
      </form>
    </Dialog>
  );
}

const assignSchema = z.object({
  field_team_id: z.string().min(1, "Choose a field team"),
  region_id: z.string().optional(),
  district_id: z.string().optional(),
  hard_to_reach_area_id: z.string().optional(),
  field_location: z.string().optional(),
  assignment_purpose: z.string().optional(),
  deployment_start_date: z.string().min(1),
  expected_return_date: z.string().min(1),
  witnessed_by_name: z.string().optional(),
});
type AssignValues = z.infer<typeof assignSchema>;

function AssignDialog({ kitId, onClose, onDone }: { kitId: string; onClose: () => void; onDone: () => void }) {
  const teamsQuery = useQuery({ queryKey: ["field-teams"], queryFn: () => api.get<FieldTeam[]>("/starlink/field-teams") });
  const regionsQuery = useQuery({ queryKey: ["regions"], queryFn: () => api.get<Region[]>("/regions") });
  const districtsQuery = useQuery({ queryKey: ["districts"], queryFn: () => api.get<District[]>("/districts") });
  const areasQuery = useQuery({ queryKey: ["hard-to-reach-areas"], queryFn: () => api.get<HardToReachArea[]>("/starlink/hard-to-reach-areas") });

  const { register, handleSubmit, formState: { errors } } = useForm<AssignValues>({
    resolver: zodResolver(assignSchema),
    defaultValues: { deployment_start_date: new Date().toISOString().slice(0, 10) },
  });
  const submit = useMutation({
    mutationFn: (v: AssignValues) =>
      api.post(`/starlink/${kitId}/assignments`, {
        ...v,
        region_id: v.region_id || undefined,
        district_id: v.district_id || undefined,
        hard_to_reach_area_id: v.hard_to_reach_area_id || undefined,
      }),
    onSuccess: () => {
      onDone();
      onClose();
    },
  });

  return (
    <Dialog open onClose={onClose} title="Assign to field team" className="max-w-xl">
      <form onSubmit={handleSubmit((v) => submit.mutate(v))} className="max-h-[70vh] space-y-4 overflow-y-auto pr-1">
        <div className="space-y-1.5">
          <Label>Field team</Label>
          <Select {...register("field_team_id")}>
            <option value="">Select...</option>
            {teamsQuery.data?.map((t) => (
              <option key={t.id} value={t.id}>{t.team_code} — {t.name}</option>
            ))}
          </Select>
          {errors.field_team_id && <p className="text-xs text-red-600">{errors.field_team_id.message}</p>}
        </div>
        <div className="grid grid-cols-2 gap-4">
          <div className="space-y-1.5">
            <Label>Region</Label>
            <Select {...register("region_id")}>
              <option value="">Unspecified</option>
              {regionsQuery.data?.map((r) => <option key={r.id} value={r.id}>{r.name}</option>)}
            </Select>
          </div>
          <div className="space-y-1.5">
            <Label>District</Label>
            <Select {...register("district_id")}>
              <option value="">Unspecified</option>
              {districtsQuery.data?.map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}
            </Select>
          </div>
        </div>
        <div className="space-y-1.5">
          <Label>Hard-to-reach area (if applicable)</Label>
          <Select {...register("hard_to_reach_area_id")}>
            <option value="">Not applicable</option>
            {areasQuery.data?.map((a) => <option key={a.id} value={a.id}>{a.name}</option>)}
          </Select>
        </div>
        <div className="space-y-1.5">
          <Label>Field location</Label>
          <Input {...register("field_location")} />
        </div>
        <div className="space-y-1.5">
          <Label>Assignment purpose</Label>
          <Input {...register("assignment_purpose")} />
        </div>
        <div className="grid grid-cols-2 gap-4">
          <div className="space-y-1.5">
            <Label>Deployment start</Label>
            <Input type="date" {...register("deployment_start_date")} />
          </div>
          <div className="space-y-1.5">
            <Label>Expected return</Label>
            <Input type="date" {...register("expected_return_date")} />
          </div>
        </div>
        <div className="space-y-1.5">
          <Label>Witnessed by</Label>
          <Input {...register("witnessed_by_name")} />
        </div>
        {submit.error instanceof ApiError && <p className="text-xs text-red-600">{submit.error.message}</p>}
        <Button type="submit" className="w-full" disabled={submit.isPending}>
          {submit.isPending ? "Saving..." : "Deploy kit"}
        </Button>
      </form>
    </Dialog>
  );
}

const returnSchema = z.object({
  return_date: z.string().min(1),
  dish_condition: z.string().default("GOOD"),
  router_condition: z.string().default("GOOD"),
  power_supply_condition: z.string().default("GOOD"),
  missing_accessories: z.string().optional(),
  damaged_accessories: z.string().optional(),
  maintenance_required: z.boolean().default(false),
  witnessed_by_name: z.string().optional(),
});
type ReturnValues = z.infer<typeof returnSchema>;

function ReturnDialog({ assignment, onClose, onDone }: { assignment: StarlinkTeamAssignment; onClose: () => void; onDone: () => void }) {
  const { register, handleSubmit } = useForm<ReturnValues>({
    resolver: zodResolver(returnSchema),
    defaultValues: { return_date: new Date().toISOString().slice(0, 10), dish_condition: "GOOD", router_condition: "GOOD", power_supply_condition: "GOOD" },
  });
  const submit = useMutation({
    mutationFn: (v: ReturnValues) => api.post(`/starlink/assignments/${assignment.id}/return`, v),
    onSuccess: () => {
      onDone();
      onClose();
    },
  });
  const conditionOptions = ["GOOD", "FAIR", "POOR", "DAMAGED"];

  return (
    <Dialog open onClose={onClose} title="Return from field team">
      <form onSubmit={handleSubmit((v) => submit.mutate(v))} className="space-y-4">
        <div className="space-y-1.5">
          <Label>Return date</Label>
          <Input type="date" {...register("return_date")} />
        </div>
        <div className="grid grid-cols-3 gap-3">
          <div className="space-y-1.5">
            <Label>Dish</Label>
            <Select {...register("dish_condition")}>{conditionOptions.map((c) => <option key={c} value={c}>{c}</option>)}</Select>
          </div>
          <div className="space-y-1.5">
            <Label>Router</Label>
            <Select {...register("router_condition")}>{conditionOptions.map((c) => <option key={c} value={c}>{c}</option>)}</Select>
          </div>
          <div className="space-y-1.5">
            <Label>Power supply</Label>
            <Select {...register("power_supply_condition")}>{conditionOptions.map((c) => <option key={c} value={c}>{c}</option>)}</Select>
          </div>
        </div>
        <div className="space-y-1.5">
          <Label>Missing accessories (if any)</Label>
          <Input {...register("missing_accessories")} />
        </div>
        <div className="space-y-1.5">
          <Label>Damaged accessories (if any)</Label>
          <Input {...register("damaged_accessories")} />
        </div>
        <label className="flex items-center gap-2 text-sm text-slate-700">
          <Checkbox {...register("maintenance_required")} /> Needs maintenance before redeployment
        </label>
        <div className="space-y-1.5">
          <Label>Witnessed by</Label>
          <Input {...register("witnessed_by_name")} />
        </div>
        {submit.error instanceof ApiError && <p className="text-xs text-red-600">{submit.error.message}</p>}
        <Button type="submit" className="w-full" disabled={submit.isPending}>
          {submit.isPending ? "Saving..." : "Confirm return"}
        </Button>
      </form>
    </Dialog>
  );
}

const movementSchema = z.object({
  transfer_date: z.string().min(1),
  purpose: z.string().optional(),
  condition_at_release: z.string().default("GOOD"),
  witnessed_by_name: z.string().optional(),
});
type MovementValues = z.infer<typeof movementSchema>;

function MovementDialog({ kitId, onClose, onDone }: { kitId: string; onClose: () => void; onDone: () => void }) {
  const { options: warehouseOptions } = useWarehouseOptions();
  const [destinationId, setDestinationId] = useState("");
  const { register, handleSubmit } = useForm<MovementValues>({
    resolver: zodResolver(movementSchema),
    defaultValues: { transfer_date: new Date().toISOString().slice(0, 10), condition_at_release: "GOOD" },
  });
  const submit = useMutation({
    mutationFn: (v: MovementValues) =>
      api.post(`/starlink/${kitId}/movements`, { ...v, destination_location_id: destinationId || undefined }),
    onSuccess: () => {
      onDone();
      onClose();
    },
  });

  return (
    <Dialog open onClose={onClose} title="Record movement">
      <form onSubmit={handleSubmit((v) => submit.mutate(v))} className="space-y-4">
        <div className="space-y-1.5">
          <Label>Destination</Label>
          <Select value={destinationId} onChange={(e) => setDestinationId(e.target.value)}>
            <option value="">Unspecified</option>
            {warehouseOptions.map((w) => (
              <option key={w.id} value={w.id}>{w.name}</option>
            ))}
          </Select>
        </div>
        <div className="space-y-1.5">
          <Label>Transfer date</Label>
          <Input type="date" {...register("transfer_date")} />
        </div>
        <div className="space-y-1.5">
          <Label>Purpose</Label>
          <Input {...register("purpose")} />
        </div>
        <div className="space-y-1.5">
          <Label>Witnessed by</Label>
          <Input {...register("witnessed_by_name")} />
        </div>
        {submit.error instanceof ApiError && <p className="text-xs text-red-600">{submit.error.message}</p>}
        <Button type="submit" className="w-full" disabled={submit.isPending}>
          {submit.isPending ? "Saving..." : "Save movement"}
        </Button>
      </form>
    </Dialog>
  );
}

const faultSchema = z.object({
  date_reported: z.string().min(1),
  fault_description: z.string().min(1, "Required"),
  priority: z.string().default("MEDIUM"),
});
type FaultValues = z.infer<typeof faultSchema>;

function FaultDialog({ kitId, onClose, onDone }: { kitId: string; onClose: () => void; onDone: () => void }) {
  const { register, handleSubmit, formState: { errors } } = useForm<FaultValues>({
    resolver: zodResolver(faultSchema),
    defaultValues: { date_reported: new Date().toISOString().slice(0, 10), priority: "MEDIUM" },
  });
  const submit = useMutation({
    mutationFn: (v: FaultValues) => api.post(`/starlink/${kitId}/faults`, v),
    onSuccess: () => {
      onDone();
      onClose();
    },
  });

  return (
    <Dialog open onClose={onClose} title="Report a fault">
      <form onSubmit={handleSubmit((v) => submit.mutate(v))} className="space-y-4">
        <div className="space-y-1.5">
          <Label>Date reported</Label>
          <Input type="date" {...register("date_reported")} />
        </div>
        <div className="space-y-1.5">
          <Label>Priority</Label>
          <Select {...register("priority")}>
            <option value="LOW">Low</option>
            <option value="MEDIUM">Medium</option>
            <option value="HIGH">High</option>
            <option value="CRITICAL">Critical</option>
          </Select>
        </div>
        <div className="space-y-1.5">
          <Label>Fault description</Label>
          <Input {...register("fault_description")} />
          {errors.fault_description && <p className="text-xs text-red-600">{errors.fault_description.message}</p>}
        </div>
        {submit.error instanceof ApiError && <p className="text-xs text-red-600">{submit.error.message}</p>}
        <Button type="submit" className="w-full" disabled={submit.isPending}>
          {submit.isPending ? "Saving..." : "Report fault"}
        </Button>
      </form>
    </Dialog>
  );
}

const checkinSchema = z.object({
  current_location: z.string().optional(),
  starlink_operational: z.boolean().default(true),
  internet_available: z.boolean().default(true),
  power_available: z.boolean().default(true),
  connectivity_quality: z.string().default("GOOD"),
  technical_problem: z.string().optional(),
  technical_support_required: z.boolean().default(false),
  comment: z.string().optional(),
});
type CheckinValues = z.infer<typeof checkinSchema>;

function CheckinDialog({ kitId, onClose, onDone }: { kitId: string; onClose: () => void; onDone: () => void }) {
  const { register, handleSubmit } = useForm<CheckinValues>({
    resolver: zodResolver(checkinSchema),
    defaultValues: { starlink_operational: true, internet_available: true, power_available: true, connectivity_quality: "GOOD" },
  });
  const submit = useMutation({
    mutationFn: (v: CheckinValues) => api.post("/starlink/checkins", { ...v, kit_id: kitId }),
    onSuccess: () => {
      onDone();
      onClose();
    },
  });

  return (
    <Dialog open onClose={onClose} title="Daily Starlink check-in">
      <form onSubmit={handleSubmit((v) => submit.mutate(v))} className="space-y-4">
        <div className="space-y-1.5">
          <Label>Current location</Label>
          <Input {...register("current_location")} placeholder="Town / village / landmark" />
        </div>
        <label className="flex items-center gap-2 text-sm text-slate-700">
          <Checkbox {...register("starlink_operational")} /> Starlink working
        </label>
        <label className="flex items-center gap-2 text-sm text-slate-700">
          <Checkbox {...register("internet_available")} /> Internet available
        </label>
        <label className="flex items-center gap-2 text-sm text-slate-700">
          <Checkbox {...register("power_available")} /> Power available
        </label>
        <div className="space-y-1.5">
          <Label>Connectivity quality</Label>
          <Select {...register("connectivity_quality")}>
            <option value="EXCELLENT">Excellent</option>
            <option value="GOOD">Good</option>
            <option value="FAIR">Fair</option>
            <option value="POOR">Poor</option>
            <option value="OFFLINE">Offline</option>
          </Select>
        </div>
        <label className="flex items-center gap-2 text-sm text-slate-700">
          <Checkbox {...register("technical_support_required")} /> Technical support required
        </label>
        <div className="space-y-1.5">
          <Label>Technical problem (if any)</Label>
          <Input {...register("technical_problem")} />
        </div>
        <div className="space-y-1.5">
          <Label>Comment</Label>
          <Input {...register("comment")} />
        </div>
        {submit.error instanceof ApiError && <p className="text-xs text-red-600">{submit.error.message}</p>}
        <Button type="submit" className="w-full" disabled={submit.isPending}>
          {submit.isPending ? "Submitting..." : "Submit check-in"}
        </Button>
      </form>
    </Dialog>
  );
}
