// Application answers: what the app may put on an employer's form, edited on Profile → Application answers.
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "./api";
import { usePublicConfig } from "./auth";

export const PREFER_NOT_TO_SAY = "Prefer not to say";

/** A fact that lives in Profile. Shown here, edited there. `value` is null until the user saves it. */
export interface ProfileFact {
  key: string;
  label: string;
  value: string | null;
}

/** A question most forms ask. Personal ones are optional and default to "Prefer not to say". */
export interface CommonQuestion {
  key: string;
  question: string;
  kind: "text" | "personal";
  options?: string[];
  id: string | null;
  answer: string | null;
  optional: boolean;
  confirmed_at: string | null;
}

/** An answer the user gave to a form question. `for_job` is set when it's about one company. */
export interface SavedAnswer {
  id: string;
  question: string;
  answer: string;
  for_job: { job_id: string; company: string; title: string } | null;
  wordings: string[];
  confirmed_at: string | null;
  last_used_at: string | null;
}

export interface ApplicationAnswers {
  profile: ProfileFact[];
  common: CommonQuestion[];
  saved: SavedAnswer[];
}

/** The answers page is part of prepared applications, hidden until the server turns it on. */
export function usePreparedApplications(): boolean {
  return usePublicConfig().data?.prepared_applications === true;
}

export function useApplicationAnswers() {
  return useQuery({ queryKey: ["answers"], queryFn: () => api<ApplicationAnswers>("/answers") });
}

function useAnswersMutation<V>(fn: (v: V) => Promise<unknown>) {
  const qc = useQueryClient();
  return useMutation({ mutationFn: fn, onSuccess: () => qc.invalidateQueries({ queryKey: ["answers"] }) });
}

export function useSaveCommonAnswer() {
  return useAnswersMutation((q: { key: string; question: string; answer: string }) => api("/answers", { method: "PUT", body: q }));
}

export function useEditAnswer() {
  return useAnswersMutation(({ id, answer }: { id: string; answer: string }) =>
    api(`/answers/${encodeURIComponent(id)}`, { method: "PATCH", body: { answer } }),
  );
}

export function useDeleteAnswer() {
  return useAnswersMutation((id: string) => api(`/answers/${encodeURIComponent(id)}`, { method: "DELETE" }));
}

