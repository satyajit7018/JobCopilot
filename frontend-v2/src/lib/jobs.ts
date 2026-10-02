import { useQuery } from "@tanstack/react-query";
import { api } from "./api";

// Mirrors backend/app/core/models.py ApplicationStatus.
export type ApplicationStatus =
  | "DISCOVERED"
  | "QUEUED"
  | "IN_PROGRESS"
  | "HITL_REQUIRED"
  | "SUBMITTED"
  | "NEEDS_REVIEW"
  | "RESPONDED"
  | "INTERVIEW"
  | "REJECTED"
  | "OFFER";

// Mirrors backend JobListing (fields the UI reads).
export interface Job {
  job_id: string;
  platform: string;
  company: string;
  title: string;
  location: string;
  url: string;
  description: string;
  salary_range: string | null;
  seniority_level: string | null;
  posted_date: string | null;
  match_score: number;
  match_reasons: string[];
  missing_skills: string[];
  status: ApplicationStatus;
  applied_at: string | null;
  created_at: string | null;
  interview_date: string | null;
  notes: string | null;
}

export function useJobs() {
  return useQuery({
    queryKey: ["jobs"],
    queryFn: async ({ signal }) => (await api<{ count: number; jobs: Job[] }>("/jobs", { signal })).jobs,
  });
}

export type Tone = "neutral" | "accent" | "ok" | "warn" | "info" | "danger";

export const STATUS_META: Record<ApplicationStatus, { label: string; tone: Tone }> = {
  DISCOVERED: { label: "New match", tone: "accent" },
  QUEUED: { label: "Queued", tone: "neutral" },
  IN_PROGRESS: { label: "Applying", tone: "neutral" },
  HITL_REQUIRED: { label: "Needs you", tone: "warn" },
  NEEDS_REVIEW: { label: "Needs review", tone: "warn" },
  SUBMITTED: { label: "Applied", tone: "neutral" },
  RESPONDED: { label: "Replied", tone: "info" },
  INTERVIEW: { label: "Interviewing", tone: "info" },
  OFFER: { label: "Offer", tone: "ok" },
  REJECTED: { label: "Closed", tone: "danger" },
};

/** Applications board columns, in pipeline order. DISCOVERED jobs live on the Jobs page. */
export const BOARD_COLUMNS: { key: string; label: string; statuses: ApplicationStatus[] }[] = [
  { key: "progress", label: "In progress", statuses: ["QUEUED", "IN_PROGRESS", "HITL_REQUIRED", "NEEDS_REVIEW"] },
  { key: "applied", label: "Applied", statuses: ["SUBMITTED", "RESPONDED"] },
  { key: "interview", label: "Interviewing", statuses: ["INTERVIEW"] },
  { key: "offer", label: "Offer", statuses: ["OFFER"] },
  { key: "closed", label: "Closed", statuses: ["REJECTED"] },
];

export function isMatch(job: Job): boolean {
  return job.status === "DISCOVERED";
}

/** Backend stores 0–1; tolerate legacy rows already stored as 0–100. */
export function scorePercent(score: number | null | undefined): number {
  if (!score || score < 0) return 0;
  return Math.min(100, Math.round(score <= 1 ? score * 100 : score));
}

export function scoreTone(pct: number): Tone {
  if (pct >= 80) return "ok";
  if (pct >= 60) return "warn";
  return "neutral";
}

/** One plain sentence explaining the score, preferring a concrete reason. */
export function matchSummary(job: Job): string | null {
  const reason = job.match_reasons?.find((r) => r.trim());
  const missing = job.missing_skills?.filter((s) => s.trim()) ?? [];
  if (reason && missing.length) return `${reason}. Missing: ${missing.slice(0, 2).join(", ")}`;
  if (reason) return reason;
  if (missing.length) return `Missing: ${missing.slice(0, 3).join(", ")}`;
  return null;
}

export function relativeTime(iso: string | null | undefined, now: Date = new Date()): string | null {
  if (!iso) return null;
  const then = new Date(iso);
  if (Number.isNaN(then.getTime())) return null;
  const mins = Math.round((now.getTime() - then.getTime()) / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.round(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.round(hours / 24);
  if (days < 30) return `${days}d ago`;
  return then.toLocaleDateString(undefined, { month: "short", day: "numeric" });
}
