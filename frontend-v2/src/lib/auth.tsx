import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { api, onUnauthorized, tokens, type TokenPair } from "./api";

export interface User {
  user_id: string;
  email: string;
  full_name: string;
  role: string;
  email_verified: boolean;
  created_at: string;
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

type Status = "loading" | "authenticated" | "anonymous";

interface AuthContextValue {
  status: Status;
  user: User | null;
  login(email: string, password: string): Promise<SignInResult>;
  register(fullName: string, email: string, password: string): Promise<SignInResult>;
  google(payload: { id_token: string } | { email: string; full_name?: string }): Promise<SignInResult>;
  completeMfa(mfaToken: string, code: string): Promise<void>;
  logout(): Promise<void>;
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

  useEffect(() => {
    onUnauthorized(signOutLocally);
    if (tokens.access) loadMe().catch(signOutLocally);
    return () => onUnauthorized(null);
  }, [loadMe, signOutLocally]);

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
    }),
    [status, user, finish, signOutLocally],
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
