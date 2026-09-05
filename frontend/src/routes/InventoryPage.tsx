import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeftRight, ClipboardList, Plus, SlidersHorizontal } from "lucide-react";
import { useState } from "react";
import { useFieldArray, useForm } from "react-hook-form";
import { z } from "zod";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
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
import { cn } from "@/lib/utils";
import { useAuthStore } from "@/store/authStore";
import type {
  AssetCategory,
  GoodsReceipt,
  InventoryTransaction,
  Page,
  StockBalance,
  StockCount,
  StockTransfer,
  Supplier,
} from "@/types";

const NEW_CATEGORY_VALUE = "__new__";

const receiveSchema = z.object({
  warehouse_id: z.string().min(1, "Choose a warehouse"),
  supplier_id: z.string().optional(),
  delivered_by_name: z.string().optional(),
  receipt_date: z.string().optional(),
  items: z
    .array(
      z
        .object({
          category_id: z.string().min(1, "Choose or create a category"),
          new_category_name: z.string().optional(),
          quantity: z.coerce.number().int().positive(),
        })
        .refine(
          (item) => item.category_id !== NEW_CATEGORY_VALUE || !!item.new_category_name?.trim(),
          { message: "Name the new category", path: ["new_category_name"] },
        ),
    )
    .min(1),
});
type ReceiveValues = z.infer<typeof receiveSchema>;

const transferSchema = z.object({
  category_id: z.string().min(1, "Choose a category"),
  from_warehouse_id: z.string().min(1, "Choose a warehouse"),
  to_warehouse_id: z.string().min(1, "Choose a warehouse"),
  quantity: z.coerce.number().int().positive(),
  expected_delivery_date: z.string().min(1, "Required"),
  reason: z.string().optional(),
});
type TransferValues = z.infer<typeof transferSchema>;

const adjustSchema = z.object({
  warehouse_id: z.string().min(1, "Choose a warehouse"),
  category_id: z.string().min(1, "Choose a category"),
  quantity_delta: z.coerce.number().int().refine((v) => v !== 0, "Must not be zero"),
  reason: z.string().min(1, "Reason is required"),
});
type AdjustValues = z.infer<typeof adjustSchema>;

export function InventoryPage() {
  const [tab, setTab] = useState<"balances" | "receipts" | "transfers" | "transactions" | "counts">("balances");
  const hasPermission = useAuthStore((s) => s.hasPermission);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-slate-900">Inventory</h1>
        <p className="text-sm text-slate-500">
          Ledger-driven stock for quantity-tracked census materials (SIM cards, cables, bags, and more).
        </p>
      </div>

      <div className="flex gap-1 border-b border-slate-200">
        {(["balances", "receipts", "transfers", "transactions", "counts"] as const).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={cn(
              "px-4 py-2 text-sm font-medium capitalize",
              tab === t ? "border-b-2 border-brand-700 text-brand-700" : "text-slate-500 hover:text-slate-700",
            )}
          >
            {t === "counts" ? "Stock Counts" : t}
          </button>
        ))}
      </div>

      {tab === "balances" && (
        <BalancesTab
          canReceive={hasPermission("inventory.receive")}
          canTransfer={hasPermission("inventory.transfer")}
          canAdjust={hasPermission("inventory.adjust")}
        />
      )}
      {tab === "receipts" && <ReceiptsTab />}
      {tab === "transfers" && <TransfersTab canReceive={hasPermission("inventory.receive")} />}
      {tab === "transactions" && <TransactionsTab />}
      {tab === "counts" && <StockCountsTab canReconcile={hasPermission("inventory.reconcile")} />}
    </div>
  );
}

