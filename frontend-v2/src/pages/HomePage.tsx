import { useMemo, type ReactNode } from "react";
import { Link } from "react-router";
import { ArrowRight, BriefcaseBusiness, CalendarClock, CircleAlert, MailQuestion, PartyPopper } from "lucide-react";
import { PageHeader } from "../components/AppShell";
import { Alert, Card, EmptyState, Spinner, buttonClass, cx } from "../components/ui";
import { useAuth } from "../lib/auth";
import { isMatch, scorePercent, useJobs, type Job } from "../lib/jobs";

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
          to: "/prep",
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
      to: "/applications",
      cta: "View",
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
  const { data, isPending, error } = useJobs();
  const now = useMemo(() => new Date(), []);
  const todos = useMemo(() => buildTodos(data ?? [], now), [data, now]);
  const firstName = user?.full_name?.trim().split(/\s+/)[0];

  const counts = useMemo(() => {
    const jobs = data ?? [];
    return [
      { label: "New matches", value: jobs.filter(isMatch).length, to: "/jobs" },
      { label: "Applied", value: jobs.filter((j) => ["SUBMITTED", "RESPONDED"].includes(j.status)).length, to: "/applications" },
      { label: "Interviewing", value: jobs.filter((j) => j.status === "INTERVIEW").length, to: "/applications" },
      { label: "Offers", value: jobs.filter((j) => j.status === "OFFER").length, to: "/applications" },
    ];
  }, [data]);

  return (
    <>
      <PageHeader title={firstName ? `${greeting(now)}, ${firstName}` : greeting(now)} />
      <div className="mx-auto flex max-w-3xl flex-col gap-6 px-4 py-5 md:px-7 md:py-8">
        {isPending ? (
          <Spinner />
        ) : error ? (
          <Alert>Couldn't load your dashboard: {error.message}</Alert>
        ) : (
          <>
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
