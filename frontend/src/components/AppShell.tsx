import { useEffect, useRef, useState, type ReactNode } from "react";
import { Link, NavLink, Outlet } from "react-router";
import { BriefcaseBusiness, CircleHelp, ListChecks, LogOut, MessageSquare, Mic, Settings, ShieldCheck, Sparkles, Sun, UserRound, type LucideIcon } from "lucide-react";
import { initials, useAuth } from "../lib/auth";
import { useIsPremium } from "../lib/billing";
import { usePageTitle } from "../lib/pageTitle";
import { VISIT_EVENT, isMatch, isNewSince, readLastVisit, useVisibleJobs } from "../lib/jobs";
import { cx } from "./ui";
import { FeedbackDialog } from "./FeedbackDialog";

interface NavItem {
  to: string;
  label: string;
  icon: LucideIcon;
  mobile: boolean;
}

const NAV: NavItem[] = [
  { to: "/", label: "Today", icon: Sun, mobile: true },
  { to: "/jobs", label: "Jobs", icon: BriefcaseBusiness, mobile: true },
  { to: "/applications", label: "Applied", icon: ListChecks, mobile: true },
  { to: "/prep", label: "Prep", icon: Mic, mobile: true },
  { to: "/profile", label: "Profile", icon: UserRound, mobile: false },
];

export function Logo() {
  return (
    <Link to="/" className="flex items-center gap-2 text-base font-bold tracking-tight">
      <img src="/favicon.svg" alt="" className="size-7" />
      <span>
        Job<span className="text-accent">Copilot</span>
      </span>
    </Link>
  );
}

/** Your plan at a glance, so Premium is easy to find (and to confirm you have it). */
function PlanCard() {
  const premium = useIsPremium();
  if (premium)
    return (
      <p className="mb-2 flex items-center gap-1.5 px-2.5 text-xs font-medium text-accent-ink">
        <Sparkles className="size-3.5" aria-hidden />
        Premium
      </p>
    );
  // One quiet row, not a coloured box.
  return (
    <Link to="/plans" className="mb-2 flex items-center gap-1.5 rounded-md px-2.5 py-2 text-xs text-ink-2 hover:bg-subtle hover:text-ink">
      <Sparkles className="size-3.5 text-accent" aria-hidden />
      Free plan
      <span className="ml-auto font-medium text-accent">Upgrade</span>
    </Link>
  );
}

