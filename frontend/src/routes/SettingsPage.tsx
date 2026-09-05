import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation } from "@tanstack/react-query";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ApiError, api } from "@/lib/api";
import { useAuthStore } from "@/store/authStore";

const changePasswordSchema = z
  .object({
    current_password: z.string().min(1, "Required"),
    new_password: z.string().min(8, "At least 8 characters"),
    confirm_password: z.string().min(1, "Required"),
  })
  .refine((v) => v.new_password === v.confirm_password, {
    message: "Passwords don't match",
    path: ["confirm_password"],
  });

type ChangePasswordValues = z.infer<typeof changePasswordSchema>;

function ChangePasswordCard() {
  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<ChangePasswordValues>({ resolver: zodResolver(changePasswordSchema) });

  const changePassword = useMutation({
    mutationFn: (values: ChangePasswordValues) =>
      api.post("/users/me/change-password", {
        current_password: values.current_password,
        new_password: values.new_password,
      }),
    onSuccess: () => reset(),
  });

  return (
    <Card>
      <CardHeader>
        <CardTitle>Change password</CardTitle>
      </CardHeader>
      <CardContent>
        <form
          onSubmit={handleSubmit((values) => changePassword.mutate(values))}
          className="max-w-sm space-y-4"
        >
          <div className="space-y-1.5">
            <Label htmlFor="current_password">Current password</Label>
            <Input id="current_password" type="password" {...register("current_password")} />
            {errors.current_password && (
              <p className="text-xs text-red-600">{errors.current_password.message}</p>
            )}
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="new_password">New password</Label>
            <Input id="new_password" type="password" {...register("new_password")} />
            {errors.new_password && <p className="text-xs text-red-600">{errors.new_password.message}</p>}
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="confirm_password">Confirm new password</Label>
            <Input id="confirm_password" type="password" {...register("confirm_password")} />
            {errors.confirm_password && (
              <p className="text-xs text-red-600">{errors.confirm_password.message}</p>
            )}
          </div>

          {changePassword.isSuccess && (
            <div className="rounded-md bg-emerald-50 px-3 py-2 text-sm text-emerald-700">
              Password updated.
            </div>
          )}
          {changePassword.error instanceof ApiError && (
            <div className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">
              {changePassword.error.message}
            </div>
          )}

          <Button type="submit" disabled={changePassword.isPending}>
            {changePassword.isPending ? "Updating..." : "Update password"}
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}

export function SettingsPage() {
  const user = useAuthStore((s) => s.user);
  const isSystemAdmin = useAuthStore((s) => s.isSystemAdmin());

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

      <ChangePasswordCard />

      {isSystemAdmin && (
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
      )}
    </div>
  );
}
