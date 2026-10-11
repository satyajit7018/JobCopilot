import { useEffect, useMemo, useState } from "react";
import { Bookmark, BookmarkCheck, BriefcaseBusiness, Clock, ExternalLink, EyeOff, MapPin, RefreshCw, Search, Wallet } from "lucide-react";
import { PageHeader } from "../components/AppShell";
import { SearchProgress } from "../components/SearchProgress";
import { Alert, Badge, Button, Card, Chip, CompanyMark, EmptyState, ScoreRing, SkeletonRows, buttonClass, cx } from "../components/ui";
import { Link, useSearchParams } from "react-router";
import {
  HIDE_REASONS,
  REGION_LABELS,
  isMatch,
  isNewSince,
  isRemote,
  jobRegions,
  matchSummary,
  relativeTime,
  rememberMatchOrder,
  scorePercent,
  useFindNewJobs,
  useHideReason,
  useLastVisit,
  useRemoveSkipRule,
  useSetMatchHidden,
  useSetMatchSaved,
  useVisibleJobs,
  type Job,
  type Region,
} from "../lib/jobs";

type Sort = "match" | "newest";

/** From this score up, a row gets the "strong match" edge. */
const STRONG_MATCH = 90;

/** How many jobs to show at once; the rest sit behind "Show more". */
const PAGE_SIZE = 20;

function postedAt(job: Job) {
  return job.posted_date ?? job.created_at;
}

export function JobsPage() {
  const { data, isPending, error, refetch, hiddenMatches: hidden } = useVisibleJobs();
  // Filters live in the address, so coming back from a job keeps them (and the link can be shared).
  const [params, setParams] = useSearchParams();
  const setParam = (key: string, value: string | boolean | number, fallback: string | boolean | number) =>
    setParams(
      (prev) => {
        const next = new URLSearchParams(prev);
        if (value === fallback) next.delete(key);
        else next.set(key, String(value));
        if (key !== "n") next.delete("n");
        return next;
      },
      { replace: true, preventScrollReset: true },
    );
  const sort: Sort = params.get("sort") === "newest" ? "newest" : "match";
  const remoteOnly = params.get("remote") === "true";
  const savedOnly = params.get("saved") === "true";
  const query = params.get("q") ?? "";
  const region = (params.get("region") ?? "") as Region | "";
  const minMatch = Number(params.get("min")) || 0;
  const limit = Math.max(PAGE_SIZE, Number(params.get("n")) || PAGE_SIZE);
  const setSort = (v: Sort) => setParam("sort", v, "match");
  const setRemoteOnly = (v: boolean) => setParam("remote", v, false);
  const setSavedOnly = (v: boolean) => setParam("saved", v, false);
  const setQuery = (v: string) => setParam("q", v, "");
  const setRegion = (v: Region | "") => setParam("region", v, "");
  const setMinMatch = (v: number) => setParam("min", v, 0);
  const lastVisit = useLastVisit("jobs");
  const hide = useSetMatchHidden();
  const [hiddenJob, setHiddenJob] = useState<Job | null>(null);
  const findNew = useFindNewJobs();

  const matches = useMemo(() => (data ?? []).filter(isMatch), [data]);

  const visible = useMemo(() => {
    const q = query.trim().toLowerCase();
    const list = matches.filter(
      (j) =>
        (!remoteOnly || isRemote(j.location)) &&
        (!savedOnly || j.status === "SAVED") &&
        (!region || jobRegions(j.location).includes(region)) &&
        scorePercent(j.match_score) >= minMatch &&
        (!q || `${j.title} ${j.company} ${j.location}`.toLowerCase().includes(q)),
    );
    return list.sort((a, b) =>
      sort === "match"
        ? b.match_score - a.match_score
        : new Date(postedAt(b) ?? 0).getTime() - new Date(postedAt(a) ?? 0).getTime(),
    );
  }, [matches, sort, remoteOnly, savedOnly, query, region, minMatch]);
  // "Next match" on a job page walks this list in the order shown here.
  useEffect(() => rememberMatchOrder(visible.map((j) => j.job_id)), [visible]);
  const savedCount = useMemo(() => matches.filter((j) => j.status === "SAVED").length, [matches]);
  const save = useSetMatchSaved();
  const newCount = useMemo(() => matches.filter((j) => isNewSince(j, lastVisit)).length, [matches, lastVisit]);

  const hideJob = (job: Job) => {
    setHiddenJob(job);
    hide.mutate({ jobId: job.job_id, hidden: true });
  };

  return (
    <>
      <PageHeader
        title="Jobs"
        actions={
          <Button size="sm" loading={findNew.isPending} onClick={() => findNew.mutate()}>
            <RefreshCw className="size-3.5" aria-hidden />
            Find new jobs
          </Button>
        }
        subtitle={
          data ? (
            <>
              {matches.length} matches
              {newCount > 0 && ` · ${newCount} new`}
              {hidden > 0 && (
                <>
                  {" · "}
                  <Link to="/profile" className="text-accent hover:underline">
                    {hidden} hidden by your job sources
                  </Link>
                </>
              )}
            </>
          ) : undefined
        }
      />
      <div className="mx-auto max-w-5xl px-4 py-5 md:px-7 md:py-6">
        <div className="mb-4 flex flex-col gap-2 sm:flex-row sm:flex-wrap sm:items-center">
          <div className="relative -mx-4 flex flex-none items-center gap-2 overflow-x-auto px-4 pb-1 sm:mx-0 sm:flex-wrap sm:overflow-visible sm:px-0 sm:pb-0 [scrollbar-width:none] [&>*]:flex-none">
          <Chip on={sort === "match"} onClick={() => setSort("match")}>
            Best match
          </Chip>
          <Chip on={sort === "newest"} onClick={() => setSort("newest")}>
            Newest
          </Chip>
          <Chip on={remoteOnly} onClick={() => setRemoteOnly(!remoteOnly)}>
            Remote
          </Chip>
          <Chip on={savedOnly} onClick={() => setSavedOnly(!savedOnly)}>
            Saved{savedCount > 0 && ` (${savedCount})`}
          </Chip>
          <FilterSelect
            label="Location"
            value={region}
            onChange={(v) => setRegion(v as Region | "")}
            options={[{ value: "", label: "Anywhere" }, ...Object.entries(REGION_LABELS).map(([value, label]) => ({ value, label }))]}
          />
          <FilterSelect
            label="Match"
            value={String(minMatch)}
            onChange={(v) => setMinMatch(Number(v))}
            options={[
              { value: "0", label: "Any match" },
              { value: "70", label: "70% or more" },
              { value: "80", label: "80% or more" },
            ]}
          />
          </div>
          <label className="relative w-full sm:ml-auto sm:w-64">
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

        <FindNewJobsStatus search={findNew} />
        {hiddenJob && (
          <HiddenNotice
            key={hiddenJob.job_id}
            job={hiddenJob}
            onUndo={() => {
              hide.mutate({ jobId: hiddenJob.job_id, hidden: false });
              setHiddenJob(null);
            }}
          />
        )}
        {hide.error && (
          <div className="mb-3">
            <Alert>Couldn't hide that job: {hide.error.message}</Alert>
          </div>
        )}
        {isPending ? (
          <SkeletonRows rows={6} label="Loading jobs" />
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
              <EmptyState icon={<Search className="size-5" />} title={savedOnly && savedCount === 0 ? "No saved jobs yet" : "Nothing matches these filters"}>
                Try clearing the search or loosening the filters.
              </EmptyState>
            )}
          </Card>
        ) : (
          <>
            <Card className="overflow-hidden">
              <ul>
                {visible.slice(0, limit).map((job) => (
                  <JobRow
                    key={job.job_id}
                    job={job}
                    isNew={isNewSince(job, lastVisit)}
                    onHide={() => hideJob(job)}
                    onToggleSave={() => save.mutate({ jobId: job.job_id, saved: job.status !== "SAVED" })}
                  />
                ))}
              </ul>
            </Card>
            <div className="mt-4 flex flex-col items-center gap-2">
              <p className="text-ink-3" aria-live="polite">
                Showing {Math.min(limit, visible.length)} of {visible.length}
              </p>
              {limit < visible.length && (
                <Button onClick={() => setParam("n", limit + PAGE_SIZE, PAGE_SIZE)}>
                  Show {Math.min(PAGE_SIZE, visible.length - limit)} more
                </Button>
              )}
            </div>
          </>
        )}
      </div>
    </>
  );
}

