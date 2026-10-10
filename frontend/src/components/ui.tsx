// Core components. Every screen is built from these; no one-off styling in pages.
import { clsx } from "clsx";
import {
  forwardRef,
  useId,
  useState,
  type ButtonHTMLAttributes,
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
  "inline-flex items-center justify-center gap-1.5 rounded-md border font-medium whitespace-nowrap transition-colors disabled:pointer-events-none disabled:opacity-50";
const buttonVariants: Record<ButtonVariant, string> = {
  primary: "border-accent bg-accent text-on-solid hover:bg-accent-hover hover:border-accent-hover",
  secondary: "border-line-strong bg-surface text-ink hover:bg-subtle",
  ghost: "border-transparent bg-transparent text-ink-2 hover:bg-subtle hover:text-ink",
  // Only for the final step of an irreversible action.
  danger: "border-danger bg-danger text-on-solid hover:opacity-90",
};
const buttonSizes: Record<ButtonSize, string> = {
  sm: "h-8 px-2.5 text-sm",
  md: "h-9 px-3.5 text-sm",
  lg: "h-11 px-5 text-base",
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
  info: "bg-info-soft text-info",
  danger: "bg-danger-soft text-danger",
};

export const toneText: Record<Tone, string> = {
  neutral: "text-ink-2",
  accent: "text-accent",
  ok: "text-ok",
  warn: "text-warn",
  info: "text-info",
  danger: "text-danger",
};

export function Badge({ tone = "neutral", children, className }: { tone?: Tone; children: ReactNode; className?: string }) {
  return (
    <span className={clsx("inline-flex h-5.5 items-center gap-1 rounded-full px-2 text-xs font-medium", toneClass[tone], className)}>
      {children}
    </span>
  );
}

export function Card({ className, children }: { className?: string; children: ReactNode }) {
  return <div className={clsx("rounded-lg border border-line bg-surface shadow-card", className)}>{children}</div>;
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
        className={clsx(controlClass, "h-10", error ? "border-danger" : "border-line-strong")}
        {...rest}
      />
      <FieldNote id={inputId} hint={hint} error={error} />
    </div>
  );
});

const controlClass =
  "w-full rounded-md border bg-surface px-3 text-sm text-ink placeholder:text-ink-3 focus:border-accent focus:outline-none focus:ring-3 focus:ring-accent-soft";

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
        className={clsx(controlClass, "h-10 border-line-strong")}
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
        className={clsx(controlClass, "border-line-strong py-2 leading-relaxed")}
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
                on ? "border-accent bg-accent-soft text-accent-ink" : "border-line-strong bg-surface text-ink-2 hover:bg-subtle",
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
        checked ? "border-accent bg-accent-soft/50" : "border-line bg-surface hover:bg-subtle",
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
    <div role="status" className="overflow-hidden rounded-lg border border-line bg-surface shadow-card">
      <span className="sr-only">{label}…</span>
      <ul aria-hidden className="animate-pulse motion-reduce:animate-none">
        {Array.from({ length: rows }, (_, i) => (
          <li key={i} className="flex items-center gap-3 border-b border-line px-4 py-4 last:border-b-0 sm:gap-4 sm:px-5">
            {avatar && <span className="size-10 flex-none rounded-md bg-subtle" />}
            <span className="flex min-w-0 flex-1 flex-col gap-2">
              <span className="h-3.5 w-2/5 rounded bg-subtle" />
              <span className="h-3 w-3/5 rounded bg-subtle" />
            </span>
            <span className="h-8 w-20 flex-none rounded-md bg-subtle max-sm:hidden" />
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
    <div className="flex flex-col items-center px-6 py-16 text-center">
      <div className="mb-4 grid size-12 place-items-center rounded-full bg-accent-soft text-accent">{icon}</div>
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

const LOGO_TINTS = ["#0F766E", "#7C3AED", "#C2410C", "#1D4ED8", "#BE185D", "#4D7C0F"];

/** Deterministic colored initial for a company (no remote logos, no tracking). */
export function CompanyMark({ name, size = "md" }: { name: string; size?: "sm" | "md" }) {
  let hash = 0;
  for (const ch of name) hash = (hash * 31 + ch.charCodeAt(0)) >>> 0;
  return (
    <div
      aria-hidden
      className={clsx(
        "grid flex-none place-items-center rounded-md font-bold text-white",
        size === "md" ? "size-10 text-sm" : "size-8 text-xs",
      )}
      style={{ background: LOGO_TINTS[hash % LOGO_TINTS.length] }}
    >
      {name.trim()[0]?.toUpperCase() ?? "?"}
    </div>
  );
}

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
        "h-8 rounded-full border px-3 font-medium",
        on ? "border-accent bg-accent-soft text-accent-ink" : "border-line bg-surface text-ink-2 hover:bg-subtle",
      )}
    >
      {children}
    </button>
  );
}
