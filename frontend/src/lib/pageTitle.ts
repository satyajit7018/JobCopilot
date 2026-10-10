import { useEffect } from "react";

const APP = "JobCopilot";

/** Names the browser tab after the page ("Jobs · JobCopilot"), so several open tabs can be told apart. */
export function usePageTitle(title: string | null | undefined) {
  useEffect(() => {
    document.title = title ? `${title} · ${APP}` : APP;
    return () => {
      document.title = APP;
    };
  }, [title]);
}