function FilterSelect({
  label,
  value,
  options,
  onChange,
}: {
  label: string;
  value: string;
  options: { value: string; label: string }[];
  onChange: (value: string) => void;
}) {
  return (
    <label className="flex h-8 items-center rounded-full border border-line bg-surface pl-3 text-ink-2 focus-within:border-accent">
      <span className="sr-only">{label}</span>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className={cx("h-full cursor-pointer rounded-full bg-transparent pr-2 font-medium focus:outline-none", value && value !== "0" && "text-accent-ink")}
      >
        {options.map((o) => (
          <option key={o.value} value={o.value}>
            {o.label}
          </option>
        ))}
      </select>
    </label>
  );
}

function JobRow({ job, isNew, onHide, onToggleSave }: { job: Job; isNew: boolean; onHide: () => void; onToggleSave: () => void }) {
  const saved = job.status === "SAVED";
  const pct = scorePercent(job.match_score);
  const why = matchSummary(job);
  const when = relativeTime(postedAt(job));

  return (
    <li
      className={cx(
        "flex flex-col gap-2 border-b border-line px-4 py-3.5 transition-colors last:border-b-0 hover:bg-subtle/60 sm:flex-row sm:items-center sm:gap-4 sm:px-5 sm:py-4",
        // The very best matches get a green edge so they stand out while scrolling.
        pct >= STRONG_MATCH && "shadow-[inset_3px_0_0_var(--color-ok)]",
      )}
    >
      <div className="flex min-w-0 flex-1 gap-3 sm:gap-4">
        <CompanyMark name={job.company} />
        {/* Phones: the score sits beside the title so the actions fit on one short row. */}
        <div className="order-last flex-none sm:hidden" aria-hidden>
          <ScoreRing pct={pct} size="sm" />
        </div>
        <div className="min-w-0 flex-1">
          <h2 className="flex flex-wrap items-center gap-x-2 text-sm font-semibold">
            <Link to={`/jobs/${encodeURIComponent(job.job_id)}`} className="hover:text-accent hover:underline">
              {job.title}
            </Link>
            {isNew && <Badge tone="accent">New</Badge>}
          </h2>
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
          {why && <p className="mt-1.5 line-clamp-2 text-ink-2 sm:line-clamp-none">{why}</p>}
        </div>
      </div>
      <div className="flex items-center gap-1 pl-13 sm:gap-4 sm:pl-0">
        <ScoreRing pct={pct} className="max-sm:sr-only" />
        <button type="button" onClick={onToggleSave} aria-pressed={saved} className={buttonClass("ghost", "md")} title={saved ? "Saved" : "Save for later"}>
          {saved ? <BookmarkCheck className="size-4 text-accent" aria-hidden /> : <Bookmark className="size-4" aria-hidden />}
          <span className="sr-only">
            {saved ? "Saved" : "Save"} {job.title} at {job.company}
          </span>
        </button>
        <button type="button" onClick={onHide} className={buttonClass("ghost", "md")} title="Not interested">
          <EyeOff className="size-4" aria-hidden />
          <span className="sr-only">Not interested in {job.title} at {job.company}</span>
        </button>
        <a href={job.url} target="_blank" rel="noopener noreferrer" className={buttonClass("ghost", "md", "max-md:hidden")} title="View posting">
          <ExternalLink className="size-4" aria-hidden />
          <span className="sr-only">View posting (opens in a new tab)</span>
        </a>
        <Link to={`/jobs/${encodeURIComponent(job.job_id)}`} className={buttonClass(pct >= 80 ? "primary" : "secondary", "md", "max-sm:ml-auto")}>
          Review
          <span className="sr-only"> {job.title} at {job.company}</span>
        </Link>
      </div>
    </li>
  );
}

