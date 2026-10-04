import { useMemo, useState } from "react";
import { BriefcaseBusiness, Clock, ExternalLink, MapPin, Search, Wallet } from "lucide-react";
import { PageHeader } from "../components/AppShell";
import { Alert, Button, Card, CompanyMark, EmptyState, Spinner, buttonClass, cx, toneText } from "../components/ui";
import { isMatch, matchSummary, relativeTime, scorePercent, scoreTone, useJobs, type Job } from "../lib/jobs";

type Sort = "match" | "newest";

function postedAt(job: Job) {
  return job.posted_date ?? job.created_at;
}

export function JobsPage() {
  const { data, isPending, error, refetch } = useJobs();
  const [sort, setSort] = useState<Sort>("match");
  const [remoteOnly, setRemoteOnly] = useState(false);
  const [query, setQuery] = useState("");

  const matches = useMemo(() => (data ?? []).filter(isMatch), [data]);

  const visible = useMemo(() => {
    const q = query.trim().toLowerCase();
    const list = matches.filter(
      (j) =>
        (!remoteOnly || /remote/i.test(j.location)) &&
        (!q || `${j.title} ${j.company} ${j.location}`.toLowerCase().includes(q)),
    );
    return list.sort((a, b) =>
      sort === "match"
        ? b.match_score - a.match_score
        : new Date(postedAt(b) ?? 0).getTime() - new Date(postedAt(a) ?? 0).getTime(),
    );
  }, [matches, sort, remoteOnly, query]);

  return (
    <>
      <PageHeader title="Jobs" subtitle={data ? `${matches.length} matches` : undefined} />
      <div className="mx-auto max-w-5xl px-4 py-5 md:px-7 md:py-6">
        <div className="mb-4 flex flex-wrap items-center gap-2">
          <Chip on={sort === "match"} onClick={() => setSort("match")}>
            Best match
          </Chip>
          <Chip on={sort === "newest"} onClick={() => setSort("newest")}>
            Newest
          </Chip>
          <Chip on={remoteOnly} onClick={() => setRemoteOnly((v) => !v)}>
            Remote
          </Chip>
          <label className="relative ml-auto w-full sm:w-64">
            <span className="sr-only">Search jobs</span>
            <Search className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-ink-3" aria-hidden />
            <input
              type="search"
              placeholder="Search title or company"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              className="h-9 w-full rounded-md border border-line bg-surface pr-3 pl-9 text-sm placeholder:text-ink-3 focus:border-accent focus:outline-none"
            />
          </label>
        </div>

        {isPending ? (
          <Spinner label="Loading jobs" />
        ) : error ? (
          <div className="flex flex-col items-start gap-3">
            <Alert>Couldn't load jobs: {error.message}</Alert>
            <Button onClick={() => refetch()}>Try again</Button>
          </div>
        ) : visible.length === 0 ? (
          <Card>
            {matches.length === 0 ? (
              <EmptyState icon={<BriefcaseBusiness className="size-5" />} title="No matches yet">
                Once your profile is set up, new openings that fit you will show up here with a match score.
              </EmptyState>
            ) : (
              <EmptyState icon={<Search className="size-5" />} title="Nothing matches these filters">
                Try clearing the search or turning off Remote.
              </EmptyState>
            )}
          </Card>
        ) : (
          <Card className="overflow-hidden">
            <ul>
              {visible.map((job) => (
                <JobRow key={job.job_id} job={job} />
              ))}
            </ul>
          </Card>
        )}
      </div>
    </>
  );
}

function Chip({ on, onClick, children }: { on: boolean; onClick: () => void; children: React.ReactNode }) {
  return (
    <button
      type="button"
      aria-pressed={on}
      onClick={onClick}
      className={cx(
        "h-8 rounded-full border px-3 font-medium",
        on ? "border-accent bg-accent-soft text-accent-ink" : "border-line bg-surface text-ink-2 hover:bg-subtle",
      )}
    >
      {children}
    </button>
  );
}

function JobRow({ job }: { job: Job }) {
  const pct = scorePercent(job.match_score);
  const tone = scoreTone(pct);
  const why = matchSummary(job);
  const when = relativeTime(postedAt(job));

  return (
    <li className="flex flex-col gap-3 border-b border-line px-4 py-4 last:border-b-0 sm:flex-row sm:items-center sm:gap-4 sm:px-5">
      <div className="flex min-w-0 flex-1 gap-3 sm:gap-4">
        <CompanyMark name={job.company} />
        <div className="min-w-0 flex-1">
          <h2 className="text-sm font-semibold">{job.title}</h2>
          <div className="mt-0.5 flex flex-wrap gap-x-3 gap-y-0.5 text-ink-2">
            <span>{job.company}</span>
            {job.location && (
              <span className="flex items-center gap-1">
                <MapPin className="size-3.5" aria-hidden />
                {job.location}
              </span>
            )}
            {job.salary_range && (
              <span className="flex items-center gap-1">
                <Wallet className="size-3.5" aria-hidden />
                {job.salary_range}
              </span>
            )}
            {when && (
              <span className="flex items-center gap-1 text-ink-3">
                <Clock className="size-3.5" aria-hidden />
                {when}
              </span>
            )}
          </div>
          {why && <p className="mt-1.5 text-ink-2">{why}</p>}
        </div>
      </div>
      <div className="flex items-center gap-4 pl-13 sm:pl-0">
        <div className="w-14 text-center" aria-label={`${pct}% match`}>
          <span className={cx("block text-lg leading-none font-bold", toneText[tone])}>{pct}</span>
          <span className="text-xs tracking-wide text-ink-3 uppercase">match</span>
        </div>
        <a href={job.url} target="_blank" rel="noopener noreferrer" className={buttonClass(pct >= 80 ? "primary" : "secondary")}>
          View posting
          <ExternalLink className="size-3.5" aria-hidden />
          <span className="sr-only">(opens in a new tab)</span>
        </a>
      </div>
    </li>
  );
}