export function AppShell() {
  const { data: jobs } = useVisibleJobs();
  // Matches found since the user last looked at Jobs (all of them before the first look),
  // so the number changes and means "something to see".
  // Leaving Jobs marks its matches as seen; re-read the count when that happens.
  const [, refresh] = useState(0);
  useEffect(() => {
    const bump = () => refresh((n) => n + 1);
    window.addEventListener(VISIT_EVENT, bump);
    return () => window.removeEventListener(VISIT_EVENT, bump);
  }, []);
  const lastSeenJobs = readLastVisit("jobs");
  const matches = jobs?.filter(isMatch) ?? [];
  const newMatches = lastSeenJobs === null ? matches.length : matches.filter((j) => isNewSince(j, lastSeenJobs)).length;

  return (
    <div className="flex min-h-dvh">
      <a href="#main" className="sr-only focus:not-sr-only focus:fixed focus:top-2 focus:left-2 focus:z-50 focus:rounded-md focus:bg-surface focus:px-3 focus:py-2">
        Skip to content
      </a>

      {/* Desktop sidebar */}
      <aside className="sticky top-0 hidden h-dvh w-60 flex-none flex-col px-3 py-5 md:flex">
        <div className="px-2 pb-5">
          <Logo />
        </div>
        <nav aria-label="Main" className="flex flex-col gap-1">
          {NAV.map(({ to, label, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
              end={to === "/"}
              className={({ isActive }) =>
                cx(
                  "flex items-center gap-3 rounded-md px-3 py-2.5 font-medium transition-colors",
                  isActive ? "bg-subtle text-ink" : "text-ink-2 hover:bg-subtle/60 hover:text-ink",
                )
              }
            >
              <Icon className="size-5" strokeWidth={1.75} aria-hidden />
              {label}
              {to === "/jobs" && newMatches > 0 && (
                <span className="ml-auto rounded-full bg-accent px-1.5 text-xs font-semibold text-on-solid" aria-label={`${newMatches} new`}>
                  {newMatches}
                </span>
              )}
            </NavLink>
          ))}
        </nav>
        <div className="flex-1" />
        <PlanCard />
        <div className="pt-1">
          <UserMenu placement="up" />
        </div>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col pb-16 md:pb-0">
        {/* Mobile top bar */}
        <header className="sticky top-0 z-20 flex h-13 items-center justify-between bg-canvas px-4 md:hidden">
          <Logo />
          <UserMenu placement="down" compact />
        </header>
        <main id="main" className="flex-1">
          <Outlet />
        </main>
      </div>

      {/* Mobile tab bar */}
      <nav aria-label="Main" className="fixed inset-x-0 bottom-0 z-20 flex h-16 border-t border-line bg-surface md:hidden">
        {NAV.filter((n) => n.mobile).map(({ to, label, icon: Icon }) => (
          <NavLink
            key={to}
            to={to}
            end={to === "/"}
            className={({ isActive }) =>
              cx("flex flex-1 flex-col items-center justify-center gap-0.5 text-[0.6875rem] font-medium", isActive ? "text-accent" : "text-ink-3")
            }
          >
            <Icon className="size-6" strokeWidth={1.75} aria-hidden />
            {label}
          </NavLink>
        ))}
      </nav>
    </div>
  );
}

function UserMenu({ placement, compact }: { placement: "up" | "down"; compact?: boolean }) {
  const { user, logout } = useAuth();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const onDown = (e: MouseEvent) => {
      if (!ref.current?.contains(e.target as Node)) setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    document.addEventListener("mousedown", onDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  const isAdmin = user?.role?.toUpperCase() === "ADMIN";
  const premium = useIsPremium();
  const [feedbackOpen, setFeedbackOpen] = useState(false);
  const close = () => setOpen(false);

  return (
    <div ref={ref} className="relative">
      <FeedbackDialog open={feedbackOpen} onClose={() => setFeedbackOpen(false)} />
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-haspopup="menu"
        aria-expanded={open}
        className={cx("flex w-full items-center gap-2.5 rounded-md text-left hover:bg-subtle", compact ? "p-1" : "p-2")}
      >
        <span className="grid size-8 flex-none place-items-center rounded-full bg-accent-soft text-xs font-semibold text-accent-ink">
          {initials(user?.full_name || user?.email)}
        </span>
        {!compact && (
          <span className="min-w-0">
            <span className="block truncate font-medium">{user?.full_name || "Your account"}</span>
            <span className="block truncate text-xs text-ink-3">{user?.email}</span>
          </span>
        )}
        {compact && <span className="sr-only">Account menu</span>}
      </button>
      {open && (
        <div
          role="menu"
          className={cx(
            "absolute z-30 w-60 rounded-lg bg-surface p-1.5 shadow-pop",
            placement === "up" ? "bottom-full left-0 mb-2" : "top-full right-0 mt-2",
          )}
        >
          <MenuLink to="/profile" icon={<UserRound className="size-4" />} onClick={close} className="md:hidden">
            Profile
          </MenuLink>
          <MenuLink to="/settings" icon={<Settings className="size-4" />} onClick={close}>
            Settings
          </MenuLink>
          <MenuLink to="/plans" icon={<Sparkles className="size-4" />} onClick={close}>
            {premium ? "Premium" : "Upgrade to Premium"}
          </MenuLink>
          <MenuLink to="/help" icon={<CircleHelp className="size-4" />} onClick={close}>
            Help
          </MenuLink>
          <button
            type="button"
            role="menuitem"
            onClick={() => {
              close();
              setFeedbackOpen(true);
            }}
            className="flex w-full items-center gap-2.5 rounded-md px-2.5 py-2 text-ink-2 hover:bg-subtle hover:text-ink"
          >
            <MessageSquare className="size-4" aria-hidden />
            Send feedback
          </button>
          {isAdmin && (
            <MenuLink to="/admin" icon={<ShieldCheck className="size-4" />} onClick={close}>
              Admin
            </MenuLink>
          )}
          <div className="my-1 border-t border-line" />
          <button
            type="button"
            role="menuitem"
            onClick={() => {
              close();
              void logout();
            }}
            className="flex w-full items-center gap-2.5 rounded-md px-2.5 py-2 text-ink-2 hover:bg-subtle hover:text-ink"
          >
            <LogOut className="size-4" aria-hidden />
            Sign out
          </button>
        </div>
      )}
    </div>
  );
}

function MenuLink({
  to,
  icon,
  children,
  onClick,
  className,
}: {
  to: string;
  icon: ReactNode;
  children: ReactNode;
  onClick: () => void;
  className?: string;
}) {
  return (
    <Link
      to={to}
      role="menuitem"
      onClick={onClick}
      className={cx("flex items-center gap-2.5 rounded-md px-2.5 py-2 text-ink-2 hover:bg-subtle hover:text-ink", className)}
    >
      {icon}
      {children}
    </Link>
  );
}

/**
 * The large title at the top of a screen. It sits in the page itself (no bar, no line) and
 * scrolls away with it. `eyebrow` is the small line above it; `subtitle` the line below.
 */
export function PageHeader({
  title,
  subtitle,
  eyebrow,
  actions,
  tabTitle,
  width = "max-w-5xl",
}: {
  title: string;
  subtitle?: ReactNode;
  eyebrow?: ReactNode;
  actions?: ReactNode;
  /** Browser tab name when it should differ from the heading (a job's title, "Home"). */
  tabTitle?: string;
  /** Matches the page's content column so the title lines up with it. */
  width?: string;
}) {
  usePageTitle(tabTitle ?? title);
  return (
    <div className={cx("mx-auto flex w-full flex-wrap items-end gap-x-3 gap-y-2 px-4 pt-3 md:px-7 md:pt-9", width)}>
      <div className="min-w-0 flex-1">
        {eyebrow && <p className="text-xs text-ink-2">{eyebrow}</p>}
        <h1 className="text-xl font-bold md:text-2xl">{title}</h1>
        {subtitle && <p className="mt-0.5 text-xs text-ink-2">{subtitle}</p>}
      </div>
      {actions && <div className="flex items-center gap-2 pb-1">{actions}</div>}
    </div>
  );
}
