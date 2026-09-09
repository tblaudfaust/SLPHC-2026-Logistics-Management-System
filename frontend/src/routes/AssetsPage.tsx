import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeftRight, Plus, Upload } from "lucide-react";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { Link } from "react-router-dom";
import { z } from "zod";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Dialog } from "@/components/ui/dialog";
import { BulkImportDialog } from "@/routes/BulkImportDialog";
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
import { categoryLabel, useAssetCategories } from "@/hooks/useAssetCategories";
import { useWarehouseOptions } from "@/hooks/useWarehouseOptions";
import { STATUS_BADGE_VARIANT, STATUS_LABEL } from "@/lib/assetStatus";
import { ApiError, api } from "@/lib/api";
import { cn } from "@/lib/utils";
import { useAuthStore } from "@/store/authStore";
import type { AssetCategory, AssetListItem, AssetModel, AssetTransfer, LocationRecord, Page } from "@/types";

const registerAssetSchema = z.object({
  category_id: z.string().min(1, "Choose a category"),
  model_id: z.string().optional(),
  serial_number: z.string().optional(),
  imei_1: z.string().optional(),
  imei_2: z.string().optional(),
  mac_address: z.string().optional(),
  sim_or_phone_number: z.string().optional(),
  condition: z.string().default("NEW"),
  current_location_id: z.string().optional(),
  remarks: z.string().optional(),
});

type RegisterAssetValues = z.infer<typeof registerAssetSchema>;

export function AssetsPage() {
  const [tab, setTab] = useState<"register" | "transfers">("register");
  const hasPermission = useAuthStore((s) => s.hasPermission);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-slate-900">Asset Register</h1>
        <p className="text-sm text-slate-500">
          Every serialized census asset — tablets, power banks, Starlink kits and more.
        </p>
      </div>

      <div className="flex gap-1 border-b border-slate-200">
        {(["register", "transfers"] as const).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={cn(
              "px-4 py-2 text-sm font-medium capitalize",
              tab === t ? "border-b-2 border-brand-700 text-brand-700" : "text-slate-500 hover:text-slate-700",
            )}
          >
            {t === "register" ? "Register" : "Transfers"}
          </button>
        ))}
      </div>

      {tab === "register" && <RegisterTab />}
      {tab === "transfers" && (
        <AssetTransfersTab
          canTransfer={hasPermission("inventory.transfer")}
          canReceive={hasPermission("inventory.receive")}
        />
      )}
    </div>
  );
}

