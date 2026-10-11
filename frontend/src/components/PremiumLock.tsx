import type { ReactNode } from "react";
import { Link } from "react-router";
import { Check, Sparkles } from "lucide-react";
import { buttonClass, cx } from "./ui";

/** Shown in place of a Premium feature for Free users. */
export function PremiumLock({
  title,
  children,
  points,
  className,
}: {
  title: string;
  children?: ReactNode;
  /** Short benefits, when one box stands in for several Premium features. */
  points?: string[];
  className?: string;
}) {
  return (
    <div className={cx("flex flex-col items-start gap-3 rounded-lg bg-surface p-5", className)}>
      <span className="inline-flex items-center gap-1.5 rounded-full bg-accent-soft px-2.5 py-0.5 text-xs font-semibold text-accent-ink">
        <Sparkles className="size-3.5" aria-hidden />
        Premium
      </span>
      <div>
        <p className="font-semibold">{title}</p>
        {children && <div className="mt-1 text-ink-2">{children}</div>}
        {points && (
          <ul className="mt-1.5 flex flex-col gap-1 text-ink-2">
            {points.map((p) => (
              <li key={p} className="flex gap-2">
                <Check className="mt-0.5 size-4 flex-none text-accent" aria-hidden />
                {p}
              </li>
            ))}
          </ul>
        )}
      </div>
      <Link to="/plans" className={buttonClass("secondary", "sm")}>
        See Premium
      </Link>
    </div>
  );
}
