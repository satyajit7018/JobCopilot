// Sends web-app errors to the backend (/api/client-errors), which logs them and forwards
// them to Sentry. Capped and de-duplicated so a crash loop can't flood the server.

const MAX_REPORTS_PER_PAGE_LOAD = 5;
const sent = new Set<string>();

function describe(error: unknown): { message: string; stack?: string } {
  if (error instanceof Error) return { message: `${error.name}: ${error.message}`.slice(0, 1000), stack: error.stack?.slice(0, 8000) };
  return { message: String(error).slice(0, 1000) };
}

export function reportError(error: unknown) {
  const { message, stack } = describe(error);
  if (sent.has(message) || sent.size >= MAX_REPORTS_PER_PAGE_LOAD) return;
  sent.add(message);
  try {
    void fetch("/api/client-errors", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message, stack, url: window.location.pathname, release: import.meta.env.MODE }),
      keepalive: true,
    }).catch(() => {});
  } catch {
    // Reporting must never cause another error.
  }
}

/** Catches errors nothing else handled (event handlers, promises). */
export function installGlobalErrorReporting() {
  window.addEventListener("error", (e) => reportError(e.error ?? e.message));
  window.addEventListener("unhandledrejection", (e) => reportError(e.reason));
}
