import { useEffect, useRef, useState, type ReactNode } from "react";
import { Link, NavLink, Outlet } from "react-router";
import { BriefcaseBusiness, Columns3, House, LogOut, Mic, Settings, ShieldCheck, Sparkles, UserRound, type LucideIcon } from "lucide-react";
import { initials, useAuth } from "../lib/auth";
import { useIsPremium } from "../lib/billing";
import { isMatch, useVisibleJobs } from "../lib/jobs";
import { cx } from "./ui";

interface NavItem {
  to: string;
  label: string;
  icon: LucideIcon;
  mobile: boolean;
}

const NAV: NavItem[] = [
  { to: "/", label: "Home", icon: House, mobile: true },
  { to: "/jobs", label: "Jobs", icon: BriefcaseBusiness, mobile: true },
  { to: "/applications", label: "Applications", icon: Columns3, mobile: true },
  { to: "/prep", label: "Prep", icon: Mic, mobile: true },
  { to: "/profile", label: "Profile", icon: UserRound, mobile: false },
];

export function Logo() {
  return (
    <Link to="/" className="flex items-center gap-2 text-base font-bold">
      <img src="/favicon.svg" alt="" className="size-7" />
      JobCopilot
    </Link>
  );
}

export function AppShell() {
  const { data: jobs } = useVisibleJobs();
  const newMatches = jobs?.filter(isMatch).length ?? 0;

  return (
    <div className="flex min-h-dvh">
      <a href="#main" className="sr-only focus:not-sr-only focus:fixed focus:top-2 focus:left-2 focus:z-50 focus:rounded-md focus:bg-surface focus:px-3 focus:py-2">
        Skip to content
      </a>

      {/* Desktop sidebar */}
      <aside className="sticky top-0 hidden h-dvh w-58 flex-none flex-col border-r border-line bg-surface px-3 py-4 md:flex">
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
                  "flex items-center gap-2.5 rounded-md px-2.5 py-2 font-medium",
                  isActive ? "bg-accent-soft text-accent-ink" : "text-ink-2 hover:bg-subtle hover:text-ink",
                )
              }
            >
              <Icon className="size-4" aria-hidden />
              {label}
              {to === "/jobs" && newMatches > 0 && (
                <span className="ml-auto rounded-full bg-accent px-1.5 text-xs font-semibold text-white" aria-label={`${newMatches} new`}>
                  {newMatches}
                </span>
              )}
            </NavLink>
          ))}
        </nav>
        <div className="flex-1" />
        <div className="border-t border-line pt-2">
          <UserMenu placement="up" />
        </div>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col pb-16 md:pb-0">
        {/* Mobile top bar */}
        <header className="sticky top-0 z-20 flex h-14 items-center justify-between border-b border-line bg-surface px-4 md:hidden">
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
              cx("flex flex-1 flex-col items-center justify-center gap-0.5 text-xs font-medium", isActive ? "text-accent" : "text-ink-3")
            }
          >
            <Icon className="size-5" aria-hidden />
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
  const close = () => setOpen(false);

  return (
    <div ref={ref} className="relative">
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
            "absolute z-30 w-56 rounded-lg border border-line bg-surface p-1 shadow-pop",
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

/** Page title bar shared by every screen. */
export function PageHeader({ title, subtitle, actions }: { title: string; subtitle?: ReactNode; actions?: ReactNode }) {
  return (
    <div className="flex flex-wrap items-center gap-x-3 gap-y-2 border-b border-line bg-surface px-4 py-4 md:h-15 md:px-7 md:py-0">
      <h1 className="text-lg font-semibold">{title}</h1>
      {subtitle && <span className="text-ink-3">{subtitle}</span>}
      {actions && <div className="ml-auto flex items-center gap-2">{actions}</div>}
    </div>
  );
}
