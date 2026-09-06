import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Pencil, Plus } from "lucide-react";
import { useState } from "react";
import { useForm } from "react-hook-form";
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
import type { Page, Procurement, Supplier } from "@/types";

const supplierSchema = z.object({
  name: z.string().min(1, "Required"),
  supplier_type: z.enum(["supplier", "donor"]),
  contact_person: z.string().optional(),
  phone: z.string().optional(),
  email: z.string().optional(),
  address: z.string().optional(),
});
type SupplierValues = z.infer<typeof supplierSchema>;

const editSupplierSchema = z.object({
  name: z.string().min(1, "Required"),
  contact_person: z.string().optional(),
  phone: z.string().optional(),
  email: z.string().optional(),
  address: z.string().optional(),
  is_active: z.boolean(),
});
type EditSupplierValues = z.infer<typeof editSupplierSchema>;

const procurementSchema = z.object({
  supplier_id: z.string().optional(),
  reference: z.string().min(1, "Required"),
  description: z.string().optional(),
  order_date: z.string().optional(),
  expected_delivery_date: z.string().optional(),
});
type ProcurementValues = z.infer<typeof procurementSchema>;

export function ProcurementPage() {
  const [tab, setTab] = useState<"suppliers" | "procurements">("suppliers");
  const hasPermission = useAuthStore((s) => s.hasPermission);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-slate-900">Suppliers &amp; Procurement</h1>
        <p className="text-sm text-slate-500">Vendors, donors, and procurement batches / purchase orders.</p>
      </div>

      <div className="flex gap-1 border-b border-slate-200">
        {(["suppliers", "procurements"] as const).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={cn(
              "px-4 py-2 text-sm font-medium capitalize",
              tab === t ? "border-b-2 border-brand-700 text-brand-700" : "text-slate-500 hover:text-slate-700",
            )}
          >
            {t}
          </button>
        ))}
      </div>

      {tab === "suppliers" ? (
        <SuppliersTab canManage={hasPermission("suppliers.manage")} />
      ) : (
        <ProcurementsTab canManage={hasPermission("procurements.manage")} />
      )}
    </div>
  );
}

