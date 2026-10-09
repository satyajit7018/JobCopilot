// One application: its apply attempts, recruiter emails, status changes,
// follow-up drafts and offer tools.
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, ApiError } from "./api";
import { useIsPremium } from "./billing";
import { STATUS_META, type ApplicationStatus, type Job, type Tone } from "./jobs";

export interface LedgerEntry {
  status: "INITIATED" | "IN_PROGRESS" | "SUBMITTED" | "FAILED" | "HITL_PAUSED" | "CANCELLED";
  attempt_count: number;
  last_error_message: string | null;
  confirmation_id: string | null;
  created_at: string;
  updated_at: string;
}

export type EmailIntent = "CONFIRMATION" | "INTERVIEW_INVITE" | "ASSESSMENT" | "REJECTION" | "FOLLOW_UP" | "OTHER";

export interface Email {
  message_id: string;
  sender: string;
  subject: string;
  body_text: string;
  received_at: string;
  associated_job_id: string | null;
  intent: EmailIntent;
  scheduling_links: string[];
}

export const INTENT_META: Record<EmailIntent, { label: string; tone: Tone }> = {
  CONFIRMATION: { label: "Confirmation", tone: "neutral" },
  INTERVIEW_INVITE: { label: "Interview invite", tone: "info" },
  ASSESSMENT: { label: "Assessment", tone: "info" },
  REJECTION: { label: "Rejection", tone: "danger" },
  FOLLOW_UP: { label: "Follow-up", tone: "neutral" },
  OTHER: { label: "Email", tone: "neutral" },
};

/** The apply record for a job, or null if the bot never ran it (404). */
export function useLedger(jobId: string) {
  return useQuery({
    queryKey: ["ledger", jobId],
    queryFn: async () => {
      try {
        return (await api<{ ledger: LedgerEntry }>(`/bot/ledger/${encodeURIComponent(jobId)}`)).ledger;
      } catch (err) {
        if (err instanceof ApiError && err.status === 404) return null;
        throw err;
      }
    },
  });
}

/** Recruiter emails we picked up. Inbox tracking is Premium, so Free accounts simply have none. */
export function useEmails() {
  const premium = useIsPremium();
  return useQuery({
    queryKey: ["emails", premium],
    queryFn: async () => (premium ? (await api<{ messages: Email[] }>("/email/messages")).messages : []),
  });
}

/** Statuses a user can set by hand, in pipeline order. */
export const MANUAL_STATUSES = (["SUBMITTED", "RESPONDED", "INTERVIEW", "OFFER", "REJECTED"] as const).map((value) => ({
  value: value as ApplicationStatus,
  label: STATUS_META[value].label,
}));

export function useSetStatus(jobId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (status: ApplicationStatus) =>
      api(`/jobs/${encodeURIComponent(jobId)}/status`, { method: "PATCH", body: { status } }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["jobs"] }),
  });
}

export function useSetInterviewDate(jobId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (interviewDate: string | null) =>
      api(`/jobs/${encodeURIComponent(jobId)}/interview`, { method: "PATCH", body: { interview_date: interviewDate } }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["jobs"] }),
  });
}

