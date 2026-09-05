import { NavLink } from "react-router-dom";

import { navItems } from "@/components/layout/navConfig";
import { cn } from "@/lib/utils";
import { useAuthStore } from "@/store/authStore";

export function Sidebar() {
  const permissions = useAuthStore((s) => s.user?.permissions ?? []);
  const roles = useAuthStore((s) => s.user?.roles ?? []);
  const visibleItems = navItems.filter(
    (item) =>
      (!item.permission || permissions.includes(item.permission)) &&
      (!item.requiresRole || roles.includes(item.requiresRole)),
  );

  return (
    <aside className="flex h-full w-64 flex-col bg-brand-950 text-brand-100">
      <div className="flex items-center gap-2 border-b border-brand-800 px-5 py-5">
        <img
          src="/statistics-sl-logo.jpg"
          alt="Statistics Sierra Leone"
          className="h-9 w-9 rounded-full bg-white object-cover"
        />
        <div>
          <p className="text-sm font-semibold text-white">SLPHC 2026</p>
          <p className="text-xs text-brand-300">Logistics Command</p>
        </div>
      </div>

      <nav className="flex-1 space-y-1 overflow-y-auto px-3 py-4">
        {visibleItems.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.to === "/"}
            className={({ isActive }) =>
              cn(
                "flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors",
                isActive
                  ? "bg-brand-700 text-white"
                  : "text-brand-200 hover:bg-brand-900 hover:text-white",
              )
            }
          >
            <item.icon size={18} />
            {item.label}
          </NavLink>
        ))}
      </nav>

      <div className="border-t border-brand-800 px-5 py-4 text-xs text-brand-400">
        Every Asset Counts. Every Movement is Traceable.
      </div>
    </aside>
  );
}
