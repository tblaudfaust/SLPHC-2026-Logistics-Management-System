import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useAuthStore } from "@/store/authStore";

export function SettingsPage() {
  const user = useAuthStore((s) => s.user);
  const isSystemAdmin = useAuthStore((s) => s.isSystemAdmin());

  if (!isSystemAdmin) {
    return (
      <div className="rounded-md border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
        Settings is only available to System Administrators.
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-slate-900">Settings</h1>
        <p className="text-sm text-slate-500">Account and system configuration.</p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Your account</CardTitle>
        </CardHeader>
        <CardContent className="space-y-1 text-sm text-slate-700">
          <p>
            <span className="text-slate-500">Name:</span> {user?.first_name} {user?.last_name}
          </p>
          <p>
            <span className="text-slate-500">Email:</span> {user?.email}
          </p>
          <p>
            <span className="text-slate-500">Roles:</span> {user?.roles.join(", ") || "None"}
          </p>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Notification, SMS &amp; email configuration</CardTitle>
        </CardHeader>
        <CardContent className="text-sm text-slate-600">
          Provider settings, escalation windows and readiness weights arrive with the Notifications
          module (build phase 8) — this page is a placeholder so the navigation structure matches
          the final application from the start.
        </CardContent>
      </Card>
    </div>
  );
}
