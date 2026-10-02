// Thin fetch wrapper for the FastAPI backend. Token storage keys match the legacy
// frontend so a session carries over while both UIs ship side by side.

export const API_BASE: string = import.meta.env.VITE_API_BASE ?? "/api";

const ACCESS_KEY = "jobcopilot_access_token";
const REFRESH_KEY = "jobcopilot_refresh_token";

export interface TokenPair {
  access_token: string;
  refresh_token?: string;
}

function read(key: string): string | null {
  try {
    return localStorage.getItem(key);
  } catch {
    return null;
  }
}

export const tokens = {
  get access() {
    return read(ACCESS_KEY);
  },
  get refresh() {
    return read(REFRESH_KEY);
  },
  set(pair: TokenPair) {
    localStorage.setItem(ACCESS_KEY, pair.access_token);
    if (pair.refresh_token) localStorage.setItem(REFRESH_KEY, pair.refresh_token);
  },
  clear() {
    localStorage.removeItem(ACCESS_KEY);
    localStorage.removeItem(REFRESH_KEY);
  },
};

export class ApiError extends Error {
  readonly status: number;
  readonly data: unknown;

  constructor(status: number, message: string, data: unknown) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.data = data;
  }
}

// FastAPI returns `detail` as a string for HTTPException and as a list for validation errors.
function errorMessage(data: unknown, fallback: string): string {
  const detail = (data as { detail?: unknown } | null)?.detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    const msgs = detail.map((d) => (d as { msg?: string })?.msg).filter(Boolean);
    if (msgs.length) return msgs.join(". ");
  }
  return fallback;
}

let unauthorizedHandler: (() => void) | null = null;

/** Called once a request is still 401 after a refresh attempt (session is gone). */
export function onUnauthorized(handler: (() => void) | null) {
  unauthorizedHandler = handler;
}

// Single-flight refresh: concurrent 401s share one /auth/refresh call.
let refreshInFlight: Promise<string | null> | null = null;

function refreshAccessToken(): Promise<string | null> {
  if (!refreshInFlight) {
    refreshInFlight = (async () => {
      const refresh = tokens.refresh;
      if (!refresh) return null;
      try {
        const res = await fetch(`${API_BASE}/auth/refresh`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ refresh_token: refresh }),
        });
        if (!res.ok) return null;
        const data = (await res.json()) as TokenPair;
        if (!data.access_token) return null;
        tokens.set(data);
        return data.access_token;
      } catch {
        return null;
      }
    })().finally(() => {
      refreshInFlight = null;
    });
  }
  return refreshInFlight;
}

export interface RequestOptions {
  method?: "GET" | "POST" | "PATCH" | "PUT" | "DELETE";
  body?: unknown;
  /** Send the bearer token and retry once after refreshing on 401. Default true. */
  auth?: boolean;
  signal?: AbortSignal;
}

export async function api<T>(path: string, opts: RequestOptions = {}): Promise<T> {
  const { method = "GET", body, auth = true, signal } = opts;

  const send = (token: string | null) => {
    const headers: Record<string, string> = { Accept: "application/json" };
    if (body !== undefined) headers["Content-Type"] = "application/json";
    if (auth && token) headers.Authorization = `Bearer ${token}`;
    return fetch(`${API_BASE}${path}`, {
      method,
      headers,
      body: body !== undefined ? JSON.stringify(body) : undefined,
      signal,
    });
  };

  let res = await send(tokens.access);

  if (res.status === 401 && auth && tokens.refresh) {
    const fresh = await refreshAccessToken();
    if (fresh) res = await send(fresh);
  }

  if (res.status === 401 && auth) {
    tokens.clear();
    unauthorizedHandler?.();
  }

  if (!res.ok) {
    const data = await res.json().catch(() => null);
    throw new ApiError(res.status, errorMessage(data, `Request failed (${res.status})`), data);
  }

  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}
