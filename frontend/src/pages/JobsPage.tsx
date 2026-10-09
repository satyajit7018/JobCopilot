import { useMemo, useState } from "react";
import { Bookmark, BookmarkCheck, BriefcaseBusiness, Clock, ExternalLink, EyeOff, MapPin, RefreshCw, Search, Wallet } from "lucide-react";
import { PageHeader } from "../components/AppShell";
import { SearchProgress } from "../components/SearchProgress";
import { Alert, Badge, Button, Card, CompanyMark, EmptyState, Spinner, buttonClass, cx, toneText } from "../components/ui";
import { Link } from "react-router";
import {
  REGION_LABELS,
  isMatch,
  isNewSince,
  isRemote,
  jobRegions,
  matchSummary,
  relativeTime,
  scorePercent,
  scoreTone,
  useFindNewJobs,
  useLastVisit,
  useSetMatchHidden,
  useSetMatchSaved,
  useVisibleJobs,
  type Job,
  type Region,
} from "../lib/jobs";

type Sort = "match" | "newest";

/** How many jobs to show at once; the rest sit behind "Show more". */
const PAGE_SIZE = 20;

function postedAt(job: Job) {
  return job.posted_date ?? job.created_at;
}

export function JobsPage() {
  const { data, isPending, error, refetch, hiddenMatches: hidden } = useVisibleJobs();
  const [sort, setSort] = useState<Sort>("match");
  const [remoteOnly, setRemoteOnly] = useState(false);
  const [savedOnly, setSavedOnly] = useState(false);
  const [query, setQuery] = useState("");
  const [region, setRegion] = useState<Region | "">("");
  const [minMatch, setMinMatch] = useState(0);
  const lastVisit = useLastVisit("jobs");
  const hide = useSetMatchHidden();
  const [hiddenJob, setHiddenJob] = useState<Job | null>(null);
  const findNew = useFindNewJobs();
  // Changing a filter or the sort starts again from the first page.
  const filterKey = `${sort}|${remoteOnly}|${savedOnly}|${query}|${region}|${minMatch}`;
  const [page, setPage] = useState({ key: filterKey, limit: PAGE_SIZE });
  const limit = page.key === filterKey ? page.limit : PAGE_SIZE;

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
          <Chip on={savedOnly} onClick={() => setSavedOnly((v) => !v)}>
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

        <FindNewJobs search={findNew} />
        {hiddenJob && (
          <div className="mb-3 flex items-center gap-3 rounded-md border border-line bg-surface px-4 py-2.5" role="status">
            <EyeOff className="size-4 flex-none text-ink-3" aria-hidden />
            <p className="min-w-0 flex-1 truncate">
              Hid <span className="font-medium">{hiddenJob.title}</span>. It won't come back in new searches.
            </p>
            <button
              type="button"
              className="font-medium text-accent hover:underline"
              onClick={() => {
                hide.mutate({ jobId: hiddenJob.job_id, hidden: false });
                setHiddenJob(null);
              }}
            >
              Undo
            </button>
          </div>
        )}
        {hide.error && (
          <div className="mb-3">
            <Alert>Couldn't hide that job: {hide.error.message}</Alert>
          </div>
        )}
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
                <Button onClick={() => setPage({ key: filterKey, limit: limit + PAGE_SIZE })}>
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
  const tone = scoreTone(pct);
  const why = matchSummary(job);
  const when = relativeTime(postedAt(job));

  return (
    <li className="flex flex-col gap-3 border-b border-line px-4 py-4 last:border-b-0 sm:flex-row sm:items-center sm:gap-4 sm:px-5">
      <div className="flex min-w-0 flex-1 gap-3 sm:gap-4">
        <CompanyMark name={job.company} />
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
          {why && <p className="mt-1.5 text-ink-2">{why}</p>}
        </div>
      </div>
      <div className="flex items-center gap-4 pl-13 sm:pl-0">
        <div className="w-14 text-center" aria-label={`${pct}% match`}>
          <span className={cx("block text-lg leading-none font-bold", toneText[tone])}>{pct}</span>
          <span className="text-xs tracking-wide text-ink-3 uppercase">match</span>
        </div>
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
        <Link to={`/jobs/${encodeURIComponent(job.job_id)}`} className={buttonClass(pct >= 80 ? "primary" : "secondary")}>
          Review
          <span className="sr-only"> {job.title} at {job.company}</span>
        </Link>
      </div>
    </li>
  );
}

function FindNewJobs({ search }: { search: ReturnType<typeof useFindNewJobs> }) {
  const found = search.data?.matched_and_saved ?? 0;
  return (
    <div className="mb-4 flex flex-col gap-2">
      <div className="flex flex-wrap items-center gap-3">
        <Button loading={search.isPending} onClick={() => search.mutate()}>
          <RefreshCw className="size-4" aria-hidden />
          Find new jobs
        </Button>
        <p className="text-ink-3">We also check for new jobs every hour.</p>
      </div>
      {search.isPending && <SearchProgress />}
      {search.isSuccess && (
        <p className="text-ink-2" role="status">
          {found > 0 ? `Found ${found} new ${found === 1 ? "match" : "matches"}. They're marked New.` : "No new matches since the last check."}
        </p>
      )}
      {search.error && <Alert tone="warn">{search.error.message}</Alert>}
    </div>
  );
}
