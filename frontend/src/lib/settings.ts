// Settings: two-step sign-in, devices, security activity, and your data.
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "./api";

// --- Two-step sign-in -------------------------------------------------------

export interface MfaSetup {
  secret: string;
  provisioning_uri: string;
  backup_codes: string[];
}

export function useStartMfa() {
  return useMutation({ mutationFn: () => api<MfaSetup>("/auth/mfa/setup", { method: "POST" }) });
}

export function useConfirmMfa() {
  return useMutation({ mutationFn: (code: string) => api("/auth/mfa/verify", { method: "POST", body: { code: code.replace(/\s/g, "") } }) });
}

export function useDisableMfa() {
  return useMutation({
    mutationFn: (input: { password: string } | { code: string }) => api("/auth/mfa/disable", { method: "POST", body: input }),
  });
}

// --- Devices ----------------------------------------------------------------

export interface Session {
  session_id: string;
  device_name: string;
  ip_address: string | null;
  created_at: string;
  last_active: string;
  is_current: boolean;
}

export function useSessions() {
  return useQuery({ queryKey: ["sessions"], queryFn: async () => (await api<{ sessions: Session[] }>("/auth/sessions")).sessions });
}

export function useRevokeSession() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string | "others") =>
      api(id === "others" ? "/auth/sessions" : `/auth/sessions/${encodeURIComponent(id)}`, { method: "DELETE" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["sessions"] }),
  });
}

// --- Security activity ------------------------------------------------------

export interface SecurityEvent {
  log_id: string;
  event_type: string;
  severity: string;
  ip_address: string | null;
  user_agent: string;
  created_at: string;
}

export function useSecurityActivity(limit = 10) {
  return useQuery({
    queryKey: ["security-logs", limit],
    queryFn: async () => (await api<{ logs: SecurityEvent[] }>(`/auth/security-logs?limit=${limit}`)).logs,
  });
}

const EVENT_LABELS: Record<string, string> = {
  "auth.login.success": "Signed in",
  "auth.login.failed": "Failed sign-in attempt",
  "auth.logout": "Signed out",
  "auth.login.google_sso": "Signed in with Google",
  "auth.lockout": "Account locked after failed attempts",
  "auth.mfa.challenge_issued": "Asked for a two-step code",
  "auth.mfa.setup": "Started setting up two-step sign-in",
  "auth.mfa.enabled": "Turned on two-step sign-in",
  "auth.mfa.disabled": "Turned off two-step sign-in",
  "auth.mfa.recovery_used": "Used a backup code",
  "auth.mfa.challenge_failed": "Wrong two-step code entered",
  "auth.session.revoked": "Signed out a device",
  "auth.session.revoked_all": "Signed out all other devices",
};

/** "auth.mfa.enabled" -> "Turned on two-step sign-in"; unknown types get a readable fallback. */
export function eventLabel(type: string): string {
  if (EVENT_LABELS[type]) return EVENT_LABELS[type];
  const words = type.split(".").slice(1).join(" ").replace(/_/g, " ").trim() || type;
  return words.charAt(0).toUpperCase() + words.slice(1);
}

// --- Your data --------------------------------------------------------------

export function useExportData() {
  return useMutation({
    mutationFn: () => api<unknown>("/account/export", { method: "POST" }),
    onSuccess: (data) => {
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `jobcopilot-export-${new Date().toISOString().slice(0, 10)}.json`;
      a.click();
      URL.revokeObjectURL(url);
    },
  });
}

export function useDeleteAccount() {
  return useMutation({
    mutationFn: (input: { confirm_email: string; password?: string; mfa_code?: string; google_id_token?: string }) => api("/account", { method: "DELETE", body: input }),
  });
}
