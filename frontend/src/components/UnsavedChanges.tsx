import { useEffect, useRef } from "react";
import { useBlocker } from "react-router";
import { Button } from "./ui";

/** Asks before leaving a page with edits that haven't been saved (links, Back, closing the tab). */
export function UnsavedChanges({ when, onSave, saving }: { when: boolean; onSave?: () => void; saving?: boolean }) {
  const blocker = useBlocker(when);
  const ref = useRef<HTMLDialogElement>(null);
  const blocked = blocker.state === "blocked";

  // Closing the tab or reloading: the browser shows its own "Leave site?" prompt.
  useEffect(() => {
    if (!when) return;
    const warn = (e: BeforeUnloadEvent) => e.preventDefault();
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [when]);

  useEffect(() => {
    const d = ref.current;
    if (!d) return;
    if (blocked && !d.open) d.showModal();
    if (!blocked && d.open) d.close();
  }, [blocked]);

  // Saved while the question was open: nothing left to lose, so carry on to where they were going.
  useEffect(() => {
    if (blocked && !when) blocker.proceed?.();
  }, [blocked, when, blocker]);

  return (
    <dialog
      ref={ref}
      onClose={() => blocker.reset?.()}
      aria-labelledby="unsaved-title"
      className="m-auto w-[min(26rem,calc(100vw-2rem))] rounded-xl bg-surface p-5 text-ink shadow-pop backdrop:bg-scrim"
    >
      <h2 id="unsaved-title" className="font-semibold">
        Leave without saving?
      </h2>
      <p className="mt-1 text-ink-2">Your changes on this page haven't been saved.</p>
      <div className="mt-4 flex flex-wrap justify-end gap-2">
        <Button variant="ghost" onClick={() => blocker.proceed?.()}>
          Leave
        </Button>
        {onSave ? (
          <>
            <Button onClick={() => blocker.reset?.()}>Keep editing</Button>
            <Button variant="primary" loading={saving} onClick={onSave}>
              Save and leave
            </Button>
          </>
        ) : (
          <Button variant="primary" onClick={() => blocker.reset?.()}>
            Keep editing
          </Button>
        )}
      </div>
    </dialog>
  );
}