function BalancesTab({
  canReceive,
  canTransfer,
  canAdjust,
}: {
  canReceive: boolean;
  canTransfer: boolean;
  canAdjust: boolean;
}) {
  const [openDialog, setOpenDialog] = useState<"receive" | "transfer" | "adjust" | null>(null);
  const queryClient = useQueryClient();

  const balancesQuery = useQuery({
    queryKey: ["stock-balances"],
    queryFn: () => api.get<StockBalance[]>("/inventory/balances"),
  });
  const categoriesQuery = useQuery({
    queryKey: ["asset-categories"],
    queryFn: () => api.get<AssetCategory[]>("/asset-categories"),
  });
  const { options: warehouseOptions } = useWarehouseOptions();
  const quantityCategories = (categoriesQuery.data ?? []).filter((c) => c.tracking_type === "quantity");

  function invalidateAll() {
    queryClient.invalidateQueries({ queryKey: ["stock-balances"] });
    queryClient.invalidateQueries({ queryKey: ["inventory-transactions"] });
    queryClient.invalidateQueries({ queryKey: ["goods-receipts"] });
    queryClient.invalidateQueries({ queryKey: ["stock-transfers"] });
    queryClient.invalidateQueries({ queryKey: ["asset-categories"] });
    setOpenDialog(null);
  }

  const receiveMutation = useMutation({
    mutationFn: (values: ReceiveValues) =>
      api.post("/inventory/receipts", {
        ...values,
        supplier_id: values.supplier_id || undefined,
        delivered_by_name: values.delivered_by_name || undefined,
        receipt_date: values.receipt_date || undefined,
        items: values.items.map((item) =>
          item.category_id === NEW_CATEGORY_VALUE
            ? { new_category_name: item.new_category_name, quantity: item.quantity }
            : { category_id: item.category_id, quantity: item.quantity },
        ),
      }),
    onSuccess: invalidateAll,
  });
  const transferMutation = useMutation({
    mutationFn: (values: TransferValues) => api.post("/inventory/transfers", values),
    onSuccess: invalidateAll,
  });
  const adjustMutation = useMutation({
    mutationFn: (values: AdjustValues) => api.post("/inventory/adjustments", values),
    onSuccess: invalidateAll,
  });

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap justify-end gap-2">
        {canReceive && (
          <Button variant="secondary" onClick={() => setOpenDialog("receive")}>
            <Plus size={16} /> Receive stock
          </Button>
        )}
        {canTransfer && (
          <Button variant="secondary" onClick={() => setOpenDialog("transfer")}>
            <ArrowLeftRight size={16} /> Transfer stock
          </Button>
        )}
        {canAdjust && (
          <Button variant="secondary" onClick={() => setOpenDialog("adjust")}>
            <SlidersHorizontal size={16} /> Adjust stock
          </Button>
        )}
      </div>

      {balancesQuery.isLoading && (
        <div className="flex items-center gap-2 text-sm text-slate-500">
          <Spinner /> Loading balances...
        </div>
      )}

      {balancesQuery.data && (
        <Table>
          <TableHead>
            <TableRow>
              <TableHeaderCell>Warehouse</TableHeaderCell>
              <TableHeaderCell>Category</TableHeaderCell>
              <TableHeaderCell>Quantity on Hand</TableHeaderCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {balancesQuery.data.map((b) => (
              <TableRow key={`${b.warehouse_id}-${b.category_id}`}>
                <TableCell>{b.warehouse_name}</TableCell>
                <TableCell className="font-medium text-slate-900">{b.category_name}</TableCell>
                <TableCell>{b.quantity_on_hand}</TableCell>
              </TableRow>
            ))}
            {balancesQuery.data.length === 0 && (
              <TableRow>
                <TableCell colSpan={3} className="py-8 text-center text-slate-400">
                  No stock movements recorded yet.
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      )}

      <Dialog
        open={openDialog === "receive"}
        onClose={() => setOpenDialog(null)}
        title="Receive stock"
        className="max-w-xl"
      >
        <ReceiveForm
          warehouses={warehouseOptions}
          categories={quantityCategories}
          submitting={receiveMutation.isPending}
          serverError={receiveMutation.error instanceof ApiError ? receiveMutation.error.message : null}
          onSubmit={(v) => receiveMutation.mutate(v)}
        />
      </Dialog>

      <Dialog open={openDialog === "transfer"} onClose={() => setOpenDialog(null)} title="Transfer stock">
        <TransferForm
          warehouses={warehouseOptions}
          categories={quantityCategories}
          submitting={transferMutation.isPending}
          serverError={transferMutation.error instanceof ApiError ? transferMutation.error.message : null}
          onSubmit={(v) => transferMutation.mutate(v)}
        />
      </Dialog>

      <Dialog open={openDialog === "adjust"} onClose={() => setOpenDialog(null)} title="Adjust stock">
        <AdjustForm
          warehouses={warehouseOptions}
          categories={quantityCategories}
          submitting={adjustMutation.isPending}
          serverError={adjustMutation.error instanceof ApiError ? adjustMutation.error.message : null}
          onSubmit={(v) => adjustMutation.mutate(v)}
        />
      </Dialog>
    </div>
  );
}

function ReceiveForm({
  warehouses,
  categories,
  submitting,
  serverError,
  onSubmit,
}: {
  warehouses: { id: string; name: string }[];
  categories: AssetCategory[];
  submitting: boolean;
  serverError: string | null;
  onSubmit: (values: ReceiveValues) => void;
}) {
  const {
    register,
    control,
    watch,
    handleSubmit,
    formState: { errors },
  } = useForm<ReceiveValues>({
    resolver: zodResolver(receiveSchema),
    defaultValues: { items: [{ category_id: "", quantity: 1 }] },
  });
  const { fields, append, remove } = useFieldArray({ control, name: "items" });
  const watchedItems = watch("items");
  const currentUser = useAuthStore((s) => s.user);

  const suppliersQuery = useQuery({
    queryKey: ["suppliers-for-select"],
    queryFn: () => api.get<Page<Supplier>>("/suppliers", { page_size: 100 }),
  });

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
      <div className="space-y-1.5">
        <Label>Received by (store officer)</Label>
        <div className="flex h-9 items-center rounded-md border border-slate-200 bg-slate-50 px-3 text-sm text-slate-700">
          {currentUser ? `${currentUser.first_name} ${currentUser.last_name}` : "—"}
        </div>
        <p className="text-xs text-slate-500">
          Automatically set to your signed-in account for accountability — it can't be typed as
          someone else.
        </p>
      </div>

      <div className="space-y-1.5">
        <Label htmlFor="warehouse_id">Warehouse</Label>
        <Select id="warehouse_id" {...register("warehouse_id")}>
          <option value="">Select...</option>
          {warehouses.map((w) => (
            <option key={w.id} value={w.id}>
              {w.name}
            </option>
          ))}
        </Select>
        {errors.warehouse_id && <p className="text-xs text-red-600">{errors.warehouse_id.message}</p>}
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div className="space-y-1.5">
          <Label htmlFor="supplier_id">Supplier / donor (optional)</Label>
          <Select id="supplier_id" {...register("supplier_id")}>
            <option value="">Unregistered / unknown</option>
            {suppliersQuery.data?.items.map((s) => (
              <option key={s.id} value={s.id}>
                {s.name}
              </option>
            ))}
          </Select>
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="receipt_date">Receipt date</Label>
          <Input id="receipt_date" type="date" {...register("receipt_date")} />
        </div>
      </div>

      <div className="space-y-1.5">
        <Label htmlFor="delivered_by_name">Delivered by (optional)</Label>
        <Input id="delivered_by_name" placeholder="Courier / driver name" {...register("delivered_by_name")} />
      </div>

      <div className="space-y-2">
        <Label>Items received</Label>
        <p className="text-xs text-slate-500">
          Don't see the item? Choose "+ Add a new item" to create it on the spot.
        </p>
        {fields.map((field, index) => {
          const isNewCategory = watchedItems?.[index]?.category_id === NEW_CATEGORY_VALUE;
          return (
            <div key={field.id} className="space-y-1.5">
              <div className="flex gap-2">
                <Select className="flex-1" {...register(`items.${index}.category_id`)}>
                  <option value="">Select category...</option>
                  {categories.map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.name}
                    </option>
                  ))}
                  <option value={NEW_CATEGORY_VALUE}>+ Add a new item...</option>
                </Select>
                <Input
                  type="number"
                  min={1}
                  className="w-24"
                  {...register(`items.${index}.quantity`)}
                />
                <Button type="button" variant="ghost" size="sm" onClick={() => remove(index)}>
                  Remove
                </Button>
              </div>
              {isNewCategory && (
                <div>
                  <Input
                    placeholder="New item name, e.g. Face Masks"
                    {...register(`items.${index}.new_category_name`)}
                  />
                  {errors.items?.[index]?.new_category_name && (
                    <p className="text-xs text-red-600">{errors.items[index]?.new_category_name?.message}</p>
                  )}
                </div>
              )}
            </div>
          );
        })}
        <Button
          type="button"
          variant="secondary"
          size="sm"
          onClick={() => append({ category_id: "", quantity: 1 })}
        >
          <Plus size={14} /> Add line
        </Button>
      </div>

      {serverError && <p className="text-xs text-red-600">{serverError}</p>}
      <Button type="submit" className="w-full" disabled={submitting}>
        {submitting ? "Recording..." : "Record receipt"}
      </Button>
    </form>
  );
}

