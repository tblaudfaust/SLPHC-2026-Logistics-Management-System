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

/** Subtle repeating watermark of logistics glyphs (truck, crate, route pin,
 * manifest) across the branded blue background — decorative only. */
function LogisticsWatermark() {
  return (
    <svg
      className="pointer-events-none absolute inset-0 h-full w-full"
      aria-hidden="true"
      focusable="false"
    >
      <defs>
        <pattern
          id="logistics-watermark"
          width="240"
          height="240"
          patternUnits="userSpaceOnUse"
          patternTransform="rotate(-8)"
        >
          {/* delivery truck */}
          <g transform="translate(14,18)" stroke="white" strokeWidth="2" fill="none" opacity="0.10">
            <rect x="0" y="12" width="38" height="20" rx="2" />
            <path d="M38 18h13l9 9v5H38z" />
            <circle cx="13" cy="36" r="4.5" />
            <circle cx="45" cy="36" r="4.5" />
          </g>
          {/* crate */}
          <g transform="translate(150,30)" stroke="white" strokeWidth="2" fill="none" opacity="0.09">
            <path d="M0 9L19 0l19 9-19 9z" />
            <path d="M0 9v19l19 9V18z" />
            <path d="M38 9v19l-19 9V18z" />
            <path d="M0 9l19 9M38 9l-19 9" />
          </g>
          {/* route / map pin */}
          <g transform="translate(56,128)" stroke="white" strokeWidth="2" fill="none" opacity="0.10">
            <path d="M13 0c7.2 0 13 5.6 13 12.6 0 9.4-13 23.4-13 23.4S0 22 0 12.6C0 5.6 5.8 0 13 0z" />
            <circle cx="13" cy="12.6" r="4.5" />
          </g>
          {/* manifest / checklist */}
          <g transform="translate(160,150)" stroke="white" strokeWidth="2" fill="none" opacity="0.09">
            <rect x="0" y="0" width="28" height="34" rx="2.5" />
            <path d="M7 9h14M7 17h14M7 25h9" strokeLinecap="round" />
          </g>
          {/* connectivity / satellite ping, nods to Starlink kits */}
          <g transform="translate(190,90)" stroke="white" strokeWidth="2" fill="none" opacity="0.08">
            <path d="M0 14a14 14 0 0 1 14-14" strokeLinecap="round" />
            <path d="M0 7a7 7 0 0 1 7-7" strokeLinecap="round" />
            <circle cx="1.5" cy="1.5" r="1.5" fill="white" stroke="none" />
          </g>
        </pattern>
      </defs>
      <rect width="100%" height="100%" fill="url(#logistics-watermark)" />
    </svg>
  );
}

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
    <div className="relative flex min-h-screen items-center justify-center overflow-hidden bg-brand-950 px-4">
      <LogisticsWatermark />
      <div
        className="pointer-events-none absolute inset-0 bg-gradient-to-b from-transparent via-transparent to-brand-950"
        aria-hidden="true"
      />
      <div className="relative z-10 w-full max-w-md rounded-2xl bg-white p-8 shadow-2xl">
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
