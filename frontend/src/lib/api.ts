import { useAuthStore } from "@/store/authStore";

const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000/api";

export class ApiError extends Error {
  status: number;
  detail: unknown;

  constructor(status: number, message: string, detail?: unknown) {
    super(message);
    this.status = status;
    this.detail = detail;
  }
}

let refreshPromise: Promise<string | null> | null = null;

/** Deduped: concurrent callers (the auth-bootstrap check, a 401 retry from
 * some other in-flight request, React StrictMode's double-effect-invoke)
 * share one in-flight request instead of each spending the single-use
 * rotating refresh token and 401'ing each other out. */
export async function refreshAccessToken(): Promise<string | null> {
  if (!refreshPromise) {
    refreshPromise = fetch(`${BASE_URL}/auth/refresh`, { method: "POST", credentials: "include" })
      .then(async (res) => {
        if (!res.ok) return null;
        const data = await res.json();
        return data.access_token as string;
      })
      .catch(() => null)
      .finally(() => {
        refreshPromise = null;
      });
  }
  return refreshPromise;
}

interface RequestOptions {
  method?: string;
  body?: unknown;
  params?: Record<string, string | number | boolean | undefined>;
  skipAuthRetry?: boolean;
}

function buildUrl(path: string, params?: RequestOptions["params"]): string {
  const url = new URL(`${BASE_URL}${path}`);
  if (params) {
    for (const [key, value] of Object.entries(params)) {
      if (value !== undefined && value !== "") url.searchParams.set(key, String(value));
    }
  }
  return url.toString();
}

/** Issues the request with auth headers attached and transparently retries
 * once via a token refresh on 401. Shared by apiRequest (JSON) and
 * fetchAuthenticated (raw Response, e.g. for image/blob endpoints). */
async function fetchWithAuthRetry(path: string, options: RequestOptions): Promise<Response> {
  const { method = "GET", body, params, skipAuthRetry } = options;
  const token = useAuthStore.getState().accessToken;

  const res = await fetch(buildUrl(path, params), {
    method,
    credentials: "include",
    headers: {
      ...(body !== undefined ? { "Content-Type": "application/json" } : {}),
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });

  if (res.status === 401 && !skipAuthRetry) {
    const newToken = await refreshAccessToken();
    if (newToken) {
      useAuthStore.getState().setSession(newToken, useAuthStore.getState().user!);
      return fetchWithAuthRetry(path, { ...options, skipAuthRetry: true });
    }
    useAuthStore.getState().clearSession();
    throw new ApiError(401, "Session expired. Please log in again.");
  }

  return res;
}

export async function apiRequest<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const res = await fetchWithAuthRetry(path, options);

  if (!res.ok) {
    let detail: unknown;
    try {
      detail = await res.json();
    } catch {
      detail = undefined;
    }
    const message =
      (detail as { detail?: string })?.detail ?? `Request failed with status ${res.status}`;
    throw new ApiError(res.status, message, detail);
  }

  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

async function fetchBlob(path: string, params?: RequestOptions["params"]): Promise<Blob> {
  const res = await fetchWithAuthRetry(path, { params });
  if (!res.ok) throw new ApiError(res.status, `Request failed with status ${res.status}`);
  return res.blob();
}

export const api = {
  get: <T>(path: string, params?: RequestOptions["params"]) => apiRequest<T>(path, { params }),
  post: <T>(path: string, body?: unknown) => apiRequest<T>(path, { method: "POST", body }),
  put: <T>(path: string, body?: unknown) => apiRequest<T>(path, { method: "PUT", body }),
  delete: <T>(path: string) => apiRequest<T>(path, { method: "DELETE" }),
  getBlob: (path: string, params?: RequestOptions["params"]) => fetchBlob(path, params),
};