function TransferForm({
  warehouses,
  categories,
  submitting,
  serverError,
  onSubmit,
}: {
  warehouses: { id: string; name: string }[];
  categories: AssetCategory[];
  submitting: boolean;
  serverError: string | null;
  onSubmit: (values: TransferValues) => void;
}) {
  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<TransferValues>({ resolver: zodResolver(transferSchema) });
  const currentUser = useAuthStore((s) => s.user);

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
      <div className="space-y-1.5">
        <Label>Released by (store officer)</Label>
        <div className="flex h-9 items-center rounded-md border border-slate-200 bg-slate-50 px-3 text-sm text-slate-700">
          {currentUser ? `${currentUser.first_name} ${currentUser.last_name}` : "—"}
        </div>
        <p className="text-xs text-slate-500">
          Automatically set to your signed-in account for accountability — it can't be typed as
          someone else.
        </p>
      </div>

      <div className="space-y-1.5">
        <Label htmlFor="t_category_id">Category</Label>
        <Select id="t_category_id" {...register("category_id")}>
          <option value="">Select...</option>
          {categories.map((c) => (
            <option key={c.id} value={c.id}>
              {c.name}
            </option>
          ))}
        </Select>
        {errors.category_id && <p className="text-xs text-red-600">{errors.category_id.message}</p>}
      </div>
      <div className="grid grid-cols-2 gap-4">
        <div className="space-y-1.5">
          <Label htmlFor="from_warehouse_id">From</Label>
          <Select id="from_warehouse_id" {...register("from_warehouse_id")}>
            <option value="">Select...</option>
            {warehouses.map((w) => (
              <option key={w.id} value={w.id}>
                {w.name}
              </option>
            ))}
          </Select>
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="to_warehouse_id">To</Label>
          <Select id="to_warehouse_id" {...register("to_warehouse_id")}>
            <option value="">Select...</option>
            {warehouses.map((w) => (
              <option key={w.id} value={w.id}>
                {w.name}
              </option>
            ))}
          </Select>
        </div>
      </div>
      <div className="grid grid-cols-2 gap-4">
        <div className="space-y-1.5">
          <Label htmlFor="t_quantity">Quantity</Label>
          <Input id="t_quantity" type="number" min={1} {...register("quantity")} />
          {errors.quantity && <p className="text-xs text-red-600">{errors.quantity.message}</p>}
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="expected_delivery_date">Expected delivery</Label>
          <Input id="expected_delivery_date" type="date" {...register("expected_delivery_date")} />
          {errors.expected_delivery_date && (
            <p className="text-xs text-red-600">{errors.expected_delivery_date.message}</p>
          )}
        </div>
      </div>
      <div className="space-y-1.5">
        <Label htmlFor="t_reason">Reason (optional)</Label>
        <Input id="t_reason" {...register("reason")} />
      </div>
      {serverError && <p className="text-xs text-red-600">{serverError}</p>}
      <Button type="submit" className="w-full" disabled={submitting}>
        {submitting ? "Dispatching..." : "Dispatch transfer"}
      </Button>
      <p className="text-center text-xs text-slate-500">
        Stock leaves the source immediately but only lands at the destination once someone there
        confirms receipt (see the Transfers tab).
      </p>
    </form>
  );
}