function RegisterTab() {
  const [dialogOpen, setDialogOpen] = useState(false);
  const [bulkImportOpen, setBulkImportOpen] = useState(false);
  const [search, setSearch] = useState("");
  const [categoryFilter, setCategoryFilter] = useState("");
  const queryClient = useQueryClient();

  const categoriesQuery = useAssetCategories("serialized");

  const assetsQuery = useQuery({
    queryKey: ["assets", search, categoryFilter],
    queryFn: () =>
      api.get<Page<AssetListItem>>("/assets", {
        search,
        category_id: categoryFilter || undefined,
        page_size: 25,
      }),
  });

  const categoriesById = new Map((categoriesQuery.data ?? []).map((c) => [c.id, c]));
  // Starlink kits are managed through their own module (Starlink
  // Management), which has its own dedicated inventory list — they stay
  // registerable here (a kit is still, physically, a serialized Asset row)
  // but don't need a second "browse by category" filter duplicating that.
  const filterableCategories = (categoriesQuery.data ?? []).filter((c) => c.code_prefix !== "STR");

  const registerAsset = useMutation({
    mutationFn: (values: RegisterAssetValues) =>
      api.post("/assets", {
        ...values,
        model_id: values.model_id || undefined,
        current_location_id: values.current_location_id || undefined,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["assets"] });
      queryClient.invalidateQueries({ queryKey: ["asset-categories"] });
      setDialogOpen(false);
    },
  });

  return (
    <div className="space-y-4">
      <div className="flex justify-end gap-2">
        <Button variant="secondary" onClick={() => setBulkImportOpen(true)}>
          <Upload size={16} /> Bulk import
        </Button>
        <Button onClick={() => setDialogOpen(true)}>
          <Plus size={16} /> Register asset
        </Button>
      </div>

      <div className="flex flex-wrap gap-3">
        <Input
          placeholder="Search by asset tag, serial or IMEI..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="max-w-sm"
        />
        <Select
          value={categoryFilter}
          onChange={(e) => setCategoryFilter(e.target.value)}
          className="max-w-xs"
        >
          <option value="">All categories</option>
          {filterableCategories.map((c) => (
            <option key={c.id} value={c.id}>
              {categoryLabel(c)}
            </option>
          ))}
        </Select>
      </div>

      {assetsQuery.isLoading && (
        <div className="flex items-center gap-2 text-sm text-slate-500">
          <Spinner /> Loading assets...
        </div>
      )}

      {assetsQuery.data && (
        <Table>
          <TableHead>
            <TableRow>
              <TableHeaderCell>Asset Tag</TableHeaderCell>
              <TableHeaderCell>Category</TableHeaderCell>
              <TableHeaderCell>Serial Number</TableHeaderCell>
              <TableHeaderCell>Status</TableHeaderCell>
              <TableHeaderCell>Condition</TableHeaderCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {assetsQuery.data.items.map((asset) => (
              <TableRow key={asset.id}>
                <TableCell className="font-medium text-brand-700">
                  <Link to={`/assets/${asset.id}`} className="hover:underline">
                    {asset.asset_tag}
                  </Link>
                </TableCell>
                <TableCell>{categoriesById.get(asset.category_id)?.name ?? "-"}</TableCell>
                <TableCell>{asset.serial_number ?? "-"}</TableCell>
                <TableCell>
                  <Badge variant={STATUS_BADGE_VARIANT[asset.status]}>{STATUS_LABEL[asset.status]}</Badge>
                </TableCell>
                <TableCell>{asset.condition}</TableCell>
              </TableRow>
            ))}
            {assetsQuery.data.items.length === 0 && (
              <TableRow>
                <TableCell colSpan={5} className="py-8 text-center text-slate-400">
                  No assets registered yet.
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      )}

      <Dialog open={dialogOpen} onClose={() => setDialogOpen(false)} title="Register asset" className="max-w-xl">
        <RegisterAssetForm
          categories={categoriesQuery.data ?? []}
          submitting={registerAsset.isPending}
          serverError={registerAsset.error instanceof ApiError ? registerAsset.error.message : null}
          onSubmit={(values) => registerAsset.mutate(values)}
        />
      </Dialog>

      <BulkImportDialog
        open={bulkImportOpen}
        onClose={() => setBulkImportOpen(false)}
        onImported={() => {
          queryClient.invalidateQueries({ queryKey: ["assets"] });
          queryClient.invalidateQueries({ queryKey: ["asset-categories"] });
        }}
      />
    </div>
  );
}

function AssetTransfersTab({ canTransfer, canReceive }: { canTransfer: boolean; canReceive: boolean }) {
  const [dispatchOpen, setDispatchOpen] = useState(false);
  const [receivingTransferId, setReceivingTransferId] = useState<string | null>(null);
  const queryClient = useQueryClient();
  const currentUser = useAuthStore((s) => s.user);

  const transfersQuery = useQuery({
    queryKey: ["asset-transfers"],
    queryFn: () => api.get<Page<AssetTransfer>>("/assets/transfers", { page_size: 50 }),
  });

  const receiveMutation = useMutation({
    mutationFn: (id: string) => api.post(`/assets/transfers/${id}/receive`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["asset-transfers"] });
      queryClient.invalidateQueries({ queryKey: ["assets"] });
      setReceivingTransferId(null);
    },
  });

  const transferBeingReceived = transfersQuery.data?.items.find((t) => t.id === receivingTransferId);

  return (
    <div className="space-y-4">
      {canTransfer && (
        <div className="flex justify-end">
          <Button onClick={() => setDispatchOpen(true)}>
            <ArrowLeftRight size={16} /> Transfer assets
          </Button>
        </div>
      )}

      {transfersQuery.isLoading && (
        <div className="flex items-center gap-2 text-sm text-slate-500">
          <Spinner /> Loading transfers...
        </div>
      )}

      <Table>
        <TableHead>
          <TableRow>
            <TableHeaderCell>Assets</TableHeaderCell>
            <TableHeaderCell>From → To</TableHeaderCell>
            <TableHeaderCell>Expected</TableHeaderCell>
            <TableHeaderCell>Status</TableHeaderCell>
            <TableHeaderCell>Released / Received by</TableHeaderCell>
            {canReceive && <TableHeaderCell></TableHeaderCell>}
          </TableRow>
        </TableHead>
        <TableBody>
          {transfersQuery.data?.items.map((t) => (
            <TableRow key={t.id}>
              <TableCell className="max-w-xs">
                <p className="font-medium text-slate-900">
                  {t.items.length} asset{t.items.length === 1 ? "" : "s"}
                </p>
                <p className="truncate text-xs text-slate-500">
                  {t.items.map((i) => i.asset.asset_tag).join(", ")}
                </p>
              </TableCell>
              <TableCell>
                {t.from_warehouse.name} → {t.to_warehouse.name}
              </TableCell>
              <TableCell>{new Date(t.expected_delivery_date).toLocaleDateString()}</TableCell>
              <TableCell>
                {t.is_overdue ? (
                  <Badge variant="destructive">OVERDUE</Badge>
                ) : (
                  <Badge variant={t.status === "RECEIVED" ? "success" : "warning"}>
                    {t.status === "IN_TRANSIT" ? "In Transit" : "Received"}
                  </Badge>
                )}
              </TableCell>
              <TableCell className="text-xs">
                {t.released_by_name}
                {t.received_by_name ? ` / ${t.received_by_name}` : ""}
              </TableCell>
              {canReceive && (
                <TableCell>
                  {t.status === "IN_TRANSIT" && (
                    <Button size="sm" variant="secondary" onClick={() => setReceivingTransferId(t.id)}>
                      Receive
                    </Button>
                  )}
                </TableCell>
              )}
            </TableRow>
          ))}
          {transfersQuery.data?.items.length === 0 && (
            <TableRow>
              <TableCell colSpan={canReceive ? 6 : 5} className="py-8 text-center text-slate-400">
                No asset transfers recorded yet.
              </TableCell>
            </TableRow>
          )}
        </TableBody>
      </Table>

      <Dialog
        open={dispatchOpen}
        onClose={() => setDispatchOpen(false)}
        title="Transfer assets"
        className="max-w-2xl"
      >
        <DispatchAssetTransferForm
          onDispatched={() => {
            queryClient.invalidateQueries({ queryKey: ["asset-transfers"] });
            queryClient.invalidateQueries({ queryKey: ["assets"] });
            setDispatchOpen(false);
          }}
        />
      </Dialog>

      <Dialog open={!!receivingTransferId} onClose={() => setReceivingTransferId(null)} title="Confirm receipt">
        {transferBeingReceived && (
          <form
            onSubmit={(e) => {
              e.preventDefault();
              receiveMutation.mutate(transferBeingReceived.id);
            }}
            className="space-y-4"
          >
            <p className="text-sm text-slate-600">
              Confirming receipt of <strong>{transferBeingReceived.items.length}</strong> asset(s) at{" "}
              {transferBeingReceived.to_warehouse.name}.
            </p>
            <div className="max-h-32 overflow-y-auto rounded-md border border-slate-200 p-2 text-xs text-slate-600">
              {transferBeingReceived.items.map((i) => i.asset.asset_tag).join(", ")}
            </div>
            <div className="space-y-1.5">
              <Label>Received by (store officer)</Label>
              <div className="flex h-9 items-center rounded-md border border-slate-200 bg-slate-50 px-3 text-sm text-slate-700">
                {currentUser ? `${currentUser.first_name} ${currentUser.last_name}` : "—"}
              </div>
              <p className="text-xs text-slate-500">
                Automatically set to your signed-in account for accountability.
              </p>
            </div>
            {receiveMutation.error instanceof ApiError && (
              <p className="text-xs text-red-600">{receiveMutation.error.message}</p>
            )}
            <Button type="submit" className="w-full" disabled={receiveMutation.isPending}>
              {receiveMutation.isPending ? "Confirming..." : "Confirm receipt"}
            </Button>
          </form>
        )}
      </Dialog>
    </div>
  );
}

