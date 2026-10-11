import { useMemo, type ReactNode } from "react";
import { Link, Navigate } from "react-router";
import { ArrowRight, BriefcaseBusiness, CalendarClock, Check, CircleAlert, MailQuestion, MapPin, PartyPopper, Sparkles, Wallet, X } from "lucide-react";
import { PageHeader } from "../components/AppShell";
import { Alert, Badge, Card, CompanyMark, EmptyState, ScoreRing, SkeletonRows, buttonClass, cx, lift } from "../components/ui";
import { useAuth } from "../lib/auth";
import { buildChecklist, markDone, useChecklistFlags } from "../lib/checklist";
import { isMatch, isNewSince, isTracked, matchSummary, readLastVisit, readableReason, scorePercent, useVisibleJobs, type Job } from "../lib/jobs";
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

function greeting(now: Date) {
  const h = now.getHours();
  return h < 12 ? "Good morning" : h < 18 ? "Good afternoon" : "Good evening";
}

export function HomePage() {
  const { user } = useAuth();
  const { data, isPending, error } = useVisibleJobs();
  const profile = useProfile();
  const now = useMemo(() => new Date(), []);
  const todos = useMemo(() => buildTodos(data ?? [], now), [data, now]);
  const firstName = user?.full_name?.trim().split(/\s+/)[0];

  const counts = useMemo(() => {
    const jobs = data ?? [];
    return [
      { label: "Matches", value: jobs.filter(isMatch).length, to: "/jobs" },
      { label: "Applied", value: jobs.filter((j) => ["SUBMITTED", "RESPONDED"].includes(j.status)).length, to: "/applications" },
      { label: "Interviewing", value: jobs.filter((j) => j.status === "INTERVIEW").length, to: "/applications" },
      { label: "Offers", value: jobs.filter((j) => j.status === "OFFER").length, to: "/applications" },
    ];
  }, [data]);

  const top = useMemo(
    () =>
      (data ?? [])
        .filter(isMatch)
        .sort((a, b) => b.match_score - a.match_score)
        .slice(0, 5),
    [data],
  );

  // First run: no resume on file yet. Send the user to setup unless they postponed it.
  const needsSetup = profile.isSuccess && profileNeedsSetup(profile.data);
  if (needsSetup && !setupLater.get()) return <Navigate to="/setup" replace />;

  return (
    <>
      <PageHeader title={firstName ? `${greeting(now)}, ${firstName}` : greeting(now)} tabTitle="Home" />
      <div className="mx-auto flex max-w-6xl flex-col gap-6 px-4 py-5 md:px-7 md:py-8">
        {isPending ? (
          <>
            <SkeletonRows rows={2} avatar={false} label="Loading your dashboard" />
            <SkeletonRows rows={3} label="Loading your matches" />
          </>
        ) : error ? (
          <Alert>Couldn't load your dashboard: {error.message}</Alert>
        ) : needsSetup ? (
          // Without a resume there's nothing to show yet; an "all caught up" state would mislead.
          <SetupReminder />
        ) : (
          <>
            <GettingStarted jobs={data ?? []} />
            {/* Wide screens: matches on the left, what needs you and your numbers on the right.
                Phones: one column, in the order the `order-*` classes give. */}
            <div className="flex flex-col gap-6 lg:grid lg:grid-cols-[minmax(0,1fr)_21rem] lg:items-start">
              <div className="contents lg:flex lg:min-w-0 lg:flex-col lg:gap-6">
                {top[0] && <BestMatch job={top[0]} />}
                <TopMatches jobs={top.slice(1)} />
              </div>
              <div className="contents lg:flex lg:flex-col lg:gap-6">
                <section aria-labelledby="today" className="order-2">
                  <h2 id="today" className="mb-3 font-display text-base font-semibold">
                    Today
                  </h2>
                  <Card>
                    {todos.length === 0 ? (
                      <EmptyState icon={<PartyPopper className="size-5" />} title="You're all caught up">
                        Nothing needs you right now. New matches and replies will show up here.
                      </EmptyState>
                    ) : (
                      <ul>
                        {todos.map((t) => (
                          <li key={t.key} className="flex items-center gap-3 border-b border-line px-4 py-3.5 last:border-b-0">
                            <span className={cx("size-2 flex-none rounded-full", t.dot)} aria-hidden />
                            <div className="min-w-0 flex-1">
                              <p className="font-semibold">{t.title}</p>
                              {t.detail && <p className="truncate text-ink-2">{t.detail}</p>}
                            </div>
                            <Link to={t.to} className={buttonClass("secondary", "sm")}>
                              {t.cta}
                              <ArrowRight className="size-3.5" aria-hidden />
                            </Link>
                          </li>
                        ))}
                      </ul>
                    )}
                  </Card>
                </section>

                <section aria-labelledby="pipeline" className="order-4">
                  <h2 id="pipeline" className="mb-3 font-display text-base font-semibold">
                    Your search
                  </h2>
                  <div className="grid grid-cols-2 gap-3 sm:grid-cols-4 lg:grid-cols-2">
                    {counts.map((c) => (
                      <Link key={c.label} to={c.to} className={cx("rounded-lg border border-line bg-surface p-4 shadow-card", lift)}>
                        <span className="block font-display text-2xl font-semibold">{c.value}</span>
                        <span className="text-ink-2">{c.label}</span>
                      </Link>
                    ))}
                  </div>
                </section>
              </div>
            </div>
          </>
        )}
      </div>
    </>
  );
}