function AdjustForm({
  warehouses,
  categories,
  submitting,
  serverError,
  onSubmit,
}: {
  warehouses: { id: string; name: string }[];
  categories: AssetCategory[];
  submitting: boolean;
  serverError: string | null;
  onSubmit: (values: AdjustValues) => void;
}) {
  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<AdjustValues>({ resolver: zodResolver(adjustSchema) });

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
      <div className="space-y-1.5">
        <Label htmlFor="a_warehouse_id">Warehouse</Label>
        <Select id="a_warehouse_id" {...register("warehouse_id")}>
          <option value="">Select...</option>
          {warehouses.map((w) => (
            <option key={w.id} value={w.id}>
              {w.name}
            </option>
          ))}
        </Select>
      </div>
      <div className="space-y-1.5">
        <Label htmlFor="a_category_id">Category</Label>
        <Select id="a_category_id" {...register("category_id")}>
          <option value="">Select...</option>
          {categories.map((c) => (
            <option key={c.id} value={c.id}>
              {c.name}
            </option>
          ))}
        </Select>
      </div>
      <div className="space-y-1.5">
        <Label htmlFor="quantity_delta">Signed correction (e.g. -5 or 10)</Label>
        <Input id="quantity_delta" type="number" {...register("quantity_delta")} />
        {errors.quantity_delta && <p className="text-xs text-red-600">{errors.quantity_delta.message}</p>}
      </div>
      <div className="space-y-1.5">
        <Label htmlFor="a_reason">Reason</Label>
        <Input id="a_reason" {...register("reason")} />
        {errors.reason && <p className="text-xs text-red-600">{errors.reason.message}</p>}
      </div>
      {serverError && <p className="text-xs text-red-600">{serverError}</p>}
      <Button type="submit" className="w-full" disabled={submitting}>
        {submitting ? "Posting..." : "Post adjustment"}
      </Button>
    </form>
  );
}