function DispatchAssetTransferForm({ onDispatched }: { onDispatched: () => void }) {
  const [fromWarehouseId, setFromWarehouseId] = useState("");
  const [toWarehouseId, setToWarehouseId] = useState("");
  const [expectedDeliveryDate, setExpectedDeliveryDate] = useState("");
  const [reason, setReason] = useState("");
  const [categoryFilter, setCategoryFilter] = useState("");
  const [search, setSearch] = useState("");
  const [selectedAssetIds, setSelectedAssetIds] = useState<Set<string>>(new Set());

  const { options: warehouseOptions } = useWarehouseOptions();
  const categoriesQuery = useAssetCategories("serialized");

  const availableAssetsQuery = useQuery({
    queryKey: ["assets-for-transfer", fromWarehouseId, categoryFilter],
    queryFn: () =>
      api.get<Page<AssetListItem>>("/assets", {
        location_id: fromWarehouseId,
        status_filter: "AVAILABLE",
        category_id: categoryFilter || undefined,
        page_size: 200,
      }),
    enabled: !!fromWarehouseId,
  });

  const categoriesById = new Map((categoriesQuery.data ?? []).map((c) => [c.id, c]));

  const availableAssets = (availableAssetsQuery.data?.items ?? []).filter((a) => {
    if (!search) return true;
    const like = search.toLowerCase();
    return a.asset_tag.toLowerCase().includes(like) || (a.serial_number ?? "").toLowerCase().includes(like);
  });

  function toggleAsset(id: string) {
    setSelectedAssetIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  const dispatchMutation = useMutation({
    mutationFn: () =>
      api.post("/assets/transfers", {
        asset_ids: Array.from(selectedAssetIds),
        from_warehouse_id: fromWarehouseId,
        to_warehouse_id: toWarehouseId,
        expected_delivery_date: expectedDeliveryDate,
        reason: reason || undefined,
      }),
    onSuccess: onDispatched,
  });

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        dispatchMutation.mutate();
      }}
      className="space-y-4"
    >
      <div className="grid grid-cols-2 gap-4">
        <div className="space-y-1.5">
          <Label htmlFor="at_from">From</Label>
          <Select
            id="at_from"
            value={fromWarehouseId}
            onChange={(e) => {
              setFromWarehouseId(e.target.value);
              setSelectedAssetIds(new Set());
            }}
          >
            <option value="">Select...</option>
            {warehouseOptions.map((w) => (
              <option key={w.id} value={w.id}>
                {w.name}
              </option>
            ))}
          </Select>
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="at_to">To</Label>
          <Select id="at_to" value={toWarehouseId} onChange={(e) => setToWarehouseId(e.target.value)}>
            <option value="">Select...</option>
            {warehouseOptions
              .filter((w) => w.id !== fromWarehouseId)
              .map((w) => (
                <option key={w.id} value={w.id}>
                  {w.name}
                </option>
              ))}
          </Select>
        </div>
      </div>

      <div className="space-y-1.5">
        <Label htmlFor="at_expected">Expected delivery</Label>
        <Input
          id="at_expected"
          type="date"
          value={expectedDeliveryDate}
          onChange={(e) => setExpectedDeliveryDate(e.target.value)}
          required
        />
      </div>

      {fromWarehouseId && (
        <div className="space-y-2">
          <Label>Select assets to transfer ({selectedAssetIds.size} selected)</Label>
          <div className="flex gap-2">
            <Select
              value={categoryFilter}
              onChange={(e) => setCategoryFilter(e.target.value)}
              className="max-w-[220px]"
            >
              <option value="">All categories</option>
              {categoriesQuery.data?.map((c) => (
                <option key={c.id} value={c.id}>
                  {categoryLabel(c)}
                </option>
              ))}
            </Select>
            <Input
              placeholder="Search tag or serial..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="flex-1"
            />
          </div>
          <div className="max-h-56 overflow-y-auto rounded-md border border-slate-200">
            {availableAssetsQuery.isLoading && (
              <div className="flex items-center gap-2 p-3 text-sm text-slate-500">
                <Spinner /> Loading available assets...
              </div>
            )}
            {!availableAssetsQuery.isLoading && availableAssets.length === 0 && (
              <p className="p-3 text-center text-sm text-slate-400">
                No available assets at this warehouse{categoryFilter ? " for this category" : ""}.
              </p>
            )}
            {availableAssets.map((asset) => (
              <label
                key={asset.id}
                className="flex cursor-pointer items-center gap-2 border-b border-slate-100 px-3 py-2 text-sm last:border-b-0 hover:bg-slate-50"
              >
                <Checkbox checked={selectedAssetIds.has(asset.id)} onChange={() => toggleAsset(asset.id)} />
                <span className="font-medium text-slate-900">{asset.asset_tag}</span>
                <span className="text-slate-500">
                  {categoriesById.get(asset.category_id)?.name ?? ""}
                  {asset.serial_number ? ` · ${asset.serial_number}` : ""}
                </span>
              </label>
            ))}
          </div>
        </div>
      )}

      <div className="space-y-1.5">
        <Label htmlFor="at_reason">Reason (optional)</Label>
        <Input id="at_reason" value={reason} onChange={(e) => setReason(e.target.value)} />
      </div>

      {dispatchMutation.error instanceof ApiError && (
        <p className="text-xs text-red-600">{dispatchMutation.error.message}</p>
      )}

      <Button
        type="submit"
        className="w-full"
        disabled={
          dispatchMutation.isPending ||
          !fromWarehouseId ||
          !toWarehouseId ||
          !expectedDeliveryDate ||
          selectedAssetIds.size === 0
        }
      >
        {dispatchMutation.isPending
          ? "Dispatching..."
          : `Dispatch transfer (${selectedAssetIds.size} asset${selectedAssetIds.size === 1 ? "" : "s"})`}
      </Button>
    </form>
  );
}