function SuppliersTab({ canManage }: { canManage: boolean }) {
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingSupplier, setEditingSupplier] = useState<Supplier | null>(null);
  const queryClient = useQueryClient();

  const suppliersQuery = useQuery({
    queryKey: ["suppliers"],
    queryFn: () => api.get<Page<Supplier>>("/suppliers", { page_size: 50 }),
  });

  const createSupplier = useMutation({
    mutationFn: (values: SupplierValues) => api.post("/suppliers", values),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["suppliers"] });
      setDialogOpen(false);
    },
  });

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<SupplierValues>({
    resolver: zodResolver(supplierSchema),
    defaultValues: { supplier_type: "supplier" },
  });

  return (
    <div className="space-y-4">
      {canManage && (
        <div className="flex justify-end">
          <Button onClick={() => setDialogOpen(true)}>
            <Plus size={16} /> New supplier
          </Button>
        </div>
      )}

      {suppliersQuery.isLoading && (
        <div className="flex items-center gap-2 text-sm text-slate-500">
          <Spinner /> Loading suppliers...
        </div>
      )}

      {suppliersQuery.data && (
        <Table>
          <TableHead>
            <TableRow>
              <TableHeaderCell>Name</TableHeaderCell>
              <TableHeaderCell>Type</TableHeaderCell>
              <TableHeaderCell>Contact</TableHeaderCell>
              <TableHeaderCell>Phone</TableHeaderCell>
              <TableHeaderCell>Status</TableHeaderCell>
              <TableHeaderCell></TableHeaderCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {suppliersQuery.data.items.map((s) => (
              <TableRow key={s.id}>
                <TableCell className="font-medium text-slate-900">{s.name}</TableCell>
                <TableCell className="capitalize">{s.supplier_type}</TableCell>
                <TableCell>{s.contact_person ?? "-"}</TableCell>
                <TableCell>{s.phone ?? "-"}</TableCell>
                <TableCell>
                  <Badge variant={s.is_active ? "success" : "neutral"}>
                    {s.is_active ? "Active" : "Inactive"}
                  </Badge>
                </TableCell>
                <TableCell>
                  {canManage && (
                    <Button variant="secondary" onClick={() => setEditingSupplier(s)}>
                      <Pencil size={14} /> Edit
                    </Button>
                  )}
                </TableCell>
              </TableRow>
            ))}
            {suppliersQuery.data.items.length === 0 && (
              <TableRow>
                <TableCell colSpan={6} className="py-8 text-center text-slate-400">
                  No suppliers yet.
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      )}

      {editingSupplier && (
        <EditSupplierDialog supplier={editingSupplier} onClose={() => setEditingSupplier(null)} />
      )}

      <Dialog open={dialogOpen} onClose={() => setDialogOpen(false)} title="New supplier">
        <form onSubmit={handleSubmit((v) => createSupplier.mutate(v))} className="space-y-4">
          <div className="space-y-1.5">
            <Label htmlFor="name">Name</Label>
            <Input id="name" {...register("name")} />
            {errors.name && <p className="text-xs text-red-600">{errors.name.message}</p>}
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="supplier_type">Type</Label>
            <Select id="supplier_type" {...register("supplier_type")}>
              <option value="supplier">Supplier</option>
              <option value="donor">Donor</option>
            </Select>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-1.5">
              <Label htmlFor="contact_person">Contact person</Label>
              <Input id="contact_person" {...register("contact_person")} />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="phone">Phone</Label>
              <Input id="phone" {...register("phone")} />
            </div>
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="email">Email</Label>
            <Input id="email" {...register("email")} />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="address">Address</Label>
            <Input id="address" {...register("address")} />
          </div>
          {createSupplier.error instanceof ApiError && (
            <p className="text-xs text-red-600">{createSupplier.error.message}</p>
          )}
          <Button type="submit" className="w-full" disabled={createSupplier.isPending}>
            {createSupplier.isPending ? "Saving..." : "Save supplier"}
          </Button>
        </form>
      </Dialog>
    </div>
  );
}

function EditSupplierDialog({ supplier, onClose }: { supplier: Supplier; onClose: () => void }) {
  const queryClient = useQueryClient();
  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<EditSupplierValues>({
    resolver: zodResolver(editSupplierSchema),
    defaultValues: {
      name: supplier.name,
      contact_person: supplier.contact_person ?? "",
      phone: supplier.phone ?? "",
      email: supplier.email ?? "",
      address: supplier.address ?? "",
      is_active: supplier.is_active,
    },
  });

  const updateSupplier = useMutation({
    mutationFn: (values: EditSupplierValues) => api.put(`/suppliers/${supplier.id}`, values),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["suppliers"] });
      queryClient.invalidateQueries({ queryKey: ["suppliers-for-select"] });
      onClose();
    },
  });

  return (
    <Dialog open onClose={onClose} title={`Edit supplier — ${supplier.name}`}>
      <form onSubmit={handleSubmit((v) => updateSupplier.mutate(v))} className="space-y-4">
        <div className="space-y-1.5">
          <Label htmlFor="edit_supplier_name">Name</Label>
          <Input id="edit_supplier_name" {...register("name")} />
          {errors.name && <p className="text-xs text-red-600">{errors.name.message}</p>}
        </div>
        <p className="text-xs text-slate-400">
          Type ({supplier.supplier_type === "donor" ? "Donor" : "Supplier"}) can't be changed after
          creation.
        </p>
        <div className="grid grid-cols-2 gap-4">
          <div className="space-y-1.5">
            <Label htmlFor="edit_contact_person">Contact person</Label>
            <Input id="edit_contact_person" {...register("contact_person")} />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="edit_phone">Phone</Label>
            <Input id="edit_phone" {...register("phone")} />
          </div>
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="edit_email">Email</Label>
          <Input id="edit_email" {...register("email")} />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="edit_address">Address</Label>
          <Input id="edit_address" {...register("address")} />
        </div>
        <label className="flex items-center gap-2 text-sm text-slate-700">
          <Checkbox {...register("is_active")} />
          Active
        </label>
        {updateSupplier.error instanceof ApiError && (
          <p className="text-xs text-red-600">{updateSupplier.error.message}</p>
        )}
        <div className="flex justify-end gap-2">
          <Button type="button" variant="secondary" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" disabled={updateSupplier.isPending}>
            {updateSupplier.isPending ? "Saving..." : "Save changes"}
          </Button>
        </div>
      </form>
    </Dialog>
  );
}

