import { zodResolver } from "@hookform/resolvers/zod";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { useNavigate } from "react-router-dom";
import { z } from "zod";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ApiError, apiRequest } from "@/lib/api";
import { useAuthStore } from "@/store/authStore";
import type { CurrentUser } from "@/types";

const loginSchema = z.object({
  email: z.string().email("Enter a valid email address"),
  password: z.string().min(1, "Password is required"),
});

type LoginFormValues = z.infer<typeof loginSchema>;

export function LoginPage() {
  const navigate = useNavigate();
  const setSession = useAuthStore((s) => s.setSession);
  const [serverError, setServerError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<LoginFormValues>({ resolver: zodResolver(loginSchema) });

  async function onSubmit(values: LoginFormValues) {
    setServerError(null);
    setSubmitting(true);
    try {
      const tokenRes = await apiRequest<{ access_token: string }>("/auth/login", {
        method: "POST",
        body: values,
        skipAuthRetry: true,
      });
      useAuthStore.setState({ accessToken: tokenRes.access_token });
      const me = await apiRequest<CurrentUser>("/auth/me", { skipAuthRetry: true });
      setSession(tokenRes.access_token, me);
      navigate("/", { replace: true });
    } catch (err) {
      if (err instanceof ApiError) {
        setServerError(err.message);
      } else {
        setServerError("Unable to reach the server. Confirm the backend is running.");
      }
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-brand-950 px-4">
      <div className="w-full max-w-md rounded-2xl bg-white p-8 shadow-2xl">
        <div className="mb-8 flex flex-col items-center text-center">
          <img
            src="/statistics-sl-logo.jpg"
            alt="Statistics Sierra Leone"
            className="mb-3 h-20 w-20 rounded-full object-cover shadow-sm"
          />
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
            Statistics Sierra Leone
          </p>
          <h1 className="text-xl font-semibold text-slate-900">SLPHC 2026 Logistics</h1>
          <p className="mt-1 text-sm text-slate-500">
            Every Asset Counts. Every Movement is Traceable.
          </p>
        </div>

        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
          <div className="space-y-1.5">
            <Label htmlFor="email">Email</Label>
            <Input id="email" type="email" autoComplete="username" {...register("email")} />
            {errors.email && <p className="text-xs text-red-600">{errors.email.message}</p>}
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="password">Password</Label>
            <Input
              id="password"
              type="password"
              autoComplete="current-password"
              {...register("password")}
            />
            {errors.password && <p className="text-xs text-red-600">{errors.password.message}</p>}
          </div>

          {serverError && (
            <div className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">{serverError}</div>
          )}

          <Button type="submit" className="w-full" disabled={submitting}>
            {submitting ? "Signing in..." : "Sign in"}
          </Button>
        </form>
      </div>
    </div>
  );
}
