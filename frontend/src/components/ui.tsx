// Core components. Every screen is built from these; no one-off styling in pages.
import { clsx } from "clsx";
import {
  forwardRef,
  useId,
  useState,
  type ButtonHTMLAttributes,
  type CSSProperties,
  type HTMLAttributes,
  type InputHTMLAttributes,
  type ReactNode,
  type SelectHTMLAttributes,
  type TextareaHTMLAttributes,
} from "react";
import { Check, Copy, LoaderCircle } from "lucide-react";
import type { Tone } from "../lib/jobs";

export { clsx as cx };

type ButtonVariant = "primary" | "secondary" | "ghost" | "danger";
type ButtonSize = "sm" | "md" | "lg";

const buttonBase =
  "inline-flex items-center justify-center gap-1.5 rounded-full border border-transparent font-semibold whitespace-nowrap transition duration-100 ease-calm active:scale-[0.97] motion-reduce:active:scale-100 disabled:pointer-events-none disabled:opacity-50";
const buttonVariants: Record<ButtonVariant, string> = {
  // At most one of these per screen: the main thing to do.
  primary: "bg-accent text-on-solid hover:bg-accent-hover",
  // "Tinted": the second action.
  secondary: "bg-accent-soft text-accent-ink hover:bg-accent-soft/70",
  ghost: "bg-transparent text-ink-2 hover:bg-subtle hover:text-ink",
  // Only for the final step of an irreversible action.
  danger: "bg-danger text-on-solid hover:opacity-90",
};
const buttonSizes: Record<ButtonSize, string> = {
  sm: "h-8 px-3.5 text-sm",
  md: "h-10 px-4.5 text-sm",
  lg: "h-12 px-6 text-base",
};

export function buttonClass(variant: ButtonVariant = "secondary", size: ButtonSize = "md", extra?: string) {
  return clsx(buttonBase, buttonVariants[variant], buttonSizes[size], extra);
}

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
  loading?: boolean;
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  { variant = "secondary", size = "md", loading, className, children, disabled, type = "button", ...rest },
  ref,
) {
  return (
    <button
      ref={ref}
      type={type}
      className={buttonClass(variant, size, className)}
      disabled={disabled || loading}
      aria-busy={loading || undefined}
      {...rest}
    >
      {loading && <LoaderCircle className="size-4 animate-spin" aria-hidden />}
      {children}
    </button>
  );
});

const toneClass: Record<Tone, string> = {
  neutral: "bg-subtle text-ink-2",
  accent: "bg-accent-soft text-accent-ink",
  ok: "bg-ok-soft text-ok",
  warn: "bg-warn-soft text-warn",
  info: "bg-accent-soft text-accent-ink",
  danger: "bg-danger-soft text-danger",
};

export const toneText: Record<Tone, string> = {
  neutral: "text-ink-2",
  accent: "text-accent",
  ok: "text-ok",
  warn: "text-warn",
  info: "text-accent",
  danger: "text-danger",
};

export function Badge({ tone = "neutral", children, className }: { tone?: Tone; children: ReactNode; className?: string }) {
  return (
    <span className={clsx("inline-flex h-5.5 items-center gap-1 rounded-full px-2 text-xs font-medium", toneClass[tone], className)}>
      {children}
    </span>
  );
}

/** For cards you can click: they rise a little under the pointer. */
export const lift = "transition duration-150 ease-calm hover:shadow-pop active:scale-[0.99] motion-reduce:active:scale-100";

export function Card({ className, children }: { className?: string; children: ReactNode }) {
  return <div className={clsx("rounded-lg bg-surface", className)}>{children}</div>;
}

interface FieldProps extends InputHTMLAttributes<HTMLInputElement> {
  label: string;
  hint?: string;
  error?: string | null;
}

export const Field = forwardRef<HTMLInputElement, FieldProps>(function Field({ label, hint, error, id, className, ...rest }, ref) {
  const inputId = id ?? rest.name;
  const describedBy = error ? `${inputId}-error` : hint ? `${inputId}-hint` : undefined;
  return (
    <div className={className}>
      <label htmlFor={inputId} className="mb-1.5 block font-medium">
        {label}
      </label>
      <input
        ref={ref}
        id={inputId}
        aria-invalid={error ? true : undefined}
        aria-describedby={describedBy}
        className={clsx(controlClass, "h-11", error ? "border-danger" : "border-transparent")}
        {...rest}
      />
      <FieldNote id={inputId} hint={hint} error={error} />
    </div>
  );
});

