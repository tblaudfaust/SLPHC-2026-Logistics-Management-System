import { LogOut } from "lucide-react";
import { useNavigate } from "react-router-dom";

import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import { useAuthStore } from "@/store/authStore";

export function Topbar() {
  const user = useAuthStore((s) => s.user);
  const clearSession = useAuthStore((s) => s.clearSession);
  const navigate = useNavigate();

  async function handleLogout() {
    try {
      await api.post("/auth/logout");
    } finally {
      clearSession();
      navigate("/login", { replace: true });
    }
  }

  return (
    <header className="flex h-16 items-center justify-between border-b border-slate-200 bg-white px-6">
      <div>
        <p className="text-sm text-slate-500">Statistics Sierra Leone &middot; SLPHC 2026</p>
      </div>
      <div className="flex items-center gap-4">
        {user && (
          <div className="text-right">
            <p className="text-sm font-medium text-slate-900">
              {user.first_name} {user.last_name}
            </p>
            <p className="text-xs text-slate-500">{user.roles.join(", ") || "No role assigned"}</p>
          </div>
        )}
        <Button variant="ghost" size="sm" onClick={handleLogout}>
          <LogOut size={16} />
          Log out
        </Button>
      </div>
    </header>
  );
}
