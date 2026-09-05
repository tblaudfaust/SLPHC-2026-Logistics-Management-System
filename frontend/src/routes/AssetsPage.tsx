import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus, Upload } from "lucide-react";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { Link } from "react-router-dom";
import { z } from "zod";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
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
import { STATUS_BADGE_VARIANT, STATUS_LABEL } from "@/lib/assetStatus";
import { ApiError, api } from "@/lib/api";
import type { AssetCategory, AssetListItem, AssetModel, LocationRecord, Page } from "@/types";

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
  const [dialogOpen, setDialogOpen] = useState(false);
  const [bulkImportOpen, setBulkImportOpen] = useState(false);
  const [search, setSearch] = useState("");
  const [categoryFilter, setCategoryFilter] = useState("");
  const queryClient = useQueryClient();

  const categoriesQuery = useQuery({
    queryKey: ["asset-categories"],
    queryFn: () => api.get<AssetCategory[]>("/asset-categories"),
  });

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
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-slate-900">Asset Register</h1>
          <p className="text-sm text-slate-500">
            Every serialized census asset — tablets, power banks, Starlink kits and more.
          </p>
        </div>
        <div className="flex gap-2">
          <Button variant="secondary" onClick={() => setBulkImportOpen(true)}>
            <Upload size={16} /> Bulk import
          </Button>
          <Button onClick={() => setDialogOpen(true)}>
            <Plus size={16} /> Register asset
          </Button>
        </div>
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
          {categoriesQuery.data?.map((c) => (
            <option key={c.id} value={c.id}>
              {c.name}
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

  const serializedCategories = categories.filter((c) => c.tracking_type === "serialized");

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
      <div className="space-y-1.5">
        <Label htmlFor="category_id">Category</Label>
        <Select id="category_id" {...register("category_id")}>
          <option value="">Select a category...</option>
          {serializedCategories.map((c) => (
            <option key={c.id} value={c.id}>
              {c.name} ({c.code_prefix})
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
