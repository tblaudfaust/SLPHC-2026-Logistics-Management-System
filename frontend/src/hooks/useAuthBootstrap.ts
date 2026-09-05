import { useEffect } from "react";

import { apiRequest, refreshAccessToken } from "@/lib/api";
import { useAuthStore } from "@/store/authStore";
import type { CurrentUser } from "@/types";

/**
 * On app load there's no access token in memory yet (it's never persisted to
 * localStorage — see authStore.ts), only the httpOnly refresh cookie from a
 * prior session. This silently exchanges that cookie for a fresh access token
 * so a page reload doesn't force a re-login.
 */
export function useAuthBootstrap() {
  const setSession = useAuthStore((s) => s.setSession);
  const clearSession = useAuthStore((s) => s.clearSession);
  const setStatus = useAuthStore((s) => s.setStatus);
  const status = useAuthStore((s) => s.status);

  useEffect(() => {
    if (status !== "idle") return;
    setStatus("loading");

    (async () => {
      try {
        // Goes through the same deduped refreshAccessToken() that api.ts's
        // 401-retry path uses, so a concurrent request elsewhere (or React
        // StrictMode's double-effect-invoke in dev) can't race this call for
        // the single-use rotating refresh token and 401 each other out.
        const accessToken = await refreshAccessToken();
        if (!accessToken) throw new Error("No active session.");
        useAuthStore.setState({ accessToken });
        const me = await apiRequest<CurrentUser>("/auth/me", { skipAuthRetry: true });
        setSession(accessToken, me);
      } catch {
        clearSession();
      }
    })();
  }, [status, setSession, clearSession, setStatus]);
}
