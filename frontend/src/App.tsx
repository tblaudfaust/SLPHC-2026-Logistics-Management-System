import { QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Route, Routes } from "react-router-dom";

import { AppShell } from "@/components/layout/AppShell";
import { queryClient } from "@/lib/queryClient";
import { AssetProfilePage } from "@/routes/AssetProfilePage";
import { AssetsPage } from "@/routes/AssetsPage";
import { AssetTagRedirect } from "@/routes/AssetTagRedirect";
import { AuditPage } from "@/routes/AuditPage";
import { DashboardPage } from "@/routes/DashboardPage";
import { InventoryPage } from "@/routes/InventoryPage";
import { LocationsPage } from "@/routes/LocationsPage";
import { LoginPage } from "@/routes/LoginPage";
import { NotFoundPage } from "@/routes/NotFoundPage";
import { NotificationsPage } from "@/routes/NotificationsPage";
import { ProcurementPage } from "@/routes/ProcurementPage";
import { ProtectedRoute } from "@/routes/ProtectedRoute";
import { ReportsPage } from "@/routes/ReportsPage";
import { RolesPage } from "@/routes/RolesPage";
import { SettingsPage } from "@/routes/SettingsPage";
import { UsersPage } from "@/routes/UsersPage";

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<LoginPage />} />

          <Route element={<ProtectedRoute />}>
            <Route element={<AppShell />}>
              <Route path="/" element={<DashboardPage />} />
              <Route path="/assets" element={<AssetsPage />} />
              <Route path="/assets/tag/:assetTag" element={<AssetTagRedirect />} />
              <Route path="/assets/:assetId" element={<AssetProfilePage />} />
              <Route path="/inventory" element={<InventoryPage />} />
              <Route path="/procurement" element={<ProcurementPage />} />
              <Route path="/notifications" element={<NotificationsPage />} />
              <Route path="/reports" element={<ReportsPage />} />
              <Route path="/users" element={<UsersPage />} />
              <Route path="/roles" element={<RolesPage />} />
              <Route path="/locations" element={<LocationsPage />} />
              <Route path="/audit" element={<AuditPage />} />
              <Route path="/settings" element={<SettingsPage />} />
            </Route>
          </Route>

          <Route path="*" element={<NotFoundPage />} />
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  );
}
