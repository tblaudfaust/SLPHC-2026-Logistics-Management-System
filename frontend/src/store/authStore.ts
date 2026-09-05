import { create } from "zustand";

import type { CurrentUser } from "@/types";

interface AuthState {
  accessToken: string | null;
  user: CurrentUser | null;
  status: "idle" | "loading" | "authenticated" | "unauthenticated";
  setSession: (accessToken: string, user: CurrentUser) => void;
  clearSession: () => void;
  setStatus: (status: AuthState["status"]) => void;
  hasPermission: (code: string) => boolean;
  hasRole: (name: string) => boolean;
  isSystemAdmin: () => boolean;
}

export const useAuthStore = create<AuthState>((set, get) => ({
  accessToken: null,
  user: null,
  status: "idle",
  setSession: (accessToken, user) => set({ accessToken, user, status: "authenticated" }),
  clearSession: () => set({ accessToken: null, user: null, status: "unauthenticated" }),
  setStatus: (status) => set({ status }),
  hasPermission: (code) => get().user?.permissions.includes(code) ?? false,
  hasRole: (name) => get().user?.roles.includes(name) ?? false,
  isSystemAdmin: () => get().user?.roles.includes("System Administrator") ?? false,
}));