/** After "Not interested": undo, and an optional reason that tunes new searches. */
function HiddenNotice({ job, onUndo }: { job: Job; onUndo: () => void }) {
  const why = useHideReason();
  const removeRule = useRemoveSkipRule();
  const answered = why.isSuccess;
  const rule = why.data?.rule ?? null;
  return (
    <div className="mb-3 rounded-md border border-line bg-surface px-4 py-2.5" role="status">
      <div className="flex items-center gap-3">
        <EyeOff className="size-4 flex-none text-ink-3" aria-hidden />
        <p className="min-w-0 flex-1 truncate">
          Hid <span className="font-medium">{job.title}</span>. It won't come back in new searches.
        </p>
        <button
          type="button"
          className="font-medium text-accent hover:underline"
          onClick={() => {
            if (rule) removeRule.mutate(rule.id);
            onUndo();
          }}
        >
          Undo
        </button>
      </div>
      {answered ? (
        <p className="mt-1.5 pl-7 text-ink-2">
          {rule ? (
            <>
              Got it. New searches will skip {rule.label.charAt(0).toLowerCase() + rule.label.slice(1)}. You can change this in{" "}
              <Link to="/profile" className="text-accent hover:underline">
                Profile
              </Link>
              .
            </>
          ) : (
            (why.data?.note ?? "Thanks, noted.")
          )}
        </p>
      ) : (
        <div className="mt-2 flex flex-wrap items-center gap-1.5 pl-7" role="group" aria-label="Why not? (optional)">
          <span className="mr-1 text-ink-3">Why not?</span>
          {HIDE_REASONS.map((r) => (
            <button
              key={r.value}
              type="button"
              disabled={why.isPending}
              onClick={() => why.mutate({ jobId: job.job_id, reason: r.value })}
              className="h-7 rounded-full border border-line px-2.5 text-xs font-medium text-ink-2 hover:bg-subtle disabled:opacity-60"
            >
              {r.label}
            </button>
          ))}
        </div>
      )}
      {why.error && <p className="mt-1.5 pl-7 text-danger">Couldn't save that: {why.error.message}</p>}
    </div>
  );
}

function FindNewJobsStatus({ search }: { search: ReturnType<typeof useFindNewJobs> }) {
  const found = search.data?.matched_and_saved ?? 0;
  if (search.isIdle) return null;
  return (
    <div className="mb-4">
      {search.isPending && <SearchProgress />}
      {search.isSuccess && (
        <p className="text-ink-2" role="status">
          {found > 0
            ? `Found ${found} new ${found === 1 ? "match" : "matches"}. They're marked New.`
            : "No new matches since the last check. We also check every hour."}
        </p>
      )}
      {search.error && <Alert tone="warn">{search.error.message}</Alert>}
    </div>
  );
}
