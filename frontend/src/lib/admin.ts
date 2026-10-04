// Admin console: platform numbers, users and roles, and the admin audit trail.
import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "./api";

export const ROLES = ["FREE", "PRO", "ELITE", "ADMIN"] as const;
export type Role = (typeof ROLES)[number];

export interface AdminMetrics {
  total_users: number;
  total_jobs: number;
  total_applications: number;
  total_organizations: number;
  active_subscriptions: Record<string, number>;
}

export interface AdminUser {
  user_id: string;
  email: string;
  full_name: string;
  role: string;
  is_active: boolean | number;
  email_verified: boolean | number;
  created_at: string;
}

export interface AuditEntry {
  log_id: string;
  admin_id: string;
  action: string;
  target_user_id: string | null;
  details: Record<string, unknown>;
  created_at: string;
}

export const PAGE_SIZE = 25;

export function useAdminMetrics() {
  return useQuery({ queryKey: ["admin", "metrics"], queryFn: () => api<AdminMetrics>("/admin/metrics") });
}

export function useAdminUsers(search: string, page: number) {
  return useQuery({
    queryKey: ["admin", "users", search, page],
    queryFn: () => {
      const q = new URLSearchParams({ limit: String(PAGE_SIZE), offset: String(page * PAGE_SIZE) });
      if (search) q.set("search", search);
      return api<{ users: AdminUser[]; total: number }>(`/admin/users?${q}`);
    },
    placeholderData: keepPreviousData,
  });
}

export function useSetRole() {
  const qc = useQueryClient();
  return useMutation({
    // The backend takes the role as a query parameter on PATCH.
    mutationFn: ({ userId, role }: { userId: string; role: Role }) =>
      api(`/admin/users/${encodeURIComponent(userId)}/role?role=${role}`, { method: "PATCH" }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["admin"] });
    },
  });
}

export function useAdminAudit() {
  return useQuery({
    queryKey: ["admin", "audit"],
    queryFn: async () => (await api<{ logs: AuditEntry[] }>("/admin/audit-logs?limit=20")).logs,
  });
}

const ACTION_LABELS: Record<string, string> = {
  UPDATE_USER_ROLE: "Changed a role",
  IMPERSONATE_USER: "Signed in as a user",
};

export function auditSummary(e: AuditEntry): string {
  const label = ACTION_LABELS[e.action] ?? e.action.replace(/_/g, " ").toLowerCase();
  const d = e.details ?? {};
  if (e.action === "UPDATE_USER_ROLE" && d.old_role && d.new_role) return `${label}: ${String(d.old_role)} → ${String(d.new_role)}`;
  return label;
}
