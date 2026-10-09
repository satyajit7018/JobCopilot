import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "./api";
import { fromChosenSource, useSources } from "./profile";

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
  | "OFFER"
  | "DISMISSED"
  | "SAVED";

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
  DISMISSED: { label: "Not interested", tone: "neutral" },
  SAVED: { label: "Saved", tone: "accent" },
};

/** Applications board columns, in pipeline order. DISCOVERED jobs live on the Jobs page. */
export const BOARD_COLUMNS: { key: string; label: string; statuses: ApplicationStatus[] }[] = [
  { key: "progress", label: "In progress", statuses: ["QUEUED", "IN_PROGRESS", "HITL_REQUIRED", "NEEDS_REVIEW"] },
  { key: "applied", label: "Applied", statuses: ["SUBMITTED", "RESPONDED"] },
  { key: "interview", label: "Interviewing", statuses: ["INTERVIEW"] },
  { key: "offer", label: "Offer", statuses: ["OFFER"] },
  { key: "closed", label: "Closed", statuses: ["REJECTED"] },
];

/** A job still on the Jobs page: a new match, or one saved for later. */
export function isMatch(job: Job): boolean {
  return job.status === "DISCOVERED" || job.status === "SAVED";
}

/** On the Applications board (applied or further along). */
export function isTracked(job: Job): boolean {
  return BOARD_COLUMNS.some((c) => c.statuses.includes(job.status));
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

/**
 * Jobs with new matches from turned-off sources removed. Tracked applications
 * always stay, whatever site they came from.
 */
export function useVisibleJobs() {
  const query = useJobs();
  const sources = useSources();
  const visible = useMemo(
    () => query.data?.filter((j) => !isMatch(j) || fromChosenSource(j.platform, sources)),
    [query.data, sources],
  );
  return { ...query, data: visible, hiddenMatches: (query.data?.length ?? 0) - (visible?.length ?? 0) };
}

/** Moves a match between new, saved and hidden, updating the list right away. */
function useSetMatchStatus() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ jobId, status }: { jobId: string; status: ApplicationStatus }) =>
      api(`/jobs/${encodeURIComponent(jobId)}/status`, { method: "PATCH", body: { status } }),
    onMutate: async ({ jobId, status }) => {
      await qc.cancelQueries({ queryKey: ["jobs"] });
      const before = qc.getQueryData<Job[]>(["jobs"]);
      qc.setQueryData<Job[]>(["jobs"], (jobs) => jobs?.map((j) => (j.job_id === jobId ? { ...j, status } : j)));
      return { before };
    },
    onError: (_e, _v, ctx) => ctx?.before && qc.setQueryData(["jobs"], ctx.before),
    onSettled: () => qc.invalidateQueries({ queryKey: ["jobs"] }),
  });
}

/** "Not interested": hides a match for good (searches won't bring it back). Undo restores it. */
export function useSetMatchHidden() {
  const m = useSetMatchStatus();
  return {
    ...m,
    mutate: ({ jobId, hidden }: { jobId: string; hidden: boolean }) => m.mutate({ jobId, status: hidden ? "DISMISSED" : "DISCOVERED" }),
  };
}

/** "Save for later": bookmarks a match. */
export function useSetMatchSaved() {
  const m = useSetMatchStatus();
  return {
    ...m,
    mutate: ({ jobId, saved }: { jobId: string; saved: boolean }) => m.mutate({ jobId, status: saved ? "SAVED" : "DISCOVERED" }),
  };
}

// --- Location filter -----------------------------------------------------------------

export type Region = "india" | "usa" | "europe" | "canada";

export const REGION_LABELS: Record<Region, string> = {
  india: "India",
  usa: "United States",
  europe: "UK & Europe",
  canada: "Canada",
};

// Word matches, like the backend scorer ("us" must not match "Australia").
const REGION_PATTERNS: Record<Region, RegExp> = {
  india: /\b(india|bangalore|bengaluru|hyderabad|pune|delhi|ncr|gurgaon|gurugram|noida|mumbai|chennai|kolkata|ahmedabad|jaipur|kochi)\b/i,
  usa: /\b(usa|u\.s\.a?\.?|united states|us|amer|north america|new york|nyc|san francisco|sf|seattle|austin|boston|chicago|los angeles|denver|california|washington|texas)\b/i,
  europe: /\b(uk|united kingdom|london|europe|emea|eu|germany|berlin|munich|amsterdam|netherlands|paris|france|dublin|ireland|spain|madrid|lisbon|portugal|poland|warsaw|stockholm|sweden|zurich|switzerland)\b/i,
  canada: /\b(canada|toronto|vancouver|montreal)\b/i,
};

export function jobRegions(location: string | null | undefined): Region[] {
  if (!location) return [];
  return (Object.keys(REGION_PATTERNS) as Region[]).filter((r) => REGION_PATTERNS[r].test(location));
}

export function isRemote(location: string | null | undefined): boolean {
  return /\bremote\b/i.test(location ?? "");
}

// --- "New since your last visit" -------------------------------------------------------

/**
 * When the user last left this page (ms), read once on arrival; the current visit is
 * recorded on leaving, so "New" badges stay put while they look around.
 */
export function useLastVisit(page: string): number | null {
  const key = `jobcopilot_last_visit_${page}`;
  const [previous] = useState<number | null>(() => {
    try {
      const v = Number(localStorage.getItem(key));
      return Number.isFinite(v) && v > 0 ? v : null;
    } catch {
      return null;
    }
  });
  useEffect(
    () => () => {
      try {
        localStorage.setItem(key, String(Date.now()));
      } catch {
        // Storage blocked: badges just won't persist.
      }
    },
    [key],
  );
  return previous;
}

export function isNewSince(job: Job, since: number | null): boolean {
  if (since === null || !job.created_at) return false;
  const t = new Date(job.created_at).getTime();
  return Number.isFinite(t) && t > since;
}

/** When the user last left a page, without recording this visit (for counts elsewhere). */
export function readLastVisit(page: string): number | null {
  try {
    const v = Number(localStorage.getItem(`jobcopilot_last_visit_${page}`));
    return Number.isFinite(v) && v > 0 ? v : null;
  } catch {
    return null;
  }
}

/** "Find new jobs": checks for postings now (we also check every hour automatically). */
export function useFindNewJobs() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => api<{ status?: string; message?: string; matched_and_saved?: number }>("/discovery/run", { method: "POST" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["jobs"] }),
  });
}
