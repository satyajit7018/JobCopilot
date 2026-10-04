import { useState, type ReactNode } from "react";
import { Link, Navigate, useParams } from "react-router";
import { ArrowLeft, CalendarClock, Check, ExternalLink, Mail, SearchX } from "lucide-react";
import { PageHeader } from "../components/AppShell";
import { Alert, Badge, Button, Card, CompanyMark, CopyButton, EmptyState, Field, Select, Spinner, buttonClass, cx } from "../components/ui";
import {
  INTENT_META,
  MANUAL_STATUSES,
  buildTimeline,
  daysSince,
  parseLpa,
  useCounterOffer,
  useEmails,
  useEvaluateOffer,
  useFollowUpDraft,
  useLedger,
  useSetStatus,
  type Email,
} from "../lib/application";
import { STATUS_META, relativeTime, useJobs, type ApplicationStatus, type Job, type Tone } from "../lib/jobs";
import { useProfile } from "../lib/profile";

const FOLLOW_UP_AFTER_DAYS = 7;

const DOT: Record<Tone, string> = {
  neutral: "bg-line-strong",
  accent: "bg-accent",
  ok: "bg-ok",
  warn: "bg-warn",
  info: "bg-info",
  danger: "bg-danger",
};

function Section({ title, action, children }: { title: string; action?: ReactNode; children: ReactNode }) {
  const id = `sec-${title.toLowerCase().replace(/\W+/g, "-")}`;
  return (
    <section aria-labelledby={id}>
      <div className="mb-3 flex items-center justify-between gap-3">
        <h2 id={id} className="text-base font-semibold">
          {title}
        </h2>
        {action}
      </div>
      <Card className="p-4 sm:p-5">{children}</Card>
    </section>
  );
}

