import { Columns3 } from "lucide-react";
import { Link } from "react-router";
import { PageHeader } from "../components/AppShell";
import { Alert, Badge, Card, EmptyState, Spinner, buttonClass } from "../components/ui";
import { BOARD_COLUMNS, STATUS_META, relativeTime, useJobs, type Job } from "../lib/jobs";

export function ApplicationsPage() {
  const { data, isPending, error } = useJobs();
  const tracked = (data ?? []).filter((j) => j.status !== "DISCOVERED");

  return (
    <>
      <PageHeader title="Applications" subtitle={data ? `${tracked.length} tracked` : undefined} />
      <div className="px-4 py-5 md:px-7 md:py-6">
        {isPending ? (
          <Spinner label="Loading applications" />
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
          <div className="-mx-4 flex snap-x scroll-px-4 md:scroll-px-7 gap-3.5 overflow-x-auto px-4 pb-2 md:-mx-7 md:px-7 xl:mx-0 xl:grid xl:grid-cols-5 xl:overflow-visible xl:px-0">
            {BOARD_COLUMNS.map((col) => {
              const items = tracked.filter((j) => col.statuses.includes(j.status));
              return (
                <section key={col.key} aria-label={col.label} className="w-64 flex-none snap-start xl:w-auto">
                  <h2 className="mb-2.5 flex items-center gap-1.5 text-sm font-semibold text-ink-2">
                    {col.label}
                    <span className="font-normal text-ink-3">{items.length}</span>
                  </h2>
                  <div className="flex flex-col gap-2.5">
                    {items.map((job) => (
                      <AppCard key={job.job_id} job={job} />
                    ))}
                    {items.length === 0 && <div className="rounded-lg border border-dashed border-line py-6 text-center text-xs text-ink-3">Nothing here</div>}
                  </div>
                </section>
              );
            })}
          </div>
        )}
      </div>
    </>
  );
}

function AppCard({ job }: { job: Job }) {
  const meta = STATUS_META[job.status] ?? { label: job.status, tone: "neutral" as const };
  const interview = job.status === "INTERVIEW" && job.interview_date ? new Date(job.interview_date) : null;
  const when = relativeTime(job.applied_at ?? job.created_at);
  return (
    <Card className="p-3">
      <h3 className="text-sm font-semibold">{job.title}</h3>
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
