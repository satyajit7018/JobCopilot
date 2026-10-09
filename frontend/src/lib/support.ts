// Feedback from the app, and the admin list of it.
import { useMutation, useQuery } from "@tanstack/react-query";
import { api } from "./api";

export function useSendFeedback() {
  return useMutation({
    mutationFn: (message: string) =>
      api<{ feedback_id: string }>("/feedback", { method: "POST", body: { message, page: window.location.pathname } }),
  });
}

export interface FeedbackItem {
  feedback_id: string;
  user_id: string;
  email: string | null;
  message: string;
  page: string | null;
  created_at: string;
}

export function useAdminFeedback() {
  return useQuery({
    queryKey: ["admin", "feedback"],
    queryFn: async () => (await api<{ feedback: FeedbackItem[] }>("/admin/feedback?limit=50")).feedback,
  });
}
