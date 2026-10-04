import { useEffect, useState, type ReactNode } from "react";
import { Navigate } from "react-router";
import { Search } from "lucide-react";
import { PageHeader } from "../components/AppShell";
import { Alert, Badge, Button, Card, Spinner } from "../components/ui";
import { useAuth } from "../lib/auth";
import { relativeTime } from "../lib/jobs";
import { PAGE_SIZE, ROLES, auditSummary, useAdminAudit, useAdminMetrics, useAdminUsers, useSetRole, type AdminUser, type Role } from "../lib/admin";

const roleLabel = (r: string) => r.charAt(0) + r.slice(1).toLowerCase();

function Section({ title, children, action }: { title: string; children: ReactNode; action?: ReactNode }) {
  const id = `sec-${title.toLowerCase().replace(/\W+/g, "-")}`;
  return (
    <section aria-labelledby={id}>
      <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
        <h2 id={id} className="text-base font-semibold">
          {title}
        </h2>
        {action}
      </div>
      {children}
    </section>
  );
}

export function AdminPage() {
  const { user } = useAuth();
  if (user?.role !== "ADMIN") return <Navigate to="/" replace />;
  return (
    <>
      <PageHeader title="Admin" />
      <div className="mx-auto flex max-w-5xl flex-col gap-8 px-4 py-5 md:px-7 md:py-8">
        <Metrics />
        <Users currentUserId={user.user_id} />
        <Audit />
      </div>
    </>
  );
}

function Metrics() {
  const { data, isPending, error } = useAdminMetrics();
  if (isPending) return <Spinner />;
  if (error) return <Alert>Couldn't load platform numbers: {error.message}</Alert>;
  const tiles = [
    { label: "Users", value: data.total_users },
    { label: "Jobs found", value: data.total_jobs },
    { label: "Applications", value: data.total_applications },
    { label: "Organizations", value: data.total_organizations },
  ];
  const paid = Object.entries(data.active_subscriptions ?? {}).filter(([tier, n]) => (tier === "PRO" || tier === "ELITE") && n > 0);
  return (
    <Section title="Platform">
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        {tiles.map((t) => (
          <Card key={t.label} className="p-4">
            <span className="block text-xl font-semibold">{t.value.toLocaleString()}</span>
            <span className="text-ink-2">{t.label}</span>
          </Card>
        ))}
      </div>
      {paid.length > 0 && (
        <p className="mt-3 text-ink-2">
          Paid plans: {paid.map(([tier, n]) => `${n} ${tier.toLowerCase()}`).join(", ")}
        </p>
      )}
    </Section>
  );
}

function Users({ currentUserId }: { currentUserId: string }) {
  const [query, setQuery] = useState("");
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(0);
  const users = useAdminUsers(search, page);

  // Search once typing pauses, and start again from the first page.
  useEffect(() => {
    const t = setTimeout(() => {
      setSearch(query.trim());
      setPage(0);
    }, 400);
    return () => clearTimeout(t);
  }, [query]);

  const total = users.data?.total ?? 0;
  const pages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  return (
    <Section
      title="Users"
      action={
        <label className="relative w-full sm:w-64">
          <span className="sr-only">Search users</span>
          <Search className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-ink-3" aria-hidden />
          <input
            type="search"
            placeholder="Search name or email"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            className="h-9 w-full rounded-md border border-line bg-surface pr-3 pl-9 text-sm placeholder:text-ink-3 focus:border-accent focus:outline-none"
          />
        </label>
      }
    >
      <Card>
        {users.isPending ? (
          <Spinner />
        ) : users.error ? (
          <div className="p-4">
            <Alert>Couldn't load users: {users.error.message}</Alert>
          </div>
        ) : users.data.users.length === 0 ? (
          <p className="p-5 text-ink-2">No users match “{search}”.</p>
        ) : (
          <ul className="divide-y divide-line">
            {users.data.users.map((u) => (
              <UserRow key={u.user_id} u={u} isSelf={u.user_id === currentUserId} />
            ))}
          </ul>
        )}
      </Card>
      {total > PAGE_SIZE && (
        <div className="mt-3 flex items-center justify-between gap-3">
          <span className="text-ink-2">
            Page {page + 1} of {pages} · {total} users
          </span>
          <div className="flex gap-2">
            <Button size="sm" disabled={page === 0} onClick={() => setPage((p) => p - 1)}>
              Previous
            </Button>
            <Button size="sm" disabled={page + 1 >= pages} onClick={() => setPage((p) => p + 1)}>
              Next
            </Button>
          </div>
        </div>
      )}
    </Section>
  );
}

function UserRow({ u, isSelf }: { u: AdminUser; isSelf: boolean }) {
  const setRole = useSetRole();
  const [pending, setPending] = useState<Role | null>(null);
  const current = u.role.toUpperCase();

  return (
    <li className="flex flex-col gap-3 px-4 py-3 sm:flex-row sm:items-center sm:px-5">
      <div className="min-w-0 flex-1">
        <p className="flex flex-wrap items-center gap-2 font-medium">
          {u.full_name || "No name"}
          {isSelf && <Badge tone="accent">You</Badge>}
          {!u.is_active && <Badge tone="danger">Disabled</Badge>}
        </p>
        <p className="truncate text-ink-2">
          {u.email}
          <span className="text-ink-3"> · joined {relativeTime(u.created_at) ?? "—"}</span>
        </p>
      </div>
      {pending ? (
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-ink-2">
            Make {u.full_name?.split(" ")[0] || "them"} <b className="text-ink">{roleLabel(pending)}</b>?
          </span>
          <Button
            size="sm"
            variant={pending === "ADMIN" ? "danger" : "primary"}
            loading={setRole.isPending}
            onClick={() => setRole.mutate({ userId: u.user_id, role: pending }, { onSuccess: () => setPending(null) })}
          >
            Confirm
          </Button>
          <Button size="sm" variant="ghost" onClick={() => setPending(null)} disabled={setRole.isPending}>
            Cancel
          </Button>
        </div>
      ) : (
        <label className="flex items-center gap-2">
          <span className="text-ink-2">Role</span>
          <select
            value={current}
            // Admins can't demote themselves here; that would lock them out of this page.
            disabled={isSelf}
            onChange={(e) => setPending(e.target.value as Role)}
            className="h-8 rounded-md border border-line-strong bg-surface px-2 text-sm disabled:opacity-60"
          >
            {ROLES.map((r) => (
              <option key={r} value={r}>
                {roleLabel(r)}
              </option>
            ))}
          </select>
        </label>
      )}
      {setRole.error && <Alert>{setRole.error.message}</Alert>}
    </li>
  );
}

function Audit() {
  const { data, isPending, error } = useAdminAudit();
  return (
    <Section title="Admin activity">
      <Card className="p-4 sm:p-5">
        {isPending ? (
          <Spinner />
        ) : error ? (
          <Alert>Couldn't load activity: {error.message}</Alert>
        ) : data.length === 0 ? (
          <p className="text-ink-2">No admin actions yet.</p>
        ) : (
          <ul className="flex flex-col gap-2.5">
            {data.map((e) => (
              <li key={e.log_id} className="flex flex-wrap items-baseline justify-between gap-x-4">
                <span>
                  {auditSummary(e)}
                  {e.target_user_id && <span className="text-ink-3"> · {e.target_user_id}</span>}
                </span>
                <span className="text-xs text-ink-3">{relativeTime(e.created_at)}</span>
              </li>
            ))}
          </ul>
        )}
      </Card>
    </Section>
  );
}
