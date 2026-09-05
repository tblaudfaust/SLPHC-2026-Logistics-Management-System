import { zodResolver } from "@hookform/resolvers/zod";
import { useQuery, useQueryClient, useMutation } from "@tanstack/react-query";
import { KeyRound, Pencil, Plus, ShieldCheck, Trash2, Warehouse as WarehouseIcon } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Dialog } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
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
import { useAuthStore } from "@/store/authStore";
import type {
  EffectivePermission,
  Page,
  PasswordResetResult,
  Role,
  UserDeleteResult,
  UserRecord,
  WarehouseAccess,
} from "@/types";

const createUserSchema = z.object({
  email: z.string().email(),
  password: z.string().min(8, "At least 8 characters"),
  first_name: z.string().min(1, "Required"),
  last_name: z.string().min(1, "Required"),
  phone: z.string().optional(),
  role_ids: z.array(z.string()).default([]),
});

type CreateUserValues = z.infer<typeof createUserSchema>;

const editUserSchema = z.object({
  first_name: z.string().min(1, "Required"),
  last_name: z.string().min(1, "Required"),
  email: z.string().email(),
  phone: z.string().optional(),
  is_active: z.boolean(),
  role_ids: z.array(z.string()).default([]),
});

type EditUserValues = z.infer<typeof editUserSchema>;

export function UsersPage() {
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingUser, setEditingUser] = useState<UserRecord | null>(null);
  const [permissionsUser, setPermissionsUser] = useState<UserRecord | null>(null);
  const [warehouseAccessUser, setWarehouseAccessUser] = useState<UserRecord | null>(null);
  const [resetPasswordUser, setResetPasswordUser] = useState<UserRecord | null>(null);
  const [deletingUser, setDeletingUser] = useState<UserRecord | null>(null);
  const [search, setSearch] = useState("");
  const queryClient = useQueryClient();
  const currentUser = useAuthStore((s) => s.user);
  const isSystemAdmin = useAuthStore((s) => s.isSystemAdmin());
  const canEditUsers = useAuthStore((s) => s.hasPermission("users.update"));

  const usersQuery = useQuery({
    queryKey: ["users", search],
    queryFn: () => api.get<Page<UserRecord>>("/users", { search, page_size: 25 }),
  });

  const rolesQuery = useQuery({
    queryKey: ["roles"],
    queryFn: () => api.get<Role[]>("/roles"),
  });

  const createUser = useMutation({
    mutationFn: (values: CreateUserValues) => api.post<UserRecord>("/users", values),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["users"] });
      setDialogOpen(false);
    },
  });

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-slate-900">Users</h1>
          <p className="text-sm text-slate-500">Manage system accounts, roles and geography scope.</p>
        </div>
        <Button onClick={() => setDialogOpen(true)}>
          <Plus size={16} /> New user
        </Button>
      </div>

      <Input
        placeholder="Search by name or email..."
        value={search}
        onChange={(e) => setSearch(e.target.value)}
        className="max-w-sm"
      />

      {usersQuery.isLoading && (
        <div className="flex items-center gap-2 text-sm text-slate-500">
          <Spinner /> Loading users...
        </div>
      )}

      {usersQuery.data && (
        <Table>
          <TableHead>
            <TableRow>
              <TableHeaderCell>Name</TableHeaderCell>
              <TableHeaderCell>Email</TableHeaderCell>
              <TableHeaderCell>Roles</TableHeaderCell>
              <TableHeaderCell>Status</TableHeaderCell>
              <TableHeaderCell>Last login</TableHeaderCell>
              <TableHeaderCell></TableHeaderCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {usersQuery.data.items.map((u) => (
              <TableRow key={u.id}>
                <TableCell className="font-medium text-slate-900">
                  {u.first_name} {u.last_name}
                </TableCell>
                <TableCell>{u.email}</TableCell>
                <TableCell>
                  <div className="flex flex-wrap gap-1">
                    {u.roles.map((r) => (
                      <Badge key={r.id}>{r.name}</Badge>
                    ))}
                    {u.roles.length === 0 && <span className="text-xs text-slate-400">No role</span>}
                  </div>
                </TableCell>
                <TableCell>
                  <Badge variant={u.is_active ? "success" : "neutral"}>
                    {u.is_active ? "Active" : "Inactive"}
                  </Badge>
                </TableCell>
                <TableCell>{u.last_login_at ? new Date(u.last_login_at).toLocaleString() : "Never"}</TableCell>
                <TableCell>
                  <div className="flex flex-wrap gap-2">
                    {canEditUsers && (
                      <Button variant="secondary" onClick={() => setEditingUser(u)}>
                        <Pencil size={14} /> Edit
                      </Button>
                    )}
                    {isSystemAdmin && (
                      <Button variant="secondary" onClick={() => setPermissionsUser(u)}>
                        <ShieldCheck size={14} /> Permissions
                      </Button>
                    )}
                    {isSystemAdmin && (
                      <Button variant="secondary" onClick={() => setWarehouseAccessUser(u)}>
                        <WarehouseIcon size={14} /> Warehouses
                      </Button>
                    )}
                    {isSystemAdmin && u.id !== currentUser?.id && (
                      <Button variant="secondary" onClick={() => setResetPasswordUser(u)}>
                        <KeyRound size={14} /> Reset password
                      </Button>
                    )}
                    {isSystemAdmin && u.id !== currentUser?.id && (
                      <Button variant="destructive" onClick={() => setDeletingUser(u)}>
                        <Trash2 size={14} /> Delete
                      </Button>
                    )}
                  </div>
                </TableCell>
              </TableRow>
            ))}
            {usersQuery.data.items.length === 0 && (
              <TableRow>
                <TableCell colSpan={6} className="py-8 text-center text-slate-400">
                  No users found.
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      )}

      <Dialog open={dialogOpen} onClose={() => setDialogOpen(false)} title="Create user">
        <CreateUserForm
          roles={rolesQuery.data ?? []}
          submitting={createUser.isPending}
          serverError={createUser.error instanceof ApiError ? createUser.error.message : null}
          onSubmit={(values) => createUser.mutate(values)}
        />
      </Dialog>

      {editingUser && (
        <EditUserDialog
          user={editingUser}
          roles={rolesQuery.data ?? []}
          isSystemAdmin={isSystemAdmin}
          onClose={() => setEditingUser(null)}
        />
      )}

      {permissionsUser && (
        <UserPermissionsDialog user={permissionsUser} onClose={() => setPermissionsUser(null)} />
      )}

      {warehouseAccessUser && (
        <WarehouseAccessDialog user={warehouseAccessUser} onClose={() => setWarehouseAccessUser(null)} />
      )}

      {resetPasswordUser && (
        <ResetPasswordDialog user={resetPasswordUser} onClose={() => setResetPasswordUser(null)} />
      )}

      {deletingUser && <DeleteUserDialog user={deletingUser} onClose={() => setDeletingUser(null)} />}
    </div>
  );
}

