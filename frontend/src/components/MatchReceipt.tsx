import { Check } from "lucide-react";
import { readableReason, type Job } from "../lib/jobs";
import { cx } from "./ui";

/**
 * Why a job matches, in the same few words and the same layout everywhere it appears.
 * The reasons are the scorer's own; nothing here is rewritten or added.
 */
export function MatchReceipt({ job, max = 4, className }: { job: Pick<Job, "match_reasons">; max?: number; className?: string }) {
  const reasons = (job.match_reasons ?? []).filter((r) => r.trim()).slice(0, max);
  if (!reasons.length) return null;
  return (
    <ul className={cx("flex flex-col gap-1.5", className)}>
      {reasons.map((r) => (
        <li key={r} className="flex gap-2">
          <Check className="mt-0.5 size-4 flex-none text-accent" strokeWidth={2.25} aria-hidden />
          {readableReason(r)}
        </li>
      ))}
    </ul>
  );
}