/** ISO date-time -> the local "YYYY-MM-DDTHH:mm" a datetime-local input expects ("" if unset or invalid). */
export function toLocalInput(iso: string | null | undefined): string {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

/** datetime-local value (local time) -> ISO string, or null if empty or invalid. */
export function fromLocalInput(value: string): string | null {
  if (!value) return null;
  const d = new Date(value);
  return Number.isNaN(d.getTime()) ? null : d.toISOString();
}

export function useFollowUpDraft(jobId: string) {
  return useMutation({
    mutationFn: (stageDays: number) =>
      api<{ followup: { subject: string; body: string } }>(
        `/email/followup/${encodeURIComponent(jobId)}?stage_days=${Math.max(1, Math.round(stageDays))}`,
        { method: "POST" },
      ),
  });
}

// --- Offers -----------------------------------------------------------------

export interface OfferEvaluation {
  total_annual_comp_lpa: number;
  market_percentile_band: string;
  rating: string;
  benchmark_p50: number;
  benchmark_p75: number;
  negotiation_guidance: string;
}

export function useEvaluateOffer() {
  return useMutation({
    mutationFn: (input: { base_salary_lpa: number; bonus_lpa: number; equity_annual_lpa: number; role_title: string }) =>
      api<{ evaluation: OfferEvaluation }>("/negotiation/evaluate", { method: "POST", body: input }),
  });
}

export function useCounterOffer() {
  return useMutation({
    mutationFn: (input: { candidate_name?: string; company_name: string; role_title: string; offered_tc: string; desired_tc: string }) =>
      api<{ counter_offer_script: string }>("/negotiation/counter-offer", { method: "POST", body: input }),
  });
}

// --- Timeline ---------------------------------------------------------------

export interface TimelineEvent {
  key: string;
  at: string;
  title: string;
  detail?: string;
  tone: Tone;
}

const valid = (iso: string | null | undefined): iso is string => Boolean(iso) && !Number.isNaN(new Date(iso!).getTime());

/** Everything known about one application, newest first. */
export function buildTimeline(job: Job, ledger: LedgerEntry | null, emails: Email[]): TimelineEvent[] {
  const events: TimelineEvent[] = [];

  if (valid(job.created_at)) {
    events.push({ key: "found", at: job.created_at, title: "Found this job", detail: job.platform || undefined, tone: "neutral" });
  }

  if (ledger) {
    if (ledger.status === "SUBMITTED") {
      events.push({
        key: "ledger",
        at: ledger.updated_at,
        title: "Application submitted",
        detail: ledger.confirmation_id ? `Confirmation ${ledger.confirmation_id}` : undefined,
        tone: "ok",
      });
    } else if (ledger.status === "FAILED") {
      events.push({
        key: "ledger",
        at: ledger.updated_at,
        title: ledger.attempt_count > 1 ? `Application failed after ${ledger.attempt_count} tries` : "Application failed",
        detail: ledger.last_error_message ?? undefined,
        tone: "danger",
      });
    } else if (ledger.status === "HITL_PAUSED") {
      events.push({ key: "ledger", at: ledger.updated_at, title: "Paused for your answer", tone: "warn" });
    } else if (ledger.status === "IN_PROGRESS" || ledger.status === "INITIATED") {
      events.push({ key: "ledger", at: ledger.updated_at, title: "Applying now", tone: "info" });
    }
  }

  // The job record's applied date covers submissions made outside the bot (or before the ledger existed).
  if (valid(job.applied_at) && ledger?.status !== "SUBMITTED") {
    events.push({ key: "applied", at: job.applied_at, title: "Applied", tone: "ok" });
  }

  for (const e of emails) {
    if (e.associated_job_id !== job.job_id || !valid(e.received_at)) continue;
    events.push({
      key: `email-${e.message_id}`,
      at: e.received_at,
      title: INTENT_META[e.intent]?.label ?? "Email",
      detail: `${e.subject} · ${e.sender}`,
      tone: INTENT_META[e.intent]?.tone ?? "neutral",
    });
  }

  if (valid(job.interview_date)) {
    const upcoming = new Date(job.interview_date).getTime() > Date.now();
    events.push({ key: "interview", at: job.interview_date, title: upcoming ? "Interview scheduled" : "Interview", tone: "info" });
  }

  return events.sort((a, b) => new Date(b.at).getTime() - new Date(a.at).getTime());
}

/** Whole days since the user applied, or null. Drives the follow-up suggestion. */
export function daysSince(iso: string | null | undefined, now: Date = new Date()): number | null {
  if (!valid(iso)) return null;
  return Math.floor((now.getTime() - new Date(iso).getTime()) / 86_400_000);
}

/** Parses "28", "28 LPA" or "28.5" into a number of LPA; null when it isn't a number. */
export function parseLpa(input: string): number | null {
  const m = input.replace(/,/g, "").match(/\d+(\.\d+)?/);
  return m ? Number(m[0]) : null;
}
