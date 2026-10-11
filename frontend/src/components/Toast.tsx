// Short confirmations that float above the page instead of pushing content down.
import { useEffect, useSyncExternalStore } from "react";

interface ToastState {
  id: number;
  message: string;
  action?: { label: string; onClick: () => void };
}

let current: ToastState | null = null;
let nextId = 1;
const listeners = new Set<() => void>();
const emit = () => listeners.forEach((l) => l());

/** Show a confirmation ("Saved"), optionally with one action ("Undo"). Replaces any toast already showing. */
export function toast(message: string, action?: ToastState["action"]) {
  current = { id: nextId++, message, action };
  emit();
}

function dismiss(id?: number) {
  if (id !== undefined && current?.id !== id) return;
  current = null;
  emit();
}

const VISIBLE_MS = 4000;

/** Mounted once, in the app shell. */
export function Toaster() {
  const state = useSyncExternalStore(
    (l) => {
      listeners.add(l);
      return () => listeners.delete(l);
    },
    () => current,
  );

  useEffect(() => {
    if (!state) return;
    const t = setTimeout(() => dismiss(state.id), VISIBLE_MS);
    return () => clearTimeout(t);
  }, [state]);

  return (
    <div className="pointer-events-none fixed inset-x-0 bottom-20 z-40 flex justify-center px-4 md:bottom-6" role="status" aria-live="polite">
      {state && (
        <div key={state.id} className="toast-in pointer-events-auto flex max-w-full items-center gap-3 rounded-full bg-ink py-2.5 pr-2.5 pl-4 text-canvas shadow-pop">
          <span className="truncate">{state.message}</span>
          {state.action ? (
            <button
              type="button"
              className="rounded-full px-2.5 py-0.5 font-semibold underline underline-offset-2"
              onClick={() => {
                state.action?.onClick();
                dismiss(state.id);
              }}
            >
              {state.action.label}
            </button>
          ) : (
            <span className="w-1.5" />
          )}
        </div>
      )}
    </div>
  );
}