/** The single best match, big enough to act on straight from Home. */
function BestMatch({ job }: { job: Job }) {
  const pct = scorePercent(job.match_score);
  const reasons = job.match_reasons.filter((r) => r.trim()).slice(0, 3);
  const missing = job.missing_skills.filter((s) => s.trim()).slice(0, 4);
  return (
    <section aria-labelledby="best-match" className="order-1">
      <div className="relative overflow-hidden rounded-lg border border-accent/25 bg-linear-to-br from-accent-soft/70 via-surface via-45% to-spark-soft/70 p-5 shadow-card sm:p-6">
        <p id="best-match" className="mb-4 flex items-center gap-1.5 text-xs font-semibold tracking-wide text-spark-ink uppercase">
          <Sparkles className="size-3.5" aria-hidden />
          Your best match right now
        </p>
        <div className="flex items-start gap-4">
          <CompanyMark name={job.company} size="lg" />
          <div className="min-w-0 flex-1">
            <h2 className="font-display text-lg leading-tight font-semibold sm:text-xl">{job.title}</h2>
            <div className="mt-1.5 flex flex-wrap gap-x-3 gap-y-0.5 text-ink-2">
              <span className="font-medium text-ink">{job.company}</span>
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
            </div>
          </div>
          <ScoreRing pct={pct} size="lg" className="max-sm:hidden" />
        </div>
        {(reasons.length > 0 || missing.length > 0) && (
          <div className="mt-4 flex flex-col gap-2">
            {reasons.length > 0 && (
              <ul className="flex flex-col gap-1.5">
                {reasons.map((r) => (
                  <li key={r} className="flex gap-2">
                    <Check className="mt-0.5 size-4 flex-none text-ok" aria-hidden />
                    {readableReason(r)}
                  </li>
                ))}
              </ul>
            )}
            {missing.length > 0 && (
              <p className="flex flex-wrap items-center gap-1.5 text-ink-2">
                Not on your resume:
                {missing.map((m) => (
                  <Badge key={m} tone="warn">
                    {m}
                  </Badge>
                ))}
              </p>
            )}
          </div>
        )}
        <div className="mt-5 flex flex-wrap items-center gap-3">
          <ScoreRing pct={pct} size="md" className="sm:hidden" />
          <Link to={`/jobs/${encodeURIComponent(job.job_id)}`} className={buttonClass("primary", "lg")}>
            Review this job
            <ArrowRight className="size-4" aria-hidden />
          </Link>
          <Link to="/jobs" className={buttonClass("ghost", "lg", "max-sm:hidden")}>
            See all matches
          </Link>
        </div>
      </div>
    </section>
  );
}

/** The next few matches, so Home answers "what else should I look at?" without a click. */
function TopMatches({ jobs }: { jobs: Job[] }) {
  if (!jobs.length) return null;

  return (
    <section aria-labelledby="top-matches" className="order-3">
      <div className="mb-3 flex items-center justify-between gap-3">
        <h2 id="top-matches" className="font-display text-base font-semibold">
          More top matches
        </h2>
        <Link to="/jobs" className="text-sm font-medium text-accent hover:underline">
          All jobs
        </Link>
      </div>
      <Card className="overflow-hidden">
        <ul>
          {jobs.map((j) => {
            const pct = scorePercent(j.match_score);
            const why = matchSummary(j);
            return (
              <li key={j.job_id} className="flex items-center gap-3 border-b border-line px-4 py-3.5 transition-colors last:border-b-0 hover:bg-subtle/60 sm:px-5">
                <CompanyMark name={j.company} />
                <div className="min-w-0 flex-1">
                  <p className="truncate font-semibold">{j.title}</p>
                  <p className="truncate text-ink-2">
                    {j.company}
                    {j.location && ` · ${j.location}`}
                  </p>
                  {why && <p className="truncate text-xs text-ink-3">{why}</p>}
                </div>
                <ScoreRing pct={pct} size="sm" />
                <Link to={`/jobs/${encodeURIComponent(j.job_id)}`} className={buttonClass("secondary", "sm")}>
                  Review
                  <span className="sr-only">
                    {" "}
                    {j.title} at {j.company}
                  </span>
                </Link>
              </li>
            );
          })}
        </ul>
      </Card>
    </section>
  );
}

/** First steps, until they're all done or dismissed. */
function GettingStarted({ jobs }: { jobs: Job[] }) {
  const flags = useChecklistFlags();
  const steps = buildChecklist({ hasResume: true, hasTracked: jobs.some(isTracked), flags });
  const done = steps.filter((s) => s.done).length;
  if (flags.dismissed || done === steps.length) return null;

  const next = steps.find((s) => !s.done);
  if (!next) return null;

  return (
    <section
      aria-labelledby="getting-started"
      className="flex flex-wrap items-center gap-x-4 gap-y-2 rounded-lg border border-line bg-surface px-4 py-2.5 shadow-card"
    >
      <h2 id="getting-started" className="flex items-center gap-2.5 font-semibold max-sm:basis-full">
        Getting started
        <span className="h-1.5 w-20 overflow-hidden rounded-full bg-subtle" aria-hidden>
          <span className="block h-full rounded-full bg-accent" style={{ width: `${(done / steps.length) * 100}%` }} />
        </span>
        <span className="font-normal text-ink-3">
          {done} of {steps.length} done
        </span>
      </h2>
      <p className="flex min-w-0 flex-1 items-center gap-2 text-ink-2">
        <span className="max-sm:sr-only">Next:</span>
        <span className="truncate">{next.title}</span>
      </p>
      <Link to={next.to} className={buttonClass("secondary", "sm")}>
        {next.cta}
        <span className="sr-only">: {next.title}</span>
      </Link>
      <button type="button" onClick={() => markDone("dismissed")} className="flex items-center gap-1 text-sm text-ink-3 hover:text-ink">
        <X className="size-3.5" aria-hidden />
        Hide
      </button>
    </section>
  );
}