function ResetPasswordDialog({ user, onClose }: { user: UserRecord; onClose: () => void }) {
  const queryClient = useQueryClient();

  const resetMutation = useMutation({
    mutationFn: () => api.post<PasswordResetResult>(`/users/${user.id}/reset-password`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["users"] });
    },
  });

  return (
    <Dialog open onClose={onClose} title={`Reset password — ${user.first_name} ${user.last_name}`}>
      {!resetMutation.data && (
        <>
          <p className="mb-4 text-sm text-slate-500">
            This immediately replaces {user.first_name}'s password with a new random one and signs
            them out everywhere. A copy is emailed to {user.email}; you'll also see it here once, to
            hand over directly if needed.
          </p>
          {resetMutation.error instanceof ApiError && (
            <div className="mb-4 rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">
              {resetMutation.error.message}
            </div>
          )}
          <div className="flex justify-end gap-2">
            <Button variant="secondary" onClick={onClose}>
              Cancel
            </Button>
            <Button onClick={() => resetMutation.mutate()} disabled={resetMutation.isPending}>
              {resetMutation.isPending ? "Resetting..." : "Reset password"}
            </Button>
          </div>
        </>
      )}

      {resetMutation.data && (
        <>
          <p className="mb-2 text-sm text-slate-700">{resetMutation.data.detail}</p>
          <p className="mb-4 text-xs text-slate-500">
            This is shown once and can't be retrieved again — ask {user.first_name} to change it
            after signing in.
          </p>
          <div className="mb-4 rounded-md border border-slate-200 bg-slate-50 px-3 py-2 font-mono text-sm text-slate-900">
            {resetMutation.data.temporary_password}
          </div>
          <div className="flex justify-end">
            <Button onClick={onClose}>Done</Button>
          </div>
        </>
      )}
    </Dialog>
  );
}

