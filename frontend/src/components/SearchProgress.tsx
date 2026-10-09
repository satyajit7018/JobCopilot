import { useEffect, useState } from "react";

/** What the first search is doing, by elapsed time (it takes ~20s; the steps overlap on the server). */
export const SEARCH_STAGES: { after: number; text: string }[] = [
  { after: 0, text: "Checking career pages at about 30 tech companies" },
  { after: 6_000, text: "Looking through startup job boards" },
  { after: 12_000, text: "Scoring each job against your resume" },
  { after: 20_000, text: "Saving your best matches" },
  { after: 35_000, text: "Still working. Some job sites are slow today" },
];

export function searchStage(elapsedMs: number): string {
  return [...SEARCH_STAGES].reverse().find((s) => elapsedMs >= s.after)!.text;
}

export function SearchProgress() {
  const [started] = useState(() => Date.now());
  const [now, setNow] = useState(started);
  useEffect(() => {
    const t = window.setInterval(() => setNow(Date.now()), 500);
    return () => window.clearInterval(t);
  }, []);
  const elapsed = now - started;
  // An estimate, not real progress: eases toward 95% over about 25 seconds.
  const pct = Math.min(95, Math.round(95 * (1 - Math.exp(-elapsed / 10_000))));

  return (
    <div className="mt-5" role="status" aria-live="polite">
      <div className="h-1.5 overflow-hidden rounded-full bg-subtle" aria-hidden>
        <div className="h-full rounded-full bg-accent transition-[width] duration-500" style={{ width: `${pct}%` }} />
      </div>
      <p className="mt-2 text-sm text-ink-2">{searchStage(elapsed)}…</p>
    </div>
  );
}

