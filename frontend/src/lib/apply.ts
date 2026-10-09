// Review & apply: tailored materials, consent for real submissions, the apply
// task, and questions the bot held for the user.
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "./api";

export type SubmissionMode = "DRY_RUN" | "LIVE";

export type ResumeWording = "ai" | "original";

/** One experience bullet the AI reworded for this job, next to the user's own words. */
export interface ResumeChange {
  role: string;
  company: string;
  before: string;
  after: string;
}

export interface TailorResult {
  cover_letter: string;
  pdf_hash: string;
  resume_wording: ResumeWording;
  resume_changes: ResumeChange[];
}

export interface ApplyResult {
  status?: string;
  message?: string;
  mode?: SubmissionMode;
  submitted?: boolean;
  simulated?: boolean;
}

export interface TaskInfo {
  task_id: string;
  job_id: string;
  status: string;
  progress_percent: number;
  result: ApplyResult | null;
}

export interface HeldQuestion {
  event_id: string;
  job_id: string;
  company: string;
  role_title: string;
  question_text: string;
  input_type: string;
  options: string[];
  ai_suggested_draft: string;
  created_at?: string;
}

/** Drafts the cover letter (and a tailored resume on the server) for one job. */
export function useTailor(jobId: string) {
  return useMutation({
    mutationFn: () => api<TailorResult>(`/jobs/${encodeURIComponent(jobId)}/tailor`, { method: "POST" }),
  });
}

/** Picks the AI wording or the user's own for this job's resume; applying uses the pick. */
export function useSetResumeWording(jobId: string) {
  return useMutation({
    mutationFn: (choice: ResumeWording) =>
      api(`/jobs/${encodeURIComponent(jobId)}/resume-wording`, { method: "PUT", body: { choice } }).then(() => choice),
  });
}

// --- Consent for real submissions -------------------------------------------

interface ConsentStatus {
  consents: Record<string, { consented: boolean } | undefined>;
}

/** Whether the user has opted in to the bot submitting real applications. */
export function useLiveConsent() {
  return useQuery({
    queryKey: ["consent"],
    queryFn: () => api<ConsentStatus>("/compliance/consent"),
    select: (d) => d.consents.autonomous_submission?.consented === true,
  });
}

export function useSetLiveConsent() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (consented: boolean) =>
      api("/compliance/consent", { method: "POST", body: { consent_type: "autonomous_submission", consented } }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["consent"] }),
  });
}

// --- The apply task ---------------------------------------------------------

export function useStartApply(jobId: string) {
  return useMutation({
    mutationFn: ({ mode, key }: { mode: SubmissionMode; key: string }) =>
      api<{ task_id: string }>(`/jobs/apply-async/${encodeURIComponent(jobId)}?mode=${mode}`, {
        method: "POST",
        // One key per approval: a double click or a retried request can't apply twice.
        headers: { "Idempotency-Key": key },
      }),
  });
}

const DONE = new Set(["SUCCESS", "FAILED", "FAILURE", "DLQ", "REVOKED"]);

export type TaskPhase = "running" | "succeeded" | "failed";

export function taskPhase(task: Pick<TaskInfo, "status"> | undefined): TaskPhase {
  if (!task || !DONE.has(task.status)) return "running";
  return task.status === "SUCCESS" ? "succeeded" : "failed";
}

/** Polls an apply task until it finishes. */
export function useApplyTask(taskId: string | null) {
  const qc = useQueryClient();
  return useQuery({
    queryKey: ["task", taskId],
    enabled: Boolean(taskId),
    queryFn: async () => {
      const { task } = await api<{ task: TaskInfo }>(`/tasks/${encodeURIComponent(taskId!)}`);
      // The job's status changes when a run finishes; refresh the lists then.
      if (taskPhase(task) !== "running") void qc.invalidateQueries({ queryKey: ["jobs"] });
      return task;
    },
    refetchInterval: (q) => (taskPhase(q.state.data) === "running" ? 2000 : false),
  });
}

/**
 * Plain-language outcome of a finished run. The server reports any non-"success"
 * result as a failed task, so the runner's own status is checked first.
 */
export function outcome(task: TaskInfo): { tone: "ok" | "info" | "warn" | "danger"; title: string; detail: string } {
  const r = task.result ?? {};
  if (r.status === "hitl_required") {
    return { tone: "info", title: "Paused for your answer", detail: "The form asked something we couldn't answer. Answer it in Applications to continue." };
  }
  if (r.status === "needs_review") {
    return { tone: "warn", title: "Check this one yourself", detail: r.message ?? "We couldn't confirm the submission. Check the employer's site." };
  }
  if (taskPhase(task) === "failed") {
    return { tone: "danger", title: "The application didn't go through", detail: r.message ?? "Nothing was submitted. You can try again." };
  }
  if (r.submitted) {
    return { tone: "ok", title: "Application submitted", detail: "We'll track replies and let you know when something changes." };
  }
  return {
    tone: "info",
    title: "Practice run finished",
    detail: r.message ?? "Your materials were prepared and checked. Nothing was submitted.",
  };
}

// --- Questions held for the user --------------------------------------------

export function useHeldQuestions() {
  return useQuery({
    queryKey: ["hitl"],
    queryFn: async () => (await api<{ events: HeldQuestion[] }>("/hitl/pending")).events,
  });
}

export function useAnswerHeld() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (input: { event_id: string; user_answer: string; save_to_vault: boolean }) =>
      api<{ message: string; task_id: string | null }>("/hitl/resolve-held", { method: "POST", body: input }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["hitl"] });
      void qc.invalidateQueries({ queryKey: ["jobs"] });
    },
  });
}

/** A fresh idempotency key; falls back where crypto.randomUUID is missing (old browsers, http). */
export function newKey(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) return crypto.randomUUID();
  return `${Date.now().toString(36)}-${Math.random().toString(36).slice(2)}`;
}
