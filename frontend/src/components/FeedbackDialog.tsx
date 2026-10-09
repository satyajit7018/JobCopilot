import { useEffect, useRef, useState } from "react";
import { Check, X } from "lucide-react";
import { useSendFeedback } from "../lib/support";
import { Alert, Button, Textarea } from "./ui";

/** "Send feedback": a short message to the team, read on the Admin page. */
export function FeedbackDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
  const ref = useRef<HTMLDialogElement>(null);
  const send = useSendFeedback();
  const [text, setText] = useState("");

  useEffect(() => {
    const d = ref.current;
    if (!d) return;
    if (open && !d.open) {
      send.reset();
      d.showModal();
    }
    if (!open && d.open) d.close();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  return (
    <dialog
      ref={ref}
      onClose={onClose}
      aria-labelledby="feedback-title"
      className="m-auto w-[min(32rem,calc(100vw-2rem))] rounded-xl border border-line bg-surface p-0 text-ink shadow-pop backdrop:bg-ink/30"
    >
      <div className="flex items-center justify-between border-b border-line px-5 py-3">
        <h2 id="feedback-title" className="font-semibold">
          Send feedback
        </h2>
        <button type="button" onClick={onClose} className="grid size-8 place-items-center rounded-md text-ink-3 hover:bg-subtle hover:text-ink">
          <X className="size-4" aria-hidden />
          <span className="sr-only">Close</span>
        </button>
      </div>
      {send.isSuccess ? (
        <div className="flex flex-col items-start gap-3 p-5">
          <p className="flex items-center gap-1.5 font-medium text-ok" role="status">
            <Check className="size-4" aria-hidden />
            Thanks, we got it.
          </p>
          <p className="text-ink-2">We read every message. If you asked something, we'll reply to your account email.</p>
          <Button onClick={onClose}>Close</Button>
        </div>
      ) : (
        <form
          className="flex flex-col gap-3 p-5"
          onSubmit={(e) => {
            e.preventDefault();
            if (text.trim().length >= 3) send.mutate(text.trim(), { onSuccess: () => setText("") });
          }}
        >
          <Textarea
            label="What's working, what isn't, or what you'd like to see?"
            name="feedback"
            rows={5}
            maxLength={4000}
            value={text}
            onChange={(e) => setText(e.target.value)}
          />
          {send.error && <Alert>Couldn't send: {send.error.message}</Alert>}
          <div className="flex justify-end gap-2">
            <Button variant="ghost" onClick={onClose}>
              Cancel
            </Button>
            <Button type="submit" variant="primary" loading={send.isPending} disabled={text.trim().length < 3}>
              Send
            </Button>
          </div>
        </form>
      )}
    </dialog>
  );
}