function ReceiptsTab() {
  const receiptsQuery = useQuery({
    queryKey: ["goods-receipts"],
    queryFn: () => api.get<Page<GoodsReceipt>>("/inventory/receipts", { page_size: 50 }),
  });

  return (
    <div className="space-y-4">
      {receiptsQuery.isLoading && (
        <div className="flex items-center gap-2 text-sm text-slate-500">
          <Spinner /> Loading receipts...
        </div>
      )}
      <div className="space-y-4">
        {receiptsQuery.data?.items.map((r) => (
          <div key={r.id} className="rounded-lg border border-slate-200 bg-white p-4">
            <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
              <div>
                <p className="text-sm font-medium text-slate-900">
                  {r.warehouse.name} · {new Date(r.receipt_date).toLocaleDateString()}
                </p>
                <p className="text-xs text-slate-500">
                  From {r.supplier?.name ?? "an unregistered supplier"}
                </p>
              </div>
              <div className="flex gap-4 text-xs text-slate-600">
                <span>
                  <span className="text-slate-400">Received by</span> {r.received_by_name}
                </span>
                {r.delivered_by_name && (
                  <span>
                    <span className="text-slate-400">Delivered by</span> {r.delivered_by_name}
                  </span>
                )}
              </div>
            </div>
            <Table>
              <TableHead>
                <TableRow>
                  <TableHeaderCell>Category</TableHeaderCell>
                  <TableHeaderCell>Quantity</TableHeaderCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {r.items.map((item) => (
                  <TableRow key={item.id}>
                    <TableCell>{item.category.name}</TableCell>
                    <TableCell className="font-medium text-emerald-700">+{item.quantity}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
            {r.remarks && <p className="mt-2 text-xs text-slate-500">{r.remarks}</p>}
          </div>
        ))}
        {receiptsQuery.data?.items.length === 0 && (
          <p className="py-8 text-center text-sm text-slate-400">No goods receipts recorded yet.</p>
        )}
      </div>
    </div>
  );
}

function TransfersTab({ canReceive }: { canReceive: boolean }) {
  const [receivingTransferId, setReceivingTransferId] = useState<string | null>(null);
  const queryClient = useQueryClient();
  const currentUser = useAuthStore((s) => s.user);

  const transfersQuery = useQuery({
    queryKey: ["stock-transfers"],
    queryFn: () => api.get<Page<StockTransfer>>("/inventory/transfers", { page_size: 50 }),
  });

  const receiveMutation = useMutation({
    mutationFn: (id: string) => api.post(`/inventory/transfers/${id}/receive`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["stock-transfers"] });
      queryClient.invalidateQueries({ queryKey: ["stock-balances"] });
      setReceivingTransferId(null);
    },
  });

  const transferBeingReceived = transfersQuery.data?.items.find((t) => t.id === receivingTransferId);

  return (
    <div className="space-y-4">
      {transfersQuery.isLoading && (
        <div className="flex items-center gap-2 text-sm text-slate-500">
          <Spinner /> Loading transfers...
        </div>
      )}
      <Table>
        <TableHead>
          <TableRow>
            <TableHeaderCell>Category</TableHeaderCell>
            <TableHeaderCell>From → To</TableHeaderCell>
            <TableHeaderCell>Qty</TableHeaderCell>
            <TableHeaderCell>Expected</TableHeaderCell>
            <TableHeaderCell>Status</TableHeaderCell>
            <TableHeaderCell>Released / Received by</TableHeaderCell>
            {canReceive && <TableHeaderCell></TableHeaderCell>}
          </TableRow>
        </TableHead>
        <TableBody>
          {transfersQuery.data?.items.map((t) => (
            <TableRow key={t.id}>
              <TableCell className="font-medium text-slate-900">{t.category.name}</TableCell>
              <TableCell>
                {t.from_warehouse.name} → {t.to_warehouse.name}
              </TableCell>
              <TableCell>{t.quantity}</TableCell>
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
              <TableCell colSpan={canReceive ? 7 : 6} className="py-8 text-center text-slate-400">
                No stock transfers recorded yet.
              </TableCell>
            </TableRow>
          )}
        </TableBody>
      </Table>

      <Dialog
        open={!!receivingTransferId}
        onClose={() => setReceivingTransferId(null)}
        title="Confirm receipt"
      >
        {transferBeingReceived && (
          <form
            onSubmit={(e) => {
              e.preventDefault();
              receiveMutation.mutate(transferBeingReceived.id);
            }}
            className="space-y-4"
          >
            <p className="text-sm text-slate-600">
              Confirming receipt of <strong>{transferBeingReceived.quantity}</strong>{" "}
              {transferBeingReceived.category.name} at {transferBeingReceived.to_warehouse.name}.
            </p>
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

function TransactionsTab() {
  const transactionsQuery = useQuery({
    queryKey: ["inventory-transactions"],
    queryFn: () => api.get<Page<InventoryTransaction>>("/inventory/transactions", { page_size: 50 }),
  });

  return (
    <div className="space-y-4">
      {transactionsQuery.isLoading && (
        <div className="flex items-center gap-2 text-sm text-slate-500">
          <Spinner /> Loading ledger...
        </div>
      )}
      {transactionsQuery.data && (
        <Table>
          <TableHead>
            <TableRow>
              <TableHeaderCell>When</TableHeaderCell>
              <TableHeaderCell>Type</TableHeaderCell>
              <TableHeaderCell>Warehouse</TableHeaderCell>
              <TableHeaderCell>Category</TableHeaderCell>
              <TableHeaderCell>Quantity</TableHeaderCell>
              <TableHeaderCell>Reason</TableHeaderCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {transactionsQuery.data.items.map((t) => (
              <TableRow key={t.id}>
                <TableCell>{new Date(t.created_at).toLocaleString()}</TableCell>
                <TableCell>
                  <Badge variant={t.quantity >= 0 ? "success" : "destructive"}>{t.transaction_type}</Badge>
                </TableCell>
                <TableCell>{t.warehouse.name}</TableCell>
                <TableCell>{t.category.name}</TableCell>
                <TableCell className="font-medium">{t.quantity > 0 ? `+${t.quantity}` : t.quantity}</TableCell>
                <TableCell>{t.reason ?? "-"}</TableCell>
              </TableRow>
            ))}
            {transactionsQuery.data.items.length === 0 && (
              <TableRow>
                <TableCell colSpan={6} className="py-8 text-center text-slate-400">
                  No ledger activity yet.
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      )}
    </div>
  );
}

const stockCountSchema = z.object({
  warehouse_id: z.string().min(1, "Choose a warehouse"),
  count_date: z.string().min(1, "Required"),
  items: z
    .array(
      z.object({
        category_id: z.string().min(1),
        physical_quantity: z.coerce.number().int().min(0),
        variance_reason: z.string().optional(),
      }),
    )
    .min(1),
});
type StockCountValues = z.infer<typeof stockCountSchema>;

function StockCountsTab({ canReconcile }: { canReconcile: boolean }) {
  const [dialogOpen, setDialogOpen] = useState(false);
  const queryClient = useQueryClient();

  const countsQuery = useQuery({
    queryKey: ["stock-counts"],
    queryFn: () => api.get<StockCount[]>("/inventory/stock-counts"),
  });
  const categoriesQuery = useQuery({
    queryKey: ["asset-categories"],
    queryFn: () => api.get<AssetCategory[]>("/asset-categories"),
  });
  const { options: warehouseOptions } = useWarehouseOptions();

  const createCount = useMutation({
    mutationFn: (values: StockCountValues) => api.post("/inventory/stock-counts", values),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["stock-counts"] });
      setDialogOpen(false);
    },
  });
  const finalizeCount = useMutation({
    mutationFn: (id: string) => api.post(`/inventory/stock-counts/${id}/finalize`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["stock-counts"] });
      queryClient.invalidateQueries({ queryKey: ["stock-balances"] });
    },
  });

  const {
    register,
    control,
    handleSubmit,
    formState: { errors },
  } = useForm<StockCountValues>({
    resolver: zodResolver(stockCountSchema),
    defaultValues: { items: [{ category_id: "", physical_quantity: 0 }] },
  });
  const { fields, append, remove } = useFieldArray({ control, name: "items" });

  return (
    <div className="space-y-4">
      {canReconcile && (
        <div className="flex justify-end">
          <Button onClick={() => setDialogOpen(true)}>
            <ClipboardList size={16} /> New stock count
          </Button>
        </div>
      )}

      {countsQuery.isLoading && (
        <div className="flex items-center gap-2 text-sm text-slate-500">
          <Spinner /> Loading stock counts...
        </div>
      )}

      <div className="space-y-4">
        {countsQuery.data?.map((count) => (
          <div key={count.id} className="rounded-lg border border-slate-200 bg-white p-4">
            <div className="mb-2 flex items-center justify-between">
              <p className="text-sm font-medium text-slate-900">
                {count.count_date} <Badge variant={count.status === "COMPLETED" ? "success" : "warning"}>{count.status}</Badge>
              </p>
              {canReconcile && count.status === "DRAFT" && (
                <Button size="sm" onClick={() => finalizeCount.mutate(count.id)} disabled={finalizeCount.isPending}>
                  Finalize
                </Button>
              )}
            </div>
            <Table>
              <TableHead>
                <TableRow>
                  <TableHeaderCell>Category</TableHeaderCell>
                  <TableHeaderCell>Expected</TableHeaderCell>
                  <TableHeaderCell>Physical</TableHeaderCell>
                  <TableHeaderCell>Variance</TableHeaderCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {count.items.map((item) => (
                  <TableRow key={item.id}>
                    <TableCell>{item.category.name}</TableCell>
                    <TableCell>{item.expected_quantity}</TableCell>
                    <TableCell>{item.physical_quantity}</TableCell>
                    <TableCell className={item.variance !== 0 ? "font-medium text-amber-700" : ""}>
                      {item.variance > 0 ? `+${item.variance}` : item.variance}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        ))}
        {countsQuery.data?.length === 0 && (
          <p className="py-8 text-center text-sm text-slate-400">No stock counts recorded yet.</p>
        )}
      </div>

      <Dialog open={dialogOpen} onClose={() => setDialogOpen(false)} title="New stock count" className="max-w-xl">
        <form onSubmit={handleSubmit((v) => createCount.mutate(v))} className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-1.5">
              <Label htmlFor="sc_warehouse_id">Warehouse</Label>
              <Select id="sc_warehouse_id" {...register("warehouse_id")}>
                <option value="">Select...</option>
                {warehouseOptions.map((w) => (
                  <option key={w.id} value={w.id}>
                    {w.name}
                  </option>
                ))}
              </Select>
              {errors.warehouse_id && <p className="text-xs text-red-600">{errors.warehouse_id.message}</p>}
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="count_date">Count date</Label>
              <Input id="count_date" type="date" {...register("count_date")} />
            </div>
          </div>

          <div className="space-y-2">
            <Label>Counted quantities</Label>
            {fields.map((field, index) => (
              <div key={field.id} className="flex gap-2">
                <Select className="flex-1" {...register(`items.${index}.category_id`)}>
                  <option value="">Category...</option>
                  {(categoriesQuery.data ?? [])
                    .filter((c) => c.tracking_type === "quantity")
                    .map((c) => (
                      <option key={c.id} value={c.id}>
                        {c.name}
                      </option>
                    ))}
                </Select>
                <Input
                  type="number"
                  min={0}
                  className="w-24"
                  {...register(`items.${index}.physical_quantity`)}
                />
                <Input
                  placeholder="Variance reason (if any)"
                  className="w-40"
                  {...register(`items.${index}.variance_reason`)}
                />
                <Button type="button" variant="ghost" size="sm" onClick={() => remove(index)}>
                  Remove
                </Button>
              </div>
            ))}
            <Button
              type="button"
              variant="secondary"
              size="sm"
              onClick={() => append({ category_id: "", physical_quantity: 0 })}
            >
              <Plus size={14} /> Add line
            </Button>
          </div>

          {createCount.error instanceof ApiError && (
            <p className="text-xs text-red-600">{createCount.error.message}</p>
          )}
          <Button type="submit" className="w-full" disabled={createCount.isPending}>
            {createCount.isPending ? "Saving..." : "Save stock count"}
          </Button>
        </form>
      </Dialog>
    </div>
  );
}