// Fields are a soft grey well with no outline until focused.
const controlClass =
  "w-full rounded-md border bg-subtle px-3.5 text-sm text-ink placeholder:text-ink-3 focus:border-accent focus:bg-surface focus:outline-none focus:ring-3 focus:ring-accent-soft";

function FieldNote({ id, hint, error }: { id?: string; hint?: string; error?: string | null }) {
  if (error)
    return (
      <p id={`${id}-error`} className="mt-1.5 text-xs text-danger">
        {error}
      </p>
    );
  if (hint)
    return (
      <p id={`${id}-hint`} className="mt-1.5 text-xs text-ink-3">
        {hint}
      </p>
    );
  return null;
}

interface SelectProps extends SelectHTMLAttributes<HTMLSelectElement> {
  label: string;
  hint?: string;
  options: { value: string | number; label: string }[];
}

export function Select({ label, hint, options, id, className, ...rest }: SelectProps) {
  const auto = useId();
  const selectId = id ?? rest.name ?? auto;
  return (
    <div className={className}>
      <label htmlFor={selectId} className="mb-1.5 block font-medium">
        {label}
      </label>
      <select
        id={selectId}
        aria-describedby={hint ? `${selectId}-hint` : undefined}
        className={clsx(controlClass, "h-11 border-transparent")}
        {...rest}
      >
        {options.map((o) => (
          <option key={o.value} value={o.value}>
            {o.label}
          </option>
        ))}
      </select>
      <FieldNote id={selectId} hint={hint} />
    </div>
  );
}

interface TextareaProps extends TextareaHTMLAttributes<HTMLTextAreaElement> {
  label: string;
  hint?: string;
}

export function Textarea({ label, hint, id, className, rows = 4, ...rest }: TextareaProps) {
  const auto = useId();
  const areaId = id ?? rest.name ?? auto;
  return (
    <div className={className}>
      <label htmlFor={areaId} className="mb-1.5 block font-medium">
        {label}
      </label>
      <textarea
        id={areaId}
        rows={rows}
        aria-describedby={hint ? `${areaId}-hint` : undefined}
        className={clsx(controlClass, "border-transparent py-2.5 leading-relaxed")}
        {...rest}
      />
      <FieldNote id={areaId} hint={hint} />
    </div>
  );
}

/** Single-choice chips (a styled radio group). */
export function ChoiceChips<T extends string>({
  label,
  hint,
  value,
  options,
  onChange,
}: {
  label: string;
  hint?: string;
  value: T;
  options: { value: T; label: string }[];
  onChange: (value: T) => void;
}) {
  const name = useId();
  return (
    <fieldset>
      <legend className="mb-1.5 font-medium">{label}</legend>
      <div className="flex flex-wrap gap-2">
        {options.map((o) => {
          const on = o.value === value;
          return (
            <label
              key={o.value}
              className={clsx(
                "inline-flex h-8 cursor-pointer items-center gap-1 rounded-full border px-3 text-sm font-medium has-focus-visible:ring-3 has-focus-visible:ring-accent-soft",
                on ? "border-transparent bg-accent-soft text-accent-ink" : "border-transparent bg-subtle text-ink-2 hover:text-ink",
              )}
            >
              <input type="radio" name={name} value={o.value} checked={on} onChange={() => onChange(o.value)} className="sr-only" />
              {on && <Check className="size-3.5" aria-hidden />}
              {o.label}
            </label>
          );
        })}
      </div>
      {hint && <p className="mt-1.5 text-xs text-ink-3">{hint}</p>}
    </fieldset>
  );
}

/** A checkbox with a title and a supporting line, used for on/off settings. */
export function CheckRow({
  checked,
  onChange,
  title,
  detail,
  disabled,
}: {
  checked: boolean;
  onChange: (checked: boolean) => void;
  title: string;
  detail?: string;
  disabled?: boolean;
}) {
  return (
    <label
      className={clsx(
        "flex cursor-pointer items-start gap-3 rounded-md border px-3.5 py-3 has-focus-visible:ring-3 has-focus-visible:ring-accent-soft",
        checked ? "border-transparent bg-accent-soft" : "border-transparent bg-subtle hover:bg-subtle/70",
        disabled && "pointer-events-none opacity-60",
      )}
    >
      <input type="checkbox" checked={checked} onChange={(e) => onChange(e.target.checked)} disabled={disabled} className="mt-0.5 size-4 flex-none accent-accent" />
      <span>
        <span className="block font-medium">{title}</span>
        {detail && <span className="block text-ink-2">{detail}</span>}
      </span>
    </label>
  );
}

