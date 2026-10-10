import { useMemo, type ReactNode } from "react";
import { Link, Navigate } from "react-router";
import { ArrowRight, BriefcaseBusiness, CalendarClock, Check, CircleAlert, MailQuestion, PartyPopper, X } from "lucide-react";
import { PageHeader } from "../components/AppShell";
import { Alert, Card, CompanyMark, EmptyState, Spinner, buttonClass, cx, toneText } from "../components/ui";
import { useAuth } from "../lib/auth";
import { buildChecklist, markDone, useChecklistFlags } from "../lib/checklist";
import { isMatch, isNewSince, isTracked, matchSummary, readLastVisit, scorePercent, scoreTone, useVisibleJobs, type Job } from "../lib/jobs";
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

  // First run: no resume on file yet. Send the user to setup unless they postponed it.
  const needsSetup = profile.isSuccess && profileNeedsSetup(profile.data);
  if (needsSetup && !setupLater.get()) return <Navigate to="/setup" replace />;

  return (
    <>
      <PageHeader title={firstName ? `${greeting(now)}, ${firstName}` : greeting(now)} />
      <div className="mx-auto flex max-w-3xl flex-col gap-6 px-4 py-5 md:px-7 md:py-8">
        {isPending ? (
          <Spinner />
        ) : error ? (
          <Alert>Couldn't load your dashboard: {error.message}</Alert>
        ) : needsSetup ? (
          // Without a resume there's nothing to show yet; an "all caught up" state would mislead.
          <SetupReminder />
        ) : (
          <>
            <GettingStarted jobs={data ?? []} />
            <section aria-labelledby="today">
              <h2 id="today" className="mb-3 text-base font-semibold">
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
                      <li key={t.key} className="flex items-center gap-3 border-b border-line px-4 py-3.5 last:border-b-0 sm:px-5">
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

            <TopMatches jobs={data ?? []} />

            <section aria-labelledby="pipeline">
              <h2 id="pipeline" className="mb-3 text-base font-semibold">
                Your search
              </h2>
              <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                {counts.map((c) => (
                  <Link key={c.label} to={c.to} className="rounded-lg border border-line bg-surface p-4 shadow-card hover:border-line-strong">
                    <span className="block text-xl font-semibold">{c.value}</span>
                    <span className="text-ink-2">{c.label}</span>
                  </Link>
                ))}
              </div>
            </section>
          </>
        )}
      </div>
    </>
  );
}

/** The best few new matches, so Home answers "what should I look at?" without a click. */
function TopMatches({ jobs }: { jobs: Job[] }) {
  const top = useMemo(
    () =>
      jobs
        .filter(isMatch)
        .sort((a, b) => b.match_score - a.match_score)
        .slice(0, 3),
    [jobs],
  );
  if (!top.length) return null;

  return (
    <section aria-labelledby="top-matches">
      <div className="mb-3 flex items-center justify-between gap-3">
        <h2 id="top-matches" className="text-base font-semibold">
          Top matches
        </h2>
        <Link to="/jobs" className="text-sm font-medium text-accent hover:underline">
          All jobs
        </Link>
      </div>
      <Card>
        <ul>
          {top.map((j) => {
            const pct = scorePercent(j.match_score);
            const why = matchSummary(j);
            return (
              <li key={j.job_id} className="flex items-center gap-3 border-b border-line px-4 py-3.5 last:border-b-0 sm:px-5">
                <CompanyMark name={j.company} size="sm" />
                <div className="min-w-0 flex-1">
                  <p className="truncate font-semibold">{j.title}</p>
                  <p className="truncate text-ink-2">
                    {j.company}
                    {j.location && ` · ${j.location}`}
                  </p>
                  {why && <p className="truncate text-xs text-ink-3">{why}</p>}
                </div>
                <span className={cx("w-10 text-right text-base font-bold", toneText[scoreTone(pct)])} aria-label={`${pct}% match`}>
                  {pct}
                </span>
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

  return (
    <section aria-labelledby="getting-started">
      <div className="mb-3 flex items-center justify-between gap-3">
        <h2 id="getting-started" className="text-base font-semibold">
          Getting started <span className="font-normal text-ink-3">· {done} of {steps.length} done</span>
        </h2>
        <button type="button" onClick={() => markDone("dismissed")} className="flex items-center gap-1 text-sm text-ink-3 hover:text-ink">
          <X className="size-3.5" aria-hidden />
          Hide
        </button>
      </div>
      <Card>
        <div className="h-1 overflow-hidden rounded-t-lg bg-subtle" aria-hidden>
          <div className="h-full bg-accent" style={{ width: `${(done / steps.length) * 100}%` }} />
        </div>
        <ol>
          {steps.filter((s) => !s.done).map((s) => (
            <li key={s.key} className="flex items-center gap-3 border-b border-line px-4 py-3 last:border-b-0 sm:px-5">
              <span
                className={cx(
                  "grid size-5 flex-none place-items-center rounded-full border",
                  s.done ? "border-ok bg-ok text-white" : "border-line-strong",
                )}
                aria-hidden
              >
                {s.done && <Check className="size-3" />}
              </span>
              <span className={cx("flex-1", s.done && "text-ink-3 line-through")}>
                {s.title}
                <span className="sr-only">{s.done ? " (done)" : " (to do)"}</span>
              </span>
              {!s.done && (
                <Link to={s.to} className={buttonClass("secondary", "sm")}>
                  {s.cta}
                </Link>
              )}
            </li>
          ))}
        </ol>
      </Card>
    </section>
  );
}
