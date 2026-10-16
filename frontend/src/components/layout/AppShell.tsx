import { Outlet } from "react-router-dom";

import { AppFooter } from "@/components/layout/AppFooter";
import { Sidebar } from "@/components/layout/Sidebar";
import { Topbar } from "@/components/layout/Topbar";

export function AppShell() {
  return (
    <div className="flex h-screen w-screen overflow-hidden bg-slate-100">
      <Sidebar />
      <div className="flex flex-1 flex-col overflow-hidden">
        <Topbar />
        <main className="flex flex-1 flex-col overflow-y-auto p-6">
          <div className="flex-1">
            <Outlet />
          </div>
          <AppFooter className="mt-8 border-t border-slate-200" />
        </main>
      </div>
    </div>
  );
}
