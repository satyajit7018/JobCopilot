import type { ReactNode } from "react";
import { Link } from "react-router";
import { Sparkles } from "lucide-react";
import { buttonClass, cx } from "./ui";

/** Shown in place of a Premium feature for Free users. */
export function PremiumLock({ title, children, className }: { title: string; children: ReactNode; className?: string }) {
  return (
    <div className={cx("flex flex-col items-start gap-3 rounded-lg border border-accent/30 bg-accent-soft/40 p-4", className)}>
      <span className="inline-flex items-center gap-1.5 rounded-full bg-accent-soft px-2.5 py-0.5 text-xs font-semibold text-accent-ink">
        <Sparkles className="size-3.5" aria-hidden />
        Premium
      </span>
      <div>
        <p className="font-semibold">{title}</p>
        <div className="mt-1 text-ink-2">{children}</div>
      </div>
      <Link to="/plans" className={buttonClass("primary", "sm")}>
        See Premium
      </Link>
    </div>
  );
}