export function Spinner({ label = "Loading" }: { label?: string }) {
  return (
    <div role="status" className="flex items-center justify-center gap-2 py-16 text-ink-3">
      <LoaderCircle className="size-5 animate-spin" aria-hidden />
      <span>{label}…</span>
    </div>
  );
}

/** Grey rows shaped like a list while it loads, so the page doesn't jump when the data arrives. */
export function SkeletonRows({ rows = 5, label = "Loading", avatar = true }: { rows?: number; label?: string; avatar?: boolean }) {
  return (
    <div role="status" className="overflow-hidden rounded-lg bg-surface">
      <span className="sr-only">{label}…</span>
      <ul aria-hidden className="animate-pulse motion-reduce:animate-none">
        {Array.from({ length: rows }, (_, i) => (
          <li key={i} className="flex items-center gap-3 border-b border-line px-4 py-4 last:border-b-0 sm:gap-4 sm:px-5">
            {avatar && <span className="size-10 flex-none rounded-[22%] bg-subtle" />}
            <span className="flex min-w-0 flex-1 flex-col gap-2">
              <span className="h-3.5 w-2/5 rounded bg-subtle" />
              <span className="h-3 w-3/5 rounded bg-subtle" />
            </span>
            <span className="size-7 flex-none rounded-full bg-subtle" />
          </li>
        ))}
      </ul>
    </div>
  );
}

export function EmptyState({
  icon,
  title,
  children,
  action,
}: {
  icon: ReactNode;
  title: string;
  children?: ReactNode;
  action?: ReactNode;
}) {
  return (
    <div className="flex flex-col items-center px-6 py-14 text-center">
      <div className="mb-3 text-accent [&>svg]:size-7" aria-hidden>
        {icon}
      </div>
      <h3 className="text-base font-semibold">{title}</h3>
      {children && <p className="mt-1 max-w-sm text-ink-2">{children}</p>}
      {action && <div className="mt-5">{action}</div>}
    </div>
  );
}

export function Alert({ tone = "danger", children }: { tone?: Tone; children: ReactNode }) {
  return (
    <div role="alert" className={clsx("rounded-md px-3.5 py-2.5 text-sm", toneClass[tone])}>
      {children}
    </div>
  );
}

const markSizes = { sm: "size-8 text-xs", md: "size-10 text-sm", lg: "size-14 text-lg" };

/**
 * The company's logo on a white plate, or its initial on grey when we don't have one. Logos
 * come from our own server (which looks them up once and keeps them), so no other site sees
 * what you view.
 */
export function CompanyMark({ name, size = "md" }: { name: string; size?: keyof typeof markSizes }) {
  return <CompanyMarkImage key={name} name={name} size={size} />;
}

function CompanyMarkImage({ name, size }: { name: string; size: keyof typeof markSizes }) {
  const [logo, setLogo] = useState<"waiting" | "shown" | "none">("waiting");
  const clean = name.trim();
  return (
    <div
      aria-hidden
      className={clsx("relative grid flex-none place-items-center overflow-hidden rounded-[22%] bg-subtle font-semibold text-ink-2", markSizes[size])}
    >
      {clean[0]?.toUpperCase() ?? "?"}
      {clean && logo !== "none" && (
        <img
          src={`/api/company-logo?name=${encodeURIComponent(clean)}`}
          alt=""
          loading="lazy"
          decoding="async"
          onLoad={() => setLogo("shown")}
          onError={() => setLogo("none")}
          className={clsx("absolute inset-0 size-full bg-white object-contain p-1", logo !== "shown" && "opacity-0")}
        />
      )}
    </div>
  );
}

const ringSizes = {
  sm: { box: "size-7", r: 11, stroke: 4, number: "" },
  md: { box: "size-18", r: 30, stroke: 8, number: "text-lg" },
  lg: { box: "size-24", r: 41, stroke: 10, number: "text-xl" },
};

/**
 * The match score as a ring that fills clockwise from the top: green from 80, amber from 60,
 * grey below. The app's signature, drawn the same way everywhere. The small size sits in
 * list rows with the number beside it; the larger ones carry the number inside.
 * `draw` plays the fill-in once (for a match that's new to the user).
 */
