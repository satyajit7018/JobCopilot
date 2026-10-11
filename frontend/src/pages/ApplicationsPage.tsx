import { useState } from "react";
import { Columns3 } from "lucide-react";
import { Link } from "react-router";
import { PageHeader } from "../components/AppShell";
import { HeldQuestions } from "../components/HeldQuestions";
import { Alert, Badge, Card, Chip, EmptyState, SkeletonRows, buttonClass, cx, lift } from "../components/ui";
import { BOARD_COLUMNS, STATUS_META, isTracked, relativeTime, useJobs, type Job } from "../lib/jobs";

export function ApplicationsPage() {
  const { data, isPending, error } = useJobs();
  const tracked = (data ?? []).filter(isTracked);
  // Only columns with something in them; an empty "In progress" column is just noise.
  const columns = BOARD_COLUMNS.map((col) => ({ ...col, items: tracked.filter((j) => col.statuses.includes(j.status)) })).filter(
    (col) => col.items.length > 0,
  );

  return (
    <>
      <PageHeader width="max-w-none" title="Applied" subtitle={data ? `${tracked.length} tracked` : undefined} />
      <div className="px-4 py-5 md:px-7 md:py-6">
        <HeldQuestions />
        {isPending ? (
          <div className="max-w-2xl">
            <SkeletonRows rows={4} avatar={false} label="Loading applications" />
          </div>
        ) : error ? (
          <Alert>Couldn't load applications: {error.message}</Alert>
        ) : tracked.length === 0 ? (
          <Card className="mx-auto max-w-2xl">
            <EmptyState
              icon={<Columns3 className="size-5" />}
              title="No applications yet"
              action={
                <Link to="/jobs" className={buttonClass("primary")}>
                  Browse your matches
                </Link>
              }
            >
              When you apply to a job, it moves here so you can follow it from applied to offer.
            </EmptyState>
          </Card>
        ) : (
          <>
            <PhoneList columns={columns} />
            <div
              className="-mx-4 hidden snap-x md:flex scroll-px-4 gap-3.5 overflow-x-auto px-4 pb-2 md:-mx-7 md:scroll-px-7 md:px-7 xl:mx-0 xl:grid xl:overflow-visible xl:px-0"
              style={{ gridTemplateColumns: `repeat(${Math.max(columns.length, 3)}, minmax(0, 1fr))` }}
            >
              {columns.map((col) => (
                <section key={col.key} aria-label={col.label} className="w-64 flex-none snap-start xl:w-auto">
                  <h2 className="mb-2.5 flex items-center gap-1.5 text-sm font-semibold text-ink-2">
                    {col.label}
                    <span className="font-normal text-ink-3">{col.items.length}</span>
                  </h2>
                  <div className="flex flex-col gap-2.5">
                    {col.items.map((job) => (
                      <AppCard key={job.job_id} job={job} />
                    ))}
                  </div>
                </section>
              ))}
            </div>
          </>
        )}
      </div>
    </>
  );
}

type Column = (typeof BOARD_COLUMNS)[number] & { items: Job[] };

/** Phones: one list with stage filters instead of a board that scrolls sideways. */
function PhoneList({ columns }: { columns: Column[] }) {
  const [stage, setStage] = useState("all");
  const current = columns.find((c) => c.key === stage);
  const items = current ? current.items : columns.flatMap((c) => c.items);
  const total = columns.reduce((n, c) => n + c.items.length, 0);
  return (
    <div className="md:hidden">
      <div
        className="relative -mx-4 mb-3 flex items-center gap-2 overflow-x-auto px-4 pb-1 [scrollbar-width:none] [&>*]:flex-none"
        role="group"
        aria-label="Filter by stage"
      >
        <Chip on={!current} onClick={() => setStage("all")}>
          All {total}
        </Chip>
        {columns.map((c) => (
          <Chip key={c.key} on={current?.key === c.key} onClick={() => setStage(c.key)}>
            {c.label} {c.items.length}
          </Chip>
        ))}
      </div>
      <ul className="flex flex-col gap-2.5" aria-label={current ? current.label : "All applications"}>
        {items.map((job) => (
          <li key={job.job_id}>
            <AppCard job={job} />
          </li>
        ))}
      </ul>
    </div>
  );
}

function AppCard({ job }: { job: Job }) {
  const meta = STATUS_META[job.status] ?? { label: job.status, tone: "neutral" as const };
  const interview = job.status === "INTERVIEW" && job.interview_date ? new Date(job.interview_date) : null;
  const applied = relativeTime(job.applied_at);
  const when = applied ? `applied ${applied}` : relativeTime(job.created_at);
  return (
    <Card className={cx("relative p-3", lift)}>
      <h3 className="text-sm font-semibold">
        {/* The link's ::after covers the card, so the whole card is clickable. */}
        <Link to={`/applications/${encodeURIComponent(job.job_id)}`} className="after:absolute after:inset-0 after:rounded-lg">
          {job.title}
        </Link>
      </h3>
      <p className="text-xs text-ink-2">
        {job.company}
        {when && <span className="text-ink-3"> · {when}</span>}
      </p>
      <div className="mt-2 flex flex-wrap gap-1.5">
        <Badge tone={meta.tone}>{meta.label}</Badge>
        {interview && !Number.isNaN(interview.getTime()) && (
          <Badge tone="info">{interview.toLocaleString(undefined, { weekday: "short", hour: "numeric", minute: "2-digit" })}</Badge>
        )}
      </div>
    </Card>
  );
}
