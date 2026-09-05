import { Navigate, Outlet } from "react-router-dom";

import { Spinner } from "@/components/ui/spinner";
import { useAuthBootstrap } from "@/hooks/useAuthBootstrap";
import { useAuthStore } from "@/store/authStore";

export function ProtectedRoute() {
  useAuthBootstrap();
  const status = useAuthStore((s) => s.status);

  if (status === "idle" || status === "loading") {
    return (
      <div className="flex h-screen w-screen items-center justify-center bg-slate-100">
        <Spinner className="h-8 w-8" />
      </div>
    );
  }

  if (status === "unauthenticated") {
    return <Navigate to="/login" replace />;
  }

  return <Outlet />;
}
