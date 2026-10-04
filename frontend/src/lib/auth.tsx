import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { api, ApiError, onUnauthorized, tokens, type TokenPair } from "./api";

export interface User {
  user_id: string;
  email: string;
  full_name: string;
  role: string;
  email_verified: boolean;
  created_at: string;
  mfa_enabled?: boolean;
}

interface TokenResponse extends TokenPair {
  user_id: string;
  email: string;
  role: string;
  mfa_required?: boolean;
  mfa_token?: string | null;
}

export interface PublicConfig {
  google_client_id: string;
  is_production: boolean;
  demo_enabled: boolean;
}

/** A sign-in step either finishes or asks for a second factor. */
export type SignInResult = { done: true } | { done: false; mfaToken: string };

/** "unreachable": a session exists but the server couldn't confirm it (offline, 5xx). */
type Status = "loading" | "authenticated" | "anonymous" | "unreachable";

/**
 * Confirms a stored session. Only an auth rejection ends it; network errors and
 * 5xx are retried, then reported as "unreachable" so the user isn't signed out
 * by a server restart or a dropped connection.
 */
export async function confirmSession(
  fetchMe: () => Promise<void>,
  { attempts = 3, delayMs = 600 }: { attempts?: number; delayMs?: number } = {},
): Promise<"ok" | "rejected" | "unreachable"> {
  for (let i = 0; i < attempts; i++) {
    try {
      await fetchMe();
      return "ok";
    } catch (err) {
      if (err instanceof ApiError && (err.status === 401 || err.status === 403)) return "rejected";
      if (i < attempts - 1) await new Promise((r) => setTimeout(r, delayMs * (i + 1)));
    }
  }
  return "unreachable";
}

interface AuthContextValue {
  status: Status;
  user: User | null;
  login(email: string, password: string): Promise<SignInResult>;
  register(fullName: string, email: string, password: string): Promise<SignInResult>;
  google(payload: { id_token: string } | { email: string; full_name?: string }): Promise<SignInResult>;
  completeMfa(mfaToken: string, code: string): Promise<void>;
  logout(): Promise<void>;
  /** Try confirming the session again after "unreachable". */
  retry(): void;
  /** Re-read the signed-in user (after changing 2FA, for example). */
  refreshUser(): Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient();
  const [status, setStatus] = useState<Status>(tokens.access ? "loading" : "anonymous");
  const [user, setUser] = useState<User | null>(null);

  const signOutLocally = useCallback(() => {
    tokens.clear();
    setUser(null);
    setStatus("anonymous");
    queryClient.clear();
  }, [queryClient]);

  const loadMe = useCallback(async () => {
    const me = await api<User>("/auth/me");
    setUser(me);
    setStatus("authenticated");
  }, []);

  const bootstrap = useCallback(async () => {
    if (!tokens.access) return;
    setStatus("loading");
    const result = await confirmSession(loadMe);
    if (result === "rejected") signOutLocally();
    else if (result === "unreachable") setStatus("unreachable");
  }, [loadMe, signOutLocally]);

  useEffect(() => {
    onUnauthorized(signOutLocally);
    void bootstrap();
    return () => onUnauthorized(null);
  }, [bootstrap, signOutLocally]);

  const finish = useCallback(
    async (res: TokenResponse): Promise<SignInResult> => {
      if (res.mfa_required && res.mfa_token) return { done: false, mfaToken: res.mfa_token };
      tokens.set(res);
      await loadMe();
      return { done: true };
    },
    [loadMe],
  );

  const value = useMemo<AuthContextValue>(
    () => ({
      status,
      user,
      login: async (email, password) =>
        finish(await api<TokenResponse>("/auth/login", { method: "POST", body: { email, password }, auth: false })),
      register: async (full_name, email, password) =>
        finish(
          await api<TokenResponse>("/auth/register", {
            method: "POST",
            body: { full_name, email, password },
            auth: false,
          }),
        ),
      google: async (payload) =>
        finish(await api<TokenResponse>("/auth/google-sso", { method: "POST", body: payload, auth: false })),
      completeMfa: async (mfa_token, code) => {
        await finish(
          await api<TokenResponse>("/auth/mfa/login-challenge", {
            method: "POST",
            body: { mfa_token, code: code.trim() },
            auth: false,
          }),
        );
      },
      logout: async () => {
        // Revoke server-side first so the refresh token dies with the session.
        await api("/auth/logout", { method: "POST" }).catch(() => undefined);
        signOutLocally();
      },
      retry: () => void bootstrap(),
      refreshUser: loadMe,
    }),
    [status, user, finish, signOutLocally, bootstrap, loadMe],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside <AuthProvider>");
  return ctx;
}

export function initials(name: string | undefined | null): string {
  const parts = (name ?? "").trim().split(/\s+/).filter(Boolean);
  if (!parts.length) return "?";
  return (parts[0][0] + (parts.length > 1 ? parts[parts.length - 1][0] : "")).toUpperCase();
}
