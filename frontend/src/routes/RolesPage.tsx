import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ShieldCheck } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Spinner } from "@/components/ui/spinner";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";
import { useAuthStore } from "@/store/authStore";
import type { Permission, Role } from "@/types";

export function RolesPage() {
  const queryClient = useQueryClient();
  const isSystemAdmin = useAuthStore((s) => s.isSystemAdmin());
  const [selectedRoleId, setSelectedRoleId] = useState<string | null>(null);
  const [checkedCodes, setCheckedCodes] = useState<Set<string>>(new Set());

  const rolesQuery = useQuery({ queryKey: ["roles"], queryFn: () => api.get<Role[]>("/roles") });
  const permissionsQuery = useQuery({
    queryKey: ["permissions"],
    queryFn: () => api.get<Permission[]>("/permissions"),
  });

  const selectedRole = rolesQuery.data?.find((r) => r.id === selectedRoleId) ?? null;

  useEffect(() => {
    if (selectedRole) {
      setCheckedCodes(new Set(selectedRole.permissions.map((p) => p.code)));
    }
  }, [selectedRole]);

  useEffect(() => {
    if (!selectedRoleId && rolesQuery.data && rolesQuery.data.length > 0) {
      setSelectedRoleId(rolesQuery.data[0].id);
    }
  }, [rolesQuery.data, selectedRoleId]);

  const grouped = useMemo(() => {
    const groups: Record<string, Permission[]> = {};
    for (const perm of permissionsQuery.data ?? []) {
      groups[perm.module] = groups[perm.module] ?? [];
      groups[perm.module].push(perm);
    }
    return groups;
  }, [permissionsQuery.data]);

  const saveMutation = useMutation({
    mutationFn: (permissionIds: string[]) =>
      api.put(`/roles/${selectedRoleId}`, { permission_ids: permissionIds }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["roles"] }),
  });

  function toggle(code: string, id: string) {
    setCheckedCodes((prev) => {
      const next = new Set(prev);
      if (next.has(code)) next.delete(code);
      else next.add(code);
      return next;
    });
    void id;
  }

  function handleSave() {
    if (!permissionsQuery.data) return;
    const ids = permissionsQuery.data.filter((p) => checkedCodes.has(p.code)).map((p) => p.id);
    saveMutation.mutate(ids);
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-slate-900">Roles &amp; Permissions</h1>
        <p className="text-sm text-slate-500">
          Configurable RBAC — each role sees only the functions its permissions grant.
        </p>
      </div>

      {(rolesQuery.isLoading || permissionsQuery.isLoading) && (
        <div className="flex items-center gap-2 text-sm text-slate-500">
          <Spinner /> Loading roles...
        </div>
      )}

      {rolesQuery.data && permissionsQuery.data && (
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-[280px_1fr]">
          <Card className="h-fit">
            <CardContent className="space-y-1 p-2">
              {rolesQuery.data.map((role) => (
                <button
                  key={role.id}
                  onClick={() => setSelectedRoleId(role.id)}
                  className={cn(
                    "flex w-full items-center justify-between rounded-md px-3 py-2 text-left text-sm",
                    role.id === selectedRoleId
                      ? "bg-brand-700 text-white"
                      : "text-slate-700 hover:bg-slate-100",
                  )}
                >
                  <span className="flex items-center gap-2">
                    <ShieldCheck size={14} />
                    {role.name}
                  </span>
                  {role.is_system && (
                    <Badge variant={role.id === selectedRoleId ? "neutral" : "default"} className="text-[10px]">
                      system
                    </Badge>
                  )}
                </button>
              ))}
            </CardContent>
          </Card>

          <Card>
            <CardContent className="space-y-5 p-5">
              {selectedRole ? (
                <>
                  <div className="flex items-center justify-between">
                    <div>
                      <h2 className="text-lg font-semibold text-slate-900">{selectedRole.name}</h2>
                      {selectedRole.description && (
                        <p className="text-sm text-slate-500">{selectedRole.description}</p>
                      )}
                    </div>
                    {isSystemAdmin && (
                      <Button onClick={handleSave} disabled={saveMutation.isPending}>
                        {saveMutation.isPending ? "Saving..." : "Save changes"}
                      </Button>
                    )}
                  </div>

                  {!isSystemAdmin && (
                    <p className="rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800">
                      Only a System Administrator can edit roles and permissions. You're viewing this
                      read-only.
                    </p>
                  )}

                  <div className="grid gap-4 sm:grid-cols-2">
                    {Object.entries(grouped).map(([module, perms]) => (
                      <div key={module} className="rounded-lg border border-slate-200 p-3">
                        <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">
                          {module}
                        </p>
                        <div className="space-y-1.5">
                          {perms.map((perm) => (
                            <label key={perm.id} className="flex items-center gap-2 text-sm text-slate-700">
                              <Checkbox
                                checked={checkedCodes.has(perm.code)}
                                onChange={() => toggle(perm.code, perm.id)}
                                disabled={!isSystemAdmin}
                              />
                              {perm.code}
                            </label>
                          ))}
                        </div>
                      </div>
                    ))}
                  </div>
                </>
              ) : (
                <p className="text-sm text-slate-400">Select a role to edit its permissions.</p>
              )}
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  );
}