export function ScoreRing({ pct, size = "md", draw, className }: { pct: number; size?: keyof typeof ringSizes; draw?: boolean; className?: string }) {
  const { box, r, stroke, number } = ringSizes[size];
  const view = (r + stroke) * 2;
  const around = 2 * Math.PI * r;
  const tone = pct >= 80 ? "ok" : pct >= 60 ? "warn" : "neutral";
  const offset = around * (1 - Math.max(0, Math.min(100, pct)) / 100);
  const ring = (
    <span className={clsx("relative grid flex-none place-items-center", box)}>
      <svg viewBox={`0 0 ${view} ${view}`} className="absolute inset-0 size-full -rotate-90" aria-hidden>
        <circle cx={view / 2} cy={view / 2} r={r} fill="none" strokeWidth={stroke} className="stroke-subtle" />
        <circle
          cx={view / 2}
          cy={view / 2}
          r={r}
          fill="none"
          stroke="currentColor"
          strokeWidth={stroke}
          strokeLinecap="round"
          strokeDasharray={around}
          strokeDashoffset={offset}
          className={draw ? "ring-draw" : undefined}
          style={draw ? ({ "--ring-around": around } as CSSProperties) : undefined}
        />
      </svg>
      {size !== "sm" && (
        <span className="text-center leading-none text-ink">
          <span className={clsx("block font-bold tabular-nums", number)}>{pct}</span>
          {size === "lg" && <span className="mt-0.5 block text-xs text-ink-3">match</span>}
        </span>
      )}
    </span>
  );
  return (
    <span
      role="img"
      aria-label={`${pct}% match`}
      title="Resume match, not your chance of an interview"
      className={clsx("inline-flex flex-none items-center gap-2", toneText[tone], className)}
    >
      {ring}
      {size === "sm" && <span className="w-6 text-right text-sm font-semibold text-ink tabular-nums">{pct}</span>}
    </span>
  );
}

/**
 * Rows inside one rounded card, separated by hairlines that start at the text (not the
 * icon). The main pattern for lists and settings.
 */
export function Group({ label, note, children, className, ...rest }: { label?: ReactNode; note?: ReactNode; children: ReactNode; className?: string } & Omit<HTMLAttributes<HTMLElement>, "children">) {
  const id = useId();
  return (
    <section aria-labelledby={label ? id : undefined} className={className} {...rest}>
      {label && (
        <h2 id={id} className="mb-2 px-1 text-xs font-normal text-ink-2">
          {label}
        </h2>
      )}
      <div className="overflow-hidden rounded-lg bg-surface">{children}</div>
      {note && <p className="mt-2 px-1 text-xs text-ink-3">{note}</p>}
    </section>
  );
}

/** Class for one row in a Group: use on an <li>, <a> or <div>. */
export const rowClass =
  "relative flex min-h-15 items-center gap-3 px-4 py-2.5 after:absolute after:right-0 after:bottom-0 after:left-16 after:h-px after:bg-line last:after:hidden";

/** Copies text to the clipboard and confirms for two seconds. */
export function CopyButton({ text, label = "Copy" }: { text: string; label?: string }) {
  const [copied, setCopied] = useState(false);
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // Clipboard blocked: the text is still selectable on the page.
    }
  };
  return (
    <Button size="sm" variant="ghost" onClick={copy}>
      {copied ? <Check className="size-4" aria-hidden /> : <Copy className="size-4" aria-hidden />}
      <span aria-live="polite">{copied ? "Copied" : label}</span>
    </Button>
  );
}

/** A round on/off filter button. */
export function Chip({ on, onClick, children }: { on: boolean; onClick: () => void; children: ReactNode }) {
  return (
    <button
      type="button"
      aria-pressed={on}
      onClick={onClick}
      className={clsx(
        "h-8 rounded-full px-3.5 font-medium transition-colors",
        on ? "bg-accent-soft text-accent-ink" : "bg-surface text-ink-2 hover:text-ink",
      )}
    >
      {children}
    </button>
  );
}

/** A choice of two or three: a grey capsule with a white pill on the selected option. */
export function Segmented<T extends string>({
  label,
  value,
  options,
  onChange,
}: {
  label: string;
  value: T;
  options: { value: T; label: string }[];
  onChange: (value: T) => void;
}) {
  return (
    <div role="group" aria-label={label} className="inline-flex h-9 flex-none rounded-full bg-subtle p-0.5">
      {options.map((o) => (
        <button
          key={o.value}
          type="button"
          aria-pressed={o.value === value}
          onClick={() => onChange(o.value)}
          className={clsx(
            "rounded-full px-3.5 font-medium transition-colors duration-200 ease-calm",
            o.value === value ? "bg-surface text-ink" : "text-ink-2 hover:text-ink",
          )}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}