function formatDate(iso: string) {
  return new Date(iso).toLocaleString(undefined, { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" });
}

export function ApplicationDetailPage() {
  const { jobId = "" } = useParams();
  const { data, isPending, error } = useJobs();
  const job = data?.find((j) => j.job_id === jobId);

  const back = (
    <Link to="/applications" className="inline-flex items-center gap-1 text-sm font-medium text-ink-2 hover:text-ink">
      <ArrowLeft className="size-4" aria-hidden />
      Applications
    </Link>
  );

  if (isPending) return <Spinner />;
  if (error)
    return (
      <div className="px-4 py-5 md:px-7">
        <Alert>Couldn't load this application: {error.message}</Alert>
      </div>
    );
  if (!job)
    return (
      <div className="mx-auto max-w-2xl px-4 py-8 md:px-7">
        {back}
        <Card className="mt-4">
          <EmptyState icon={<SearchX className="size-5" />} title="This application isn't available" action={<Link to="/applications" className={buttonClass("primary")}>Back to Applications</Link>}>
            It may have been removed or belongs to another account.
          </EmptyState>
        </Card>
      </div>
    );
  // Not applied yet: the review page is where that happens.
  if (job.status === "DISCOVERED") return <Navigate to={`/jobs/${encodeURIComponent(job.job_id)}`} replace />;

  return <Detail job={job} back={back} />;
}

function Detail({ job, back }: { job: Job; back: ReactNode }) {
  const ledger = useLedger(job.job_id);
  const emails = useEmails();
  const jobEmails = (emails.data ?? []).filter((e) => e.associated_job_id === job.job_id);
  const timeline = buildTimeline(job, ledger.data ?? null, emails.data ?? []);
  const meta = STATUS_META[job.status] ?? { label: job.status, tone: "neutral" as const };
  const interview = job.interview_date && !Number.isNaN(new Date(job.interview_date).getTime()) ? new Date(job.interview_date) : null;

  return (
    <>
      <PageHeader title="Application" />
      <div className="mx-auto max-w-6xl px-4 py-5 md:px-7 md:py-6">
        <div className="mb-4">{back}</div>

        <div className="mb-6 flex items-start gap-3 sm:gap-4">
          <CompanyMark name={job.company} />
          <div className="min-w-0 flex-1">
            <h1 className="text-lg font-semibold sm:text-xl">{job.title}</h1>
            <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-ink-2">
              <span>{job.company}</span>
              <Badge tone={meta.tone}>{meta.label}</Badge>
              {interview && interview.getTime() > Date.now() && (
                <Badge tone="info">
                  <CalendarClock className="size-3" aria-hidden />
                  {formatDate(interview.toISOString())}
                </Badge>
              )}
              <a href={job.url} target="_blank" rel="noopener noreferrer" className="flex items-center gap-1 font-medium text-accent hover:underline">
                View posting
                <ExternalLink className="size-3.5" aria-hidden />
                <span className="sr-only">(opens in a new tab)</span>
              </a>
            </div>
          </div>
        </div>

        <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_22rem] lg:items-start">
          <div className="flex min-w-0 flex-col gap-6">
            {job.status === "OFFER" && <OfferTools job={job} />}
            {(job.status === "SUBMITTED" || job.status === "RESPONDED") && <FollowUp job={job} />}

            <Section title="Timeline">
              {ledger.isPending || emails.isPending ? (
                <Spinner />
              ) : timeline.length === 0 ? (
                <p className="text-ink-2">Nothing has happened on this application yet.</p>
              ) : (
                <ol className="relative flex flex-col gap-4">
                  {timeline.map((e, i) => (
                    <li key={e.key} className="relative flex gap-3">
                      {i < timeline.length - 1 && <span className="absolute top-4 bottom-[-1rem] left-[4.5px] w-px bg-line" aria-hidden />}
                      <span className={cx("relative mt-1.5 size-2.5 flex-none rounded-full", DOT[e.tone])} aria-hidden />
                      <div className="min-w-0 flex-1">
                        <p className="font-medium">{e.title}</p>
                        {e.detail && <p className="break-words text-ink-2">{e.detail}</p>}
                        <p className="text-xs text-ink-3">{formatDate(e.at)}</p>
                      </div>
                    </li>
                  ))}
                </ol>
              )}
              {(ledger.error || emails.error) && (
                <div className="mt-3">
                  <Alert tone="warn">Part of the history couldn't load. Refresh to try again.</Alert>
                </div>
              )}
            </Section>

            <Section title="Emails">
              {emails.isPending ? (
                <Spinner />
              ) : jobEmails.length === 0 ? (
                <p className="flex items-center gap-2 text-ink-2">
                  <Mail className="size-4 flex-none text-ink-3" aria-hidden />
                  No emails about this application yet. Replies we pick up from your inbox show here.
                </p>
              ) : (
                <ul className="flex flex-col divide-y divide-line">
                  {jobEmails.map((e) => (
                    <EmailItem key={e.message_id} email={e} />
                  ))}
                </ul>
              )}
            </Section>
          </div>

          {/* Status is the main control: first on phones, sticky right column on desktop. */}
          <div className="order-first lg:sticky lg:top-6 lg:order-none">
            <StatusCard job={job} />
          </div>
        </div>
      </div>
    </>
  );
}

function EmailItem({ email }: { email: Email }) {
  const meta = INTENT_META[email.intent] ?? INTENT_META.OTHER;
  return (
    <li className="py-3 first:pt-0 last:pb-0">
      <details className="group">
        <summary className="flex cursor-pointer list-none items-start gap-3 rounded-md focus-visible:outline-2">
          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-center gap-2">
              <Badge tone={meta.tone}>{meta.label}</Badge>
              <span className="text-xs text-ink-3">{relativeTime(email.received_at)}</span>
            </div>
            <p className="mt-1 truncate font-medium">{email.subject}</p>
            <p className="truncate text-ink-2">{email.sender}</p>
          </div>
          <span className="mt-1 text-xs font-medium text-accent group-open:hidden">Read</span>
          <span className="mt-1 hidden text-xs font-medium text-accent group-open:inline">Hide</span>
        </summary>
        <div className="mt-3 rounded-md bg-canvas px-4 py-3 leading-relaxed whitespace-pre-wrap">{email.body_text}</div>
        {email.scheduling_links.length > 0 && (
          <div className="mt-3 flex flex-wrap gap-2">
            {email.scheduling_links.map((url) => (
              <a key={url} href={url} target="_blank" rel="noopener noreferrer" className={buttonClass("secondary", "sm")}>
                <CalendarClock className="size-3.5" aria-hidden />
                Pick a time
                <span className="sr-only">(opens in a new tab)</span>
              </a>
            ))}
          </div>
        )}
      </details>
    </li>
  );
}

function StatusCard({ job }: { job: Job }) {
  const setStatus = useSetStatus(job.job_id);
  const manual = MANUAL_STATUSES.some((s) => s.value === job.status);
  const [saved, setSaved] = useState(false);
  const options = manual ? MANUAL_STATUSES : [{ value: job.status, label: STATUS_META[job.status]?.label ?? job.status }, ...MANUAL_STATUSES];

  return (
    <Card className="flex flex-col gap-3 p-5">
      <div>
        <h2 className="text-base font-semibold">Where it stands</h2>
        <p className="mt-0.5 text-ink-2">We update this from emails. Change it if you heard back another way.</p>
      </div>
      <Select
        label="Status"
        value={job.status}
        disabled={setStatus.isPending}
        options={options}
        onChange={(e) => {
          setSaved(false);
          setStatus.mutate(e.target.value as ApplicationStatus, { onSuccess: () => setSaved(true) });
        }}
      />
      {setStatus.error && <Alert>Couldn't update: {setStatus.error.message}</Alert>}
      {saved && !setStatus.isPending && (
        <p className="flex items-center gap-1.5 text-ok" role="status">
          <Check className="size-4" aria-hidden />
          Updated
        </p>
      )}
    </Card>
  );
}

function FollowUp({ job }: { job: Job }) {
  const draft = useFollowUpDraft(job.job_id);
  const days = daysSince(job.applied_at);
  const due = days !== null && days >= FOLLOW_UP_AFTER_DAYS;
  const text = draft.data ? `Subject: ${draft.data.followup.subject}\n\n${draft.data.followup.body}` : "";

  return (
    <Section title="Follow up" action={draft.data && <CopyButton text={text} label="Copy email" />}>
      {draft.data ? (
        <div className="flex flex-col gap-3">
          <p className="font-medium">{draft.data.followup.subject}</p>
          <div className="rounded-md border border-line bg-canvas px-4 py-3 leading-relaxed whitespace-pre-wrap">{draft.data.followup.body}</div>
          <p className="text-xs text-ink-3">We don't send this. Copy it into your email to the recruiter.</p>
        </div>
      ) : (
        <div className="flex flex-col items-start gap-3">
          <p className="text-ink-2">
            {days === null
              ? "No reply yet. A short, polite follow-up can help."
              : due
                ? `It's been ${days} days without a reply. A short follow-up is normal now.`
                : `You applied ${days === 0 ? "today" : `${days} ${days === 1 ? "day" : "days"} ago`}. Most people wait about a week before following up.`}
          </p>
          {draft.error && <Alert>Couldn't draft it: {draft.error.message}</Alert>}
          <Button variant={due ? "primary" : "secondary"} loading={draft.isPending} onClick={() => draft.mutate(days ?? FOLLOW_UP_AFTER_DAYS)}>
            Draft a follow-up
          </Button>
        </div>
      )}
    </Section>
  );
}

function OfferTools({ job }: { job: Job }) {
  const evaluate = useEvaluateOffer();
  const counter = useCounterOffer();
  // Sign the email with the name on the resume, not the account's display name.
  const candidateName = useProfile().data?.full_name || undefined;
  const [base, setBase] = useState("");
  const [bonus, setBonus] = useState("");
  const [equity, setEquity] = useState("");
  const [desired, setDesired] = useState("");

  const baseLpa = parseLpa(base);
  const result = evaluate.data?.evaluation;

  const runEvaluate = () => {
    if (baseLpa === null) return;
    evaluate.mutate(
      { base_salary_lpa: baseLpa, bonus_lpa: parseLpa(bonus) ?? 0, equity_annual_lpa: parseLpa(equity) ?? 0, role_title: job.title },
      { onSuccess: ({ evaluation }) => setDesired((d) => d || String(Math.max(evaluation.benchmark_p75, evaluation.total_annual_comp_lpa))) },
    );
  };

  return (
    <Section title="Your offer">
      <form
        className="flex flex-col gap-4"
        onSubmit={(e) => {
          e.preventDefault();
          runEvaluate();
        }}
      >
        <p className="text-ink-2">Enter the yearly numbers from the offer letter, in lakhs (LPA).</p>
        <div className="grid gap-4 sm:grid-cols-3">
          <Field label="Base salary" name="base" inputMode="decimal" placeholder="e.g. 32" value={base} onChange={(e) => setBase(e.target.value)} />
          <Field label="Bonus" name="bonus" inputMode="decimal" placeholder="0" value={bonus} onChange={(e) => setBonus(e.target.value)} />
          <Field label="Equity / year" name="equity" inputMode="decimal" placeholder="0" value={equity} onChange={(e) => setEquity(e.target.value)} />
        </div>
        {evaluate.error && <Alert>Couldn't check the offer: {evaluate.error.message}</Alert>}
        <Button type="submit" variant={result ? "secondary" : "primary"} className="self-start" loading={evaluate.isPending} disabled={baseLpa === null}>
          {result ? "Check again" : "Check this offer"}
        </Button>
      </form>

      {result && (
        <div className="mt-5 flex flex-col gap-4 border-t border-line pt-5">
          <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
            <span className="text-xl font-semibold">{result.total_annual_comp_lpa} LPA</span>
            <Badge tone={result.rating === "Below Market" ? "warn" : result.rating === "Fair Market" ? "neutral" : "ok"}>{result.rating}</Badge>
            <span className="text-ink-2">{result.market_percentile_band}</span>
          </div>
          <p>{result.negotiation_guidance}</p>
          <p className="text-xs text-ink-3">
            Compared with built-in salary ranges for similar roles in India (median {result.benchmark_p50} LPA, 75th percentile {result.benchmark_p75} LPA), not live market data.
          </p>

          <form
            className="flex flex-col gap-3 sm:flex-row sm:items-end"
            onSubmit={(e) => {
              e.preventDefault();
              if (parseLpa(desired) !== null)
                counter.mutate({
                  candidate_name: candidateName,
                  company_name: job.company,
                  role_title: job.title,
                  offered_tc: `${result.total_annual_comp_lpa} LPA`,
                  desired_tc: `${parseLpa(desired)} LPA`,
                });
            }}
          >
            <Field className="sm:w-48" label="What you'd like" name="desired" inputMode="decimal" hint="Total per year, in LPA" value={desired} onChange={(e) => setDesired(e.target.value)} />
            <Button type="submit" variant={counter.data ? "secondary" : "primary"} loading={counter.isPending} disabled={parseLpa(desired) === null} className="sm:mb-6">
              Draft a counter-offer
            </Button>
          </form>
          {counter.error && <Alert>Couldn't draft it: {counter.error.message}</Alert>}
          {counter.data && (
            <div>
              <div className="mb-1.5 flex items-center justify-between">
                <h3 className="text-sm font-semibold">Counter-offer email</h3>
                <CopyButton text={counter.data.counter_offer_script} label="Copy email" />
              </div>
              <div className="rounded-md border border-line bg-canvas px-4 py-3 leading-relaxed whitespace-pre-wrap">{counter.data.counter_offer_script}</div>
              <p className="mt-1.5 text-xs text-ink-3">We don't send this. Edit it to sound like you, then send it yourself.</p>
            </div>
          )}
        </div>
      )}
    </Section>
  );
}
