import { useMemo, type ReactNode } from "react";
import { Link, Navigate } from "react-router";
import { BriefcaseBusiness, CalendarClock, ChevronRight, CircleAlert, MailQuestion, X } from "lucide-react";
import { PageHeader } from "../components/AppShell";
import { MatchReceipt } from "../components/MatchReceipt";
import { Alert, Card, CompanyMark, Group, ScoreRing, SkeletonRows, buttonClass, cx, rowClass } from "../components/ui";
import { buildChecklist, markDone, useChecklistFlags } from "../lib/checklist";
import { isMatch, isNewSince, isTracked, readLastVisit, relativeTime, scorePercent, useSearchStatus, useVisibleJobs, type Job } from "../lib/jobs";
import { needsSetup as profileNeedsSetup, setupLater, useProfile } from "../lib/profile";
import { SetupReminder } from "./SetupPage";

const FOLLOW_UP_DAYS = 7;

interface Todo {
  key: string;
  icon: ReactNode;
  dot: string;
  title: string;
  detail: string;
  to: string;
  cta: string;
}

/** Turns the job list into the handful of things that need the user today. */
export function buildTodos(jobs: Job[], now: Date = new Date()): Todo[] {
  const todos: Todo[] = [];

  for (const j of jobs) {
    if (j.status === "INTERVIEW" && j.interview_date) {
      const at = new Date(j.interview_date);
      if (!Number.isNaN(at.getTime()) && at >= now) {
        todos.push({
          key: `iv-${j.job_id}`,
          icon: <CalendarClock className="size-4" />,
          dot: "bg-info",
          title: `Interview ${at.toLocaleString(undefined, { weekday: "short", hour: "numeric", minute: "2-digit" })}`,
          detail: `${j.company} · ${j.title}`,
          to: `/prep?job=${encodeURIComponent(j.job_id)}`,
          cta: "Prepare",
        });
      }
    }
  }

  const blocked = jobs.filter((j) => j.status === "HITL_REQUIRED" || j.status === "NEEDS_REVIEW");
  if (blocked.length) {
    todos.push({
      key: "blocked",
      icon: <CircleAlert className="size-4" />,
      dot: "bg-warn",
      title: blocked.length === 1 ? "1 application needs you" : `${blocked.length} applications need you`,
      detail: blocked
        .slice(0, 2)
        .map((j) => j.company)
        .join(", "),
      to: "/applications",
      cta: "Review",
    });
  }

  const cutoff = now.getTime() - FOLLOW_UP_DAYS * 86_400_000;
  const quiet = jobs.filter((j) => j.status === "SUBMITTED" && j.applied_at && new Date(j.applied_at).getTime() < cutoff);
  if (quiet.length) {
    todos.push({
      key: "follow-up",
      icon: <MailQuestion className="size-4" />,
      dot: "bg-warn",
      title: quiet.length === 1 ? `Follow up with ${quiet[0].company}` : `Follow up on ${quiet.length} applications`,
      detail: `No reply in ${FOLLOW_UP_DAYS}+ days`,
      to: quiet.length === 1 ? `/applications/${encodeURIComponent(quiet[0].job_id)}` : "/applications",
      cta: "View",
    });
  }

  const since = readLastVisit("jobs");
  const fresh = since === null ? [] : jobs.filter((j) => isMatch(j) && isNewSince(j, since));
  if (fresh.length) {
    todos.push({
      key: "new",
      icon: <BriefcaseBusiness className="size-4" />,
      dot: "bg-accent",
      title: fresh.length === 1 ? "1 new match since your last visit" : `${fresh.length} new matches since your last visit`,
      detail: fresh
        .slice(0, 2)
        .map((j) => j.company)
        .join(", "),
      to: "/jobs",
      cta: "See new",
    });
  }

  const strong = jobs.filter((j) => isMatch(j) && scorePercent(j.match_score) >= 80);
  if (strong.length) {
    todos.push({
      key: "matches",
      icon: <BriefcaseBusiness className="size-4" />,
      dot: "bg-accent",
      title: strong.length === 1 ? "1 strong match to look at" : `${strong.length} strong matches to look at`,
      detail: "80% match or better",
      to: "/jobs",
      cta: "See jobs",
    });
  }

  return todos;
}

/** Things that need the person (not just "there are matches"): shown under "Needs you". */
const NEEDS_YOU = (t: Todo) => t.key.startsWith("iv-") || t.key === "blocked" || t.key === "follow-up";