function ProcurementsTab({ canManage }: { canManage: boolean }) {
  const [dialogOpen, setDialogOpen] = useState(false);
  const queryClient = useQueryClient();

  const procurementsQuery = useQuery({
    queryKey: ["procurements"],
    queryFn: () => api.get<Page<Procurement>>("/procurements", { page_size: 50 }),
  });
  const suppliersQuery = useQuery({
    queryKey: ["suppliers-for-select"],
    queryFn: () => api.get<Page<Supplier>>("/suppliers", { page_size: 100 }),
  });

  const createProcurement = useMutation({
    mutationFn: (values: ProcurementValues) =>
      api.post("/procurements", { ...values, supplier_id: values.supplier_id || undefined }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["procurements"] });
      setDialogOpen(false);
    },
  });

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<ProcurementValues>({ resolver: zodResolver(procurementSchema) });

  return (
    <div className="space-y-4">
      {canManage && (
        <div className="flex justify-end">
          <Button onClick={() => setDialogOpen(true)}>
            <Plus size={16} /> New procurement
          </Button>
        </div>
      )}

      {procurementsQuery.isLoading && (
        <div className="flex items-center gap-2 text-sm text-slate-500">
          <Spinner /> Loading procurements...
        </div>
      )}

      {procurementsQuery.data && (
        <Table>
          <TableHead>
            <TableRow>
              <TableHeaderCell>Reference</TableHeaderCell>
              <TableHeaderCell>Supplier</TableHeaderCell>
              <TableHeaderCell>Status</TableHeaderCell>
              <TableHeaderCell>Order Date</TableHeaderCell>
              <TableHeaderCell>Expected Delivery</TableHeaderCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {procurementsQuery.data.items.map((p) => (
              <TableRow key={p.id}>
                <TableCell className="font-medium text-slate-900">{p.reference}</TableCell>
                <TableCell>{p.supplier?.name ?? "-"}</TableCell>
                <TableCell>
                  <Badge>{p.status.replace(/_/g, " ")}</Badge>
                </TableCell>
                <TableCell>{p.order_date ?? "-"}</TableCell>
                <TableCell>{p.expected_delivery_date ?? "-"}</TableCell>
              </TableRow>
            ))}
            {procurementsQuery.data.items.length === 0 && (
              <TableRow>
                <TableCell colSpan={5} className="py-8 text-center text-slate-400">
                  No procurements yet.
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      )}

      <Dialog open={dialogOpen} onClose={() => setDialogOpen(false)} title="New procurement">
        <form onSubmit={handleSubmit((v) => createProcurement.mutate(v))} className="space-y-4">
          <div className="space-y-1.5">
            <Label htmlFor="reference">Reference / PO number</Label>
            <Input id="reference" {...register("reference")} />
            {errors.reference && <p className="text-xs text-red-600">{errors.reference.message}</p>}
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="supplier_id">Supplier (optional)</Label>
            <Select id="supplier_id" {...register("supplier_id")}>
              <option value="">Unspecified</option>
              {suppliersQuery.data?.items.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name}
                </option>
              ))}
            </Select>
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="description">Description</Label>
            <Input id="description" {...register("description")} />
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-1.5">
              <Label htmlFor="order_date">Order date</Label>
              <Input id="order_date" type="date" {...register("order_date")} />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="expected_delivery_date">Expected delivery</Label>
              <Input id="expected_delivery_date" type="date" {...register("expected_delivery_date")} />
            </div>
          </div>
          {createProcurement.error instanceof ApiError && (
            <p className="text-xs text-red-600">{createProcurement.error.message}</p>
          )}
          <Button type="submit" className="w-full" disabled={createProcurement.isPending}>
            {createProcurement.isPending ? "Saving..." : "Save procurement"}
          </Button>
        </form>
      </Dialog>
    </div>
  );
}