function RegisterAssetForm({
  categories,
  submitting,
  serverError,
  onSubmit,
}: {
  categories: AssetCategory[];
  submitting: boolean;
  serverError: string | null;
  onSubmit: (values: RegisterAssetValues) => void;
}) {
  const {
    register,
    handleSubmit,
    watch,
    formState: { errors },
  } = useForm<RegisterAssetValues>({
    resolver: zodResolver(registerAssetSchema),
    defaultValues: { condition: "NEW" },
  });

  const selectedCategoryId = watch("category_id");

  const modelsQuery = useQuery({
    queryKey: ["asset-models", selectedCategoryId],
    queryFn: () => api.get<AssetModel[]>("/asset-models", { category_id: selectedCategoryId }),
    enabled: !!selectedCategoryId,
  });

  const locationsQuery = useQuery({
    queryKey: ["locations-for-select"],
    queryFn: () => api.get<Page<LocationRecord>>("/locations", { page_size: 100 }),
  });

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
      <div className="space-y-1.5">
        <Label htmlFor="category_id">Category</Label>
        <Select id="category_id" {...register("category_id")}>
          <option value="">Select a category...</option>
          {categories.map((c) => (
            <option key={c.id} value={c.id}>
              {categoryLabel(c)}
            </option>
          ))}
        </Select>
        {errors.category_id && <p className="text-xs text-red-600">{errors.category_id.message}</p>}
      </div>

      {selectedCategoryId && (
        <div className="space-y-1.5">
          <Label htmlFor="model_id">Model (optional)</Label>
          <Select id="model_id" {...register("model_id")}>
            <option value="">Unspecified</option>
            {modelsQuery.data?.map((m) => (
              <option key={m.id} value={m.id}>
                {m.brand} {m.model_name}
              </option>
            ))}
          </Select>
        </div>
      )}

      <div className="grid grid-cols-2 gap-4">
        <div className="space-y-1.5">
          <Label htmlFor="serial_number">Serial number</Label>
          <Input id="serial_number" {...register("serial_number")} />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="condition">Condition</Label>
          <Select id="condition" {...register("condition")}>
            {["NEW", "GOOD", "FAIR", "POOR", "DAMAGED", "UNUSABLE"].map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </Select>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div className="space-y-1.5">
          <Label htmlFor="imei_1">IMEI 1 (optional)</Label>
          <Input id="imei_1" {...register("imei_1")} />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="imei_2">IMEI 2 (optional)</Label>
          <Input id="imei_2" {...register("imei_2")} />
        </div>
      </div>

      <div className="space-y-1.5">
        <Label htmlFor="current_location_id">Initial location (optional)</Label>
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

      {serverError && (
        <div className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">{serverError}</div>
      )}

      <Button type="submit" className="w-full" disabled={submitting}>
        {submitting ? "Registering..." : "Register asset"}
      </Button>
    </form>
  );
}