export function HomePage() {
  const { data, isPending, error } = useVisibleJobs();
  const profile = useProfile();
  const now = useMemo(() => new Date(), []);
  const jobs = useMemo(() => data ?? [], [data]);
  const needsYou = useMemo(() => buildTodos(jobs, now).filter(NEEDS_YOU), [jobs, now]);

  const numbers = useMemo(
    () => [
      { label: "Matches", value: jobs.filter(isMatch).length, to: "/jobs" },
      { label: "Applied", value: jobs.filter((j) => ["SUBMITTED", "RESPONDED"].includes(j.status)).length, to: "/applications" },
      { label: "Interviewing", value: jobs.filter((j) => j.status === "INTERVIEW").length, to: "/applications" },
    ],
    [jobs],
  );
  const top = useMemo(
    () =>
      jobs
        .filter(isMatch)
        .sort((a, b) => b.match_score - a.match_score)
        .slice(0, 7),
    [jobs],
  );

  // First run: no resume on file yet. Send the user to setup unless they postponed it.
  const needsSetup = profile.isSuccess && profileNeedsSetup(profile.data);
  if (needsSetup && !setupLater.get()) return <Navigate to="/setup" replace />;

  const date = now.toLocaleDateString(undefined, { weekday: "long", day: "numeric", month: "long" });

  return (
    <>
      <PageHeader title="Today" eyebrow={date} subtitle={<ScanLine jobs={jobs} />} />
      <div className="mx-auto flex max-w-5xl flex-col gap-8 px-4 py-5 md:px-7 md:py-7">
        {isPending ? (
          <>
            <SkeletonRows rows={2} avatar={false} label="Loading today" />
            <SkeletonRows rows={3} label="Loading your matches" />
          </>
        ) : error ? (
          <Alert>Couldn't load today: {error.message}</Alert>
        ) : needsSetup ? (
          // Without a resume there's nothing to show yet; an "all caught up" state would mislead.
          <SetupReminder />
        ) : (
          <>
            {/* Wide screens: the best match on the left, what needs you and your numbers on
                the right. Phones: one column, in the order the `order-*` classes give. */}
            <div className="flex flex-col gap-8 lg:grid lg:grid-cols-[minmax(0,2fr)_minmax(0,1fr)] lg:items-start lg:gap-6">
              <div className="contents lg:block">
                {top[0] ? <BestMatch job={top[0]} /> : <NoMatchesYet />}
              </div>
              <div className="contents lg:flex lg:flex-col lg:gap-6">
                <GettingStarted jobs={jobs} />
                {needsYou.length > 0 && (
                  <Group label="Needs you" className="order-1">
                    <ul>
                      {needsYou.map((t) => (
                        <li key={t.key} className={cx(rowClass, "after:left-4")}>
                          <span className={cx("size-2 flex-none rounded-full", t.dot)} aria-hidden />
                          <div className="min-w-0 flex-1">
                            <p className="font-semibold">{t.title}</p>
                            {t.detail && <p className="truncate text-xs text-ink-2">{t.detail}</p>}
                          </div>
                          <Link to={t.to} className={buttonClass("secondary", "sm")}>
                            {t.cta}
                          </Link>
                        </li>
                      ))}
                    </ul>
                  </Group>
                )}
                <Group label="Your search" className="order-4">
                  <ul>
                    {numbers.map((n) => (
                      <li key={n.label}>
                        <Link to={n.to} className={cx(rowClass, "min-h-12 after:left-4 hover:bg-subtle/50")}>
                          <span className="flex-1">{n.label}</span>
                          <span className="font-semibold tabular-nums">{n.value}</span>
                          <ChevronRight className="size-4 text-ink-3" aria-hidden />
                        </Link>
                      </li>
                    ))}
                  </ul>
                </Group>
              </div>
            </div>

            <UpNext jobs={top.slice(1)} />
          </>
        )}
      </div>
    </>
  );
}

/** "Checked 4,048 postings 12m ago · 3 new for you": the hourly check, made visible. */
function ScanLine({ jobs }: { jobs: Job[] }) {
  const { data } = useSearchStatus();
  const since = readLastVisit("jobs");
  const fresh = since === null ? 0 : jobs.filter((j) => isMatch(j) && isNewSince(j, since)).length;
  const read = data?.last_read;
  const when = read ? relativeTime(read.at) : null;
  if (!read || !when) return fresh > 0 ? <>{fresh} new for you</> : null;
  return (
    <span className="inline-flex flex-wrap items-center gap-x-1.5">
      <span className={cx("size-1.5 rounded-full bg-accent", data?.is_running && "animate-pulse motion-reduce:animate-none")} aria-hidden />
      {data?.is_running ? "Checking for new jobs now" : `Checked ${read.postings.toLocaleString()} postings ${when}`}
      {fresh > 0 && (
        <>
          <span aria-hidden>·</span>
          <Link to="/jobs" className="font-medium text-accent hover:underline">
            {fresh} new for you
          </Link>
        </>
      )}
    </span>
  );
}

const HERO_DRAWN_KEY = "jobcopilot_hero_drawn";

/** The hero's ring draws itself once a day, or whenever the best match is a new one. */
function shouldDraw(job: Job): boolean {
  const today = new Date().toDateString();
  try {
    const seen = sessionStorage.getItem(HERO_DRAWN_KEY);
    sessionStorage.setItem(HERO_DRAWN_KEY, `${today}|${job.job_id}`);
    return seen !== `${today}|${job.job_id}`;
  } catch {
    return false;
  }
}