function DeleteUserDialog({ user, onClose }: { user: UserRecord; onClose: () => void }) {
  const queryClient = useQueryClient();

  const deleteMutation = useMutation({
    mutationFn: () => api.delete<UserDeleteResult>(`/users/${user.id}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["users"] });
    },
  });

  return (
    <Dialog open onClose={onClose} title={`Delete account — ${user.first_name} ${user.last_name}`}>
      {!deleteMutation.data && (
        <>
          <p className="mb-4 text-sm text-slate-500">
            This removes {user.first_name} {user.last_name}'s account and signs them out everywhere.
            If they have any history in the system (assets, transactions, audit trail), the account
            is deactivated instead of removed, so those records stay intact.
          </p>
          {deleteMutation.error instanceof ApiError && (
            <div className="mb-4 rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">
              {deleteMutation.error.message}
            </div>
          )}
          <div className="flex justify-end gap-2">
            <Button variant="secondary" onClick={onClose}>
              Cancel
            </Button>
            <Button variant="destructive" onClick={() => deleteMutation.mutate()} disabled={deleteMutation.isPending}>
              {deleteMutation.isPending ? "Deleting..." : "Delete account"}
            </Button>
          </div>
        </>
      )}

      {deleteMutation.data && (
        <>
          <p className="mb-4 text-sm text-slate-700">{deleteMutation.data.detail}</p>
          <div className="flex justify-end">
            <Button onClick={onClose}>Done</Button>
          </div>
        </>
      )}
    </Dialog>
  );
}

function WarehouseAccessDialog({ user, onClose }: { user: UserRecord; onClose: () => void }) {
  const queryClient = useQueryClient();
  const { options: warehouseOptions, isLoading: warehousesLoading } = useWarehouseOptions();
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());

  const accessQuery = useQuery({
    queryKey: ["user-warehouse-access", user.id],
    queryFn: () => api.get<WarehouseAccess[]>(`/users/${user.id}/warehouses`),
  });

  useEffect(() => {
    if (accessQuery.data) {
      setSelectedIds(new Set(accessQuery.data.map((w) => w.id)));
    }
  }, [accessQuery.data]);

  const saveMutation = useMutation({
    mutationFn: () => api.put(`/users/${user.id}/warehouses`, { warehouse_ids: [...selectedIds] }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["user-warehouse-access", user.id] });
      onClose();
    },
  });

  function toggle(id: string) {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  return (
    <Dialog open onClose={onClose} title={`Warehouse access — ${user.first_name} ${user.last_name}`}>
      <p className="mb-4 text-sm text-slate-500">
        Leave everything unchecked for unrestricted (national) access to inventory. Checking one or
        more warehouses limits this user to viewing and acting on inventory at only those
        warehouses — receipts, transfers, adjustments and stock counts elsewhere will be blocked,
        regardless of their role's permissions.
      </p>

      {(accessQuery.isLoading || warehousesLoading) && (
        <div className="flex items-center gap-2 text-sm text-slate-500">
          <Spinner /> Loading warehouses...
        </div>
      )}

      {!accessQuery.isLoading && !warehousesLoading && (
        <div className="max-h-80 space-y-1.5 overflow-y-auto rounded-md border border-slate-200 p-2">
          {warehouseOptions.map((w) => (
            <label key={w.id} className="flex items-center gap-2 text-sm text-slate-700">
              <Checkbox checked={selectedIds.has(w.id)} onChange={() => toggle(w.id)} />
              {w.name}
            </label>
          ))}
          {warehouseOptions.length === 0 && (
            <p className="text-xs text-slate-400">No warehouses configured yet.</p>
          )}
        </div>
      )}

      {saveMutation.error instanceof ApiError && (
        <div className="mt-4 rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">
          {saveMutation.error.message}
        </div>
      )}

      <div className="mt-4 flex justify-end gap-2">
        <Button variant="secondary" onClick={onClose}>
          Cancel
        </Button>
        <Button onClick={() => saveMutation.mutate()} disabled={saveMutation.isPending}>
          {saveMutation.isPending ? "Saving..." : "Save changes"}
        </Button>
      </div>
    </Dialog>
  );
}

function EditUserDialog({
  user,
  roles,
  isSystemAdmin,
  onClose,
}: {
  user: UserRecord;
  roles: Role[];
  isSystemAdmin: boolean;
  onClose: () => void;
}) {
  const queryClient = useQueryClient();
  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<EditUserValues>({
    resolver: zodResolver(editUserSchema),
    defaultValues: {
      first_name: user.first_name,
      last_name: user.last_name,
      email: user.email,
      phone: user.phone ?? "",
      is_active: user.is_active,
      role_ids: user.roles.map((r) => r.id),
    },
  });

  const updateMutation = useMutation({
    mutationFn: (values: EditUserValues) => {
      const { role_ids, ...rest } = values;
      const payload: Record<string, unknown> = { ...rest, phone: values.phone || null };
      if (isSystemAdmin) payload.role_ids = role_ids;
      return api.put(`/users/${user.id}`, payload);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["users"] });
      onClose();
    },
  });

  return (
    <Dialog open onClose={onClose} title={`Edit user — ${user.first_name} ${user.last_name}`}>
      <form onSubmit={handleSubmit((values) => updateMutation.mutate(values))} className="space-y-4">
        <div className="grid grid-cols-2 gap-4">
          <div className="space-y-1.5">
            <Label htmlFor="edit_first_name">First name</Label>
            <Input id="edit_first_name" {...register("first_name")} />
            {errors.first_name && <p className="text-xs text-red-600">{errors.first_name.message}</p>}
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="edit_last_name">Last name</Label>
            <Input id="edit_last_name" {...register("last_name")} />
            {errors.last_name && <p className="text-xs text-red-600">{errors.last_name.message}</p>}
          </div>
        </div>

        <div className="space-y-1.5">
          <Label htmlFor="edit_email">Email address</Label>
          <Input id="edit_email" type="email" {...register("email")} />
          {errors.email && <p className="text-xs text-red-600">{errors.email.message}</p>}
        </div>

        <div className="space-y-1.5">
          <Label htmlFor="edit_phone">Mobile contact</Label>
          <Input id="edit_phone" placeholder="+232..." {...register("phone")} />
        </div>

        <label className="flex items-center gap-2 text-sm text-slate-700">
          <Checkbox {...register("is_active")} />
          Account active
        </label>

        <div className="space-y-1.5">
          <Label>Roles</Label>
          {isSystemAdmin ? (
            <div className="max-h-40 space-y-1.5 overflow-y-auto rounded-md border border-slate-200 p-2">
              {roles.map((role) => (
                <label key={role.id} className="flex items-center gap-2 text-sm text-slate-700">
                  <Checkbox value={role.id} {...register("role_ids")} />
                  {role.name}
                </label>
              ))}
              {roles.length === 0 && <p className="text-xs text-slate-400">No roles available yet.</p>}
            </div>
          ) : (
            <div className="flex flex-wrap gap-1">
              {user.roles.map((r) => (
                <Badge key={r.id}>{r.name}</Badge>
              ))}
              {user.roles.length === 0 && <span className="text-xs text-slate-400">No role</span>}
              <p className="w-full text-xs text-slate-400">
                Only a System Administrator can change a user's roles.
              </p>
            </div>
          )}
        </div>

        {updateMutation.error instanceof ApiError && (
          <div className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">
            {updateMutation.error.message}
          </div>
        )}

        <div className="flex justify-end gap-2">
          <Button type="button" variant="secondary" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" disabled={updateMutation.isPending}>
            {updateMutation.isPending ? "Saving..." : "Save changes"}
          </Button>
        </div>
      </form>
    </Dialog>
  );
}

function UserPermissionsDialog({ user, onClose }: { user: UserRecord; onClose: () => void }) {
  const queryClient = useQueryClient();
  const [effectiveCodes, setEffectiveCodes] = useState<Set<string>>(new Set());

  const permissionsQuery = useQuery({
    queryKey: ["user-permissions", user.id],
    queryFn: () => api.get<EffectivePermission[]>(`/users/${user.id}/permissions`),
  });

  useEffect(() => {
    if (permissionsQuery.data) {
      setEffectiveCodes(new Set(permissionsQuery.data.filter((p) => p.effective).map((p) => p.code)));
    }
  }, [permissionsQuery.data]);

  const grouped = useMemo(() => {
    const groups: Record<string, EffectivePermission[]> = {};
    for (const perm of permissionsQuery.data ?? []) {
      groups[perm.module] = groups[perm.module] ?? [];
      groups[perm.module].push(perm);
    }
    return groups;
  }, [permissionsQuery.data]);

  const saveMutation = useMutation({
    mutationFn: () => {
      const overrides = (permissionsQuery.data ?? []).flatMap(
        (perm): { permission_id: string; effect: "GRANT" | "REVOKE" }[] => {
          const wants = effectiveCodes.has(perm.code);
          if (wants && !perm.from_role) return [{ permission_id: perm.id, effect: "GRANT" }];
          if (!wants && perm.from_role) return [{ permission_id: perm.id, effect: "REVOKE" }];
          return [];
        },
      );
      return api.put(`/users/${user.id}/permissions`, { overrides });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["user-permissions", user.id] });
      onClose();
    },
  });

  function toggle(code: string) {
    setEffectiveCodes((prev) => {
      const next = new Set(prev);
      if (next.has(code)) next.delete(code);
      else next.add(code);
      return next;
    });
  }

  return (
    <Dialog
      open
      onClose={onClose}
      title={`Permissions — ${user.first_name} ${user.last_name}`}
      className="max-w-2xl"
    >
      <p className="mb-4 text-sm text-slate-500">
        Checked permissions apply to this user right now, whether granted by their role(s) or added
        individually below. Unchecking a role-granted permission revokes it for this user only —
        their role and other members keep it. Changes take effect the next time this user logs in.
      </p>

      {permissionsQuery.isLoading && (
        <div className="flex items-center gap-2 text-sm text-slate-500">
          <Spinner /> Loading permissions...
        </div>
      )}

      {permissionsQuery.data && (
        <div className="max-h-[26rem] space-y-4 overflow-y-auto pr-1">
          {Object.entries(grouped).map(([module, perms]) => (
            <div key={module} className="rounded-lg border border-slate-200 p-3">
              <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">{module}</p>
              <div className="space-y-1.5">
                {perms.map((perm) => {
                  const checked = effectiveCodes.has(perm.code);
                  const overridden = checked !== perm.from_role;
                  return (
                    <label key={perm.id} className="flex items-center gap-2 text-sm text-slate-700">
                      <Checkbox checked={checked} onChange={() => toggle(perm.code)} />
                      <span>{perm.code}</span>
                      {perm.from_role && (
                        <Badge variant="neutral" className="text-[10px]">
                          via role
                        </Badge>
                      )}
                      {overridden && (
                        <Badge variant={checked ? "success" : "warning"} className="text-[10px]">
                          {checked ? "granted" : "revoked"}
                        </Badge>
                      )}
                    </label>
                  );
                })}
              </div>
            </div>
          ))}
        </div>
      )}

      {saveMutation.error instanceof ApiError && (
        <div className="mt-4 rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">
          {saveMutation.error.message}
        </div>
      )}

      <div className="mt-4 flex justify-end gap-2">
        <Button variant="secondary" onClick={onClose}>
          Cancel
        </Button>
        <Button onClick={() => saveMutation.mutate()} disabled={saveMutation.isPending}>
          {saveMutation.isPending ? "Saving..." : "Save changes"}
        </Button>
      </div>
    </Dialog>
  );
}

function CreateUserForm({
  roles,
  submitting,
  serverError,
  onSubmit,
}: {
  roles: Role[];
  submitting: boolean;
  serverError: string | null;
  onSubmit: (values: CreateUserValues) => void;
}) {
  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<CreateUserValues>({
    resolver: zodResolver(createUserSchema),
    defaultValues: { role_ids: [] },
  });

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
      <div className="grid grid-cols-2 gap-4">
        <div className="space-y-1.5">
          <Label htmlFor="first_name">First name</Label>
          <Input id="first_name" {...register("first_name")} />
          {errors.first_name && <p className="text-xs text-red-600">{errors.first_name.message}</p>}
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="last_name">Last name</Label>
          <Input id="last_name" {...register("last_name")} />
          {errors.last_name && <p className="text-xs text-red-600">{errors.last_name.message}</p>}
        </div>
      </div>

      <div className="space-y-1.5">
        <Label htmlFor="email">Email</Label>
        <Input id="email" type="email" {...register("email")} />
        {errors.email && <p className="text-xs text-red-600">{errors.email.message}</p>}
      </div>

      <div className="space-y-1.5">
        <Label htmlFor="password">Temporary password</Label>
        <Input id="password" type="password" {...register("password")} />
        {errors.password && <p className="text-xs text-red-600">{errors.password.message}</p>}
      </div>

      <div className="space-y-1.5">
        <Label htmlFor="phone">Phone (optional)</Label>
        <Input id="phone" {...register("phone")} />
      </div>

      <div className="space-y-1.5">
        <Label>Roles</Label>
        <div className="max-h-40 space-y-1.5 overflow-y-auto rounded-md border border-slate-200 p-2">
          {roles.map((role) => (
            <label key={role.id} className="flex items-center gap-2 text-sm text-slate-700">
              <Checkbox value={role.id} {...register("role_ids")} />
              {role.name}
            </label>
          ))}
          {roles.length === 0 && <p className="text-xs text-slate-400">No roles available yet.</p>}
        </div>
      </div>

      {serverError && (
        <div className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">{serverError}</div>
      )}

      <Button type="submit" className="w-full" disabled={submitting}>
        {submitting ? "Creating..." : "Create user"}
      </Button>
    </form>
  );
}