/** The single best match, big enough to act on straight from Today. */
function BestMatch({ job }: { job: Job }) {
  const pct = scorePercent(job.match_score);
  const draw = useMemo(() => shouldDraw(job), [job.job_id]); // eslint-disable-line react-hooks/exhaustive-deps
  const meta = [job.company, job.location, job.salary_range].filter(Boolean).join(" · ");
  return (
    <section aria-labelledby="best-match" className="order-2 rounded-xl bg-surface p-5 sm:p-7">
      <p id="best-match" className="mb-4 text-xs text-ink-2">
        Best match for you
      </p>
      <div className="flex items-center gap-4 sm:gap-5">
        <ScoreRing pct={pct} size="lg" draw={draw} />
        <div className="min-w-0 flex-1">
          <h2 className="text-lg leading-tight font-bold">{job.title}</h2>
          <p className="mt-1 text-ink-2">{meta}</p>
        </div>
        <CompanyMark name={job.company} size="lg" />
      </div>
      <MatchReceipt job={job} max={3} className="mt-5" />
      <div className="mt-6 flex flex-wrap items-center gap-3">
        <Link to={`/jobs/${encodeURIComponent(job.job_id)}`} className={buttonClass("primary", "lg", "max-sm:w-full")}>
          Review
          <span className="sr-only">
            {" "}
            {job.title} at {job.company}
          </span>
        </Link>
        <Link to="/jobs" className={buttonClass("ghost", "lg", "text-accent max-sm:hidden")}>
          See all matches
        </Link>
      </div>
    </section>
  );
}

function NoMatchesYet() {
  return (
    <Card className="order-2 rounded-xl p-6">
      <BriefcaseBusiness className="mb-3 size-7 text-accent" aria-hidden />
      <h2 className="text-base font-semibold">No matches yet</h2>
      <p className="mt-1 max-w-md text-ink-2">We check for new jobs every hour and score each one against your resume. The best one will show up here.</p>
      <Link to="/jobs" className={buttonClass("secondary", "md", "mt-4")}>
        Search now
      </Link>
    </Card>
  );
}

/** The next few matches: a grouped list on phones, a grid of cards on wide screens. */
function UpNext({ jobs }: { jobs: Job[] }) {
  if (!jobs.length) return null;
  return (
    <section aria-labelledby="up-next">
      <div className="mb-2 flex items-center justify-between gap-3 px-1">
        <h2 id="up-next" className="text-xs font-normal text-ink-2">
          Up next
        </h2>
        <Link to="/jobs" className="font-medium text-accent hover:underline">
          See all
        </Link>
      </div>
      <ul className="overflow-hidden rounded-lg bg-surface lg:grid lg:grid-cols-2 lg:gap-3 lg:overflow-visible lg:rounded-none lg:bg-transparent">
        {jobs.map((j) => (
          <li
            key={j.job_id}
            className={cx(rowClass, "transition-colors hover:bg-subtle/50 lg:rounded-lg lg:bg-surface lg:py-3.5 lg:after:hidden lg:hover:bg-surface lg:hover:shadow-pop")}
          >
            <CompanyMark name={j.company} />
            <div className="min-w-0 flex-1">
              <p className="truncate font-semibold">
                <Link to={`/jobs/${encodeURIComponent(j.job_id)}`} className="after:absolute after:inset-0">
                  {j.title}
                </Link>
              </p>
              <p className="truncate text-xs text-ink-2">
                {j.company}
                {j.location && ` · ${j.location}`}
              </p>
            </div>
            <ScoreRing pct={scorePercent(j.match_score)} size="sm" />
          </li>
        ))}
      </ul>
    </section>
  );
}

/** First steps, as one quiet row until they're all done or dismissed. */
function GettingStarted({ jobs }: { jobs: Job[] }) {
  const flags = useChecklistFlags();
  const steps = buildChecklist({ hasResume: true, hasTracked: jobs.some(isTracked), flags });
  const done = steps.filter((s) => s.done).length;
  if (flags.dismissed || done === steps.length) return null;
  const next = steps.find((s) => !s.done);
  if (!next) return null;

  return (
    <section aria-labelledby="getting-started" className="order-3 rounded-lg bg-surface px-4 py-3.5">
      <div className="flex items-center justify-between gap-3">
        <h2 id="getting-started" className="text-xs font-normal whitespace-nowrap text-ink-2">
          Getting started · {done} of {steps.length} done
        </h2>
        <button type="button" onClick={() => markDone("dismissed")} className="flex items-center gap-1 text-xs text-ink-3 hover:text-ink">
          <X className="size-3.5" aria-hidden />
          Hide
        </button>
      </div>
      <div className="mt-2 flex items-center gap-3">
        <p className="min-w-0 flex-1 font-semibold">{next.title}</p>
        <Link to={next.to} className={buttonClass("secondary", "sm")}>
          {next.cta}
          <span className="sr-only">: {next.title}</span>
        </Link>
      </div>
    </section>
  );
}
