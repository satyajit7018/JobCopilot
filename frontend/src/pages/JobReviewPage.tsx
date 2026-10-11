import { useEffect, useState, type ReactNode } from "react";
import { Link, useParams } from "react-router";
import { ArrowLeft, ArrowRight, Bookmark, BookmarkCheck, Check, CircleAlert, ExternalLink, EyeOff, FileText, SearchX, ShieldCheck } from "lucide-react";
import { MatchReceipt } from "../components/MatchReceipt";
import { toast } from "../components/Toast";
import { Alert, Badge, Button, Card, CheckRow, ChoiceChips, CompanyMark, CopyButton, EmptyState, Group, ScoreRing, Segmented, Spinner, buttonClass, cx, rowClass, toneText } from "../components/ui";
import {
  newKey,
  outcome,
  taskPhase,
  useApplyTask,
  useLiveConsent,
  useSetLiveConsent,
  useStartApply,
  useSetResumeWording,
  useTailor,
  type ResumeChange,
  type ResumeWording,
  type SubmissionMode,
} from "../lib/apply";
import {
  STATUS_META,
  applyOnSiteOnly,
  isTracked,
  nextMatch,
  scorePercent,
  useCompanyInfo,
  useJobDescription,
  useJobs,
  useSetMatchHidden,
  useSetMatchSaved,
  useVisibleJobs,
  type Job,
} from "../lib/jobs";
import { useSetStatus } from "../lib/application";
import { markDone } from "../lib/checklist";
import { usePageTitle } from "../lib/pageTitle";
import { useIsPremium } from "../lib/billing";
import { PremiumLock } from "../components/PremiumLock";
import { noticeLabel, useProfile } from "../lib/profile";

const DESCRIPTION_PREVIEW = 700;

function Section({ title, action, children }: { title: string; action?: ReactNode; children: ReactNode }) {
  const id = `sec-${title.toLowerCase().replace(/\W+/g, "-")}`;
  return (
    <section aria-labelledby={id}>
      <div className="mb-2 flex items-center justify-between gap-3">
        <h2 id={id} className="px-1 text-xs font-normal text-ink-2">
          {title}
        </h2>
        {action}
      </div>
      <Card className="p-5">{children}</Card>
    </section>
  );
}

// The running task survives navigation within the tab, so leaving and coming back keeps progress.
const taskStore = {
  key: (jobId: string) => `jobcopilot_task_${jobId}`,
  get(jobId: string) {
    try {
      return sessionStorage.getItem(this.key(jobId));
    } catch {
      return null;
    }
  },
  set(jobId: string, taskId: string | null) {
    try {
      if (taskId) sessionStorage.setItem(this.key(jobId), taskId);
      else sessionStorage.removeItem(this.key(jobId));
    } catch {
      // ignore
    }
  },
};

export function JobReviewPage() {
  const { jobId = "" } = useParams();
  const { data, isPending, error } = useJobs();
  const visible = useVisibleJobs();
  const job = data?.find((j) => j.job_id === jobId);

  const back = (
    <Link to="/jobs" className="inline-flex items-center gap-1 text-sm font-medium text-ink-2 hover:text-ink">
      <ArrowLeft className="size-4" aria-hidden />
      Jobs
    </Link>
  );

  if (isPending) return <Spinner />;
  if (error)
    return (
      <div className="px-4 py-5 md:px-7">
        <Alert>Couldn't load this job: {error.message}</Alert>
      </div>
    );
  if (!job)
    return (
      <div className="mx-auto max-w-2xl px-4 py-8 md:px-7">
        {back}
        <Card className="mt-4">
          <EmptyState icon={<SearchX className="size-5" />} title="This job isn't available" action={<Link to="/jobs" className={buttonClass("primary")}>Back to Jobs</Link>}>
            It may have been removed or belongs to another account.
          </EmptyState>
        </Card>
      </div>
    );

  return <Review key={job.job_id} job={job} back={back} next={nextMatch(visible.data ?? [], job.job_id)} />;
}

/** The company in its own words, or at least a link to its website. Hidden when we have neither. */
function AboutCompany({ company, jobId }: { company: string; jobId: string }) {
  const { data } = useCompanyInfo(company, jobId);
  if (!data?.about && !data?.website) return null;
  const site = data.website?.replace(/^https?:\/\//, "");
  return (
    <Section title={`About ${company}`}>
      {data.about ? (
        <p className="leading-relaxed">{data.about}</p>
      ) : (
        <p className="text-ink-2">We don't have a description of {company} yet. Their website has the details.</p>
      )}
      {(data.about || data.website) && (
        <p className="mt-3 flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-ink-3">
          {data.about && <span>{data.source === "posting" ? "From the job posting." : "From the company's website."}</span>}
          {data.website && (
            <a href={data.website} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 text-sm font-medium text-accent hover:underline">
              Visit {site}
              <ExternalLink className="size-3.5" aria-hidden />
              <span className="sr-only">(opens in a new tab)</span>
            </a>
          )}
        </p>
      )}
    </Section>
  );
}

function Review({ job, back, next }: { job: Job; back: ReactNode; next: Job | null }) {
  const tailor = useTailor(job.job_id);
  const description = useJobDescription(job.job_id);
  useEffect(() => markDone("reviewed"), []);
  const premium = useIsPremium();
  const [taskId, setTaskId] = useState<string | null>(() => taskStore.get(job.job_id));
  const pct = scorePercent(job.match_score);
  usePageTitle(`${job.title} at ${job.company}`);

  return (
    <>
      <div className="mx-auto max-w-6xl px-4 pt-3 pb-28 md:px-7 md:pt-8 md:pb-10">
        <div className="mb-5 flex items-center justify-between gap-3">
          {back}
          {next && (
            <Link to={`/jobs/${encodeURIComponent(next.job_id)}`} className="inline-flex items-center gap-1 text-sm font-medium text-accent hover:underline">
              Next match
              <ArrowRight className="size-4" aria-hidden />
              <span className="sr-only">
                : {next.title} at {next.company}
              </span>
            </Link>
          )}
        </div>
        {job.status === "DISMISSED" && <HiddenNotice job={job} />}

        <div className="mb-7 flex items-center gap-4">
          <CompanyMark name={job.company} size="lg" />
          <div className="min-w-0 flex-1">
            <h1 className="text-lg leading-tight font-bold sm:text-xl">{job.title}</h1>
            <p className="mt-1 text-ink-2">{[job.company, job.location, job.salary_range].filter(Boolean).join(" · ")}</p>
            <div className="mt-2.5 flex flex-wrap items-center gap-2">
              <SaveButton job={job} />
              <HideButton job={job} />
            </div>
          </div>
          <ScoreRing pct={pct} size="lg" className="max-sm:hidden" />
        </div>

        <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_22rem] lg:grid-rows-[auto_auto_1fr] lg:items-start">
          <div className="flex min-w-0 flex-col gap-6">
            <Section title="Why it's a match">
              <div className="flex items-start gap-4">
                <ScoreRing pct={pct} size="md" className="sm:hidden" />
                <div className="min-w-0 flex-1">
                  {job.match_reasons.length ? (
                    <MatchReceipt job={job} max={8} />
                  ) : (
                    <p className="text-ink-2">No details were recorded for this match.</p>
                  )}
                  {job.missing_skills.length > 0 && (
                    <div className="mt-3">
                      <p className="mb-1.5 text-ink-2">Asked for, but not on your resume:</p>
                      <div className="flex flex-wrap gap-1.5">
                        {job.missing_skills.map((s) => (
                          <Badge key={s} tone="warn">
                            {s}
                          </Badge>
                        ))}
                      </div>
                    </div>
                  )}
                  <p className="mt-3 text-xs text-ink-3">This score compares your resume with the job post. It isn't your chance of getting an interview.</p>
                </div>
              </div>
            </Section>

            <AboutCompany company={job.company} jobId={job.job_id} />

            {premium && <Materials job={job} tailor={tailor} />}
          </div>

          {/* On phones the panel follows the materials; on desktop it's a sticky right column. */}
          <div className="lg:sticky lg:top-6 lg:col-start-2 lg:row-span-3 lg:row-start-1">
            {!premium || applyOnSiteOnly(job) ? (
              <ApplyYourself job={job} />
            ) : taskId ? (
              <Progress
                taskId={taskId}
                job={job}
                onRetry={() => {
                  taskStore.set(job.job_id, null);
                  setTaskId(null);
                }}
              />
            ) : (
              <ApplyPanel
                job={job}
                prepared={tailor.isSuccess}
                onStarted={(id) => {
                  taskStore.set(job.job_id, id);
                  setTaskId(id);
                }}
              />
            )}
          </div>

          {description.isPending ? (
            <div className="min-w-0 lg:col-start-1" role="status">
              <span className="sr-only">Loading the job description…</span>
              <div aria-hidden className="flex animate-pulse flex-col gap-2.5 rounded-lg bg-surface p-5 motion-reduce:animate-none">
                <span className="h-3.5 w-1/3 rounded bg-subtle" />
                <span className="h-3 w-full rounded bg-subtle" />
                <span className="h-3 w-5/6 rounded bg-subtle" />
              </div>
            </div>
          ) : (
            description.data && (
              <div className="min-w-0 lg:col-start-1">
                <Description text={description.data} />
              </div>
            )
          )}

          <div className="min-w-0 lg:col-start-1">
            <Details job={job} />
          </div>
        </div>
      </div>
    </>
  );
}

/**
 * Where this posting came from. Only facts we hold are shown; a row with nothing to say is
 * left out.
 */
function Details({ job }: { job: Job }) {
  const day = (iso: string | null) => {
    const d = iso ? new Date(iso) : null;
    return d && !Number.isNaN(d.getTime()) ? d.toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" }) : null;
  };
  const rows: [string, ReactNode][] = [];
  const posted = day(job.posted_date);
  const found = day(job.created_at);
  if (job.platform && job.platform !== "DIRECT_CALL") rows.push(["Source", job.platform]);
  if (posted) rows.push(["Posted", posted]);
  if (found) rows.push(["Found by JobCopilot", found]);
  if (job.location) rows.push(["Place", job.location]);
  if (job.salary_range) rows.push(["Pay", job.salary_range]);
  const hasLink = /^https?:\/\//.test(job.url);
  if (!rows.length && !hasLink) return null;
  return (
    <Group label="Details">
      <dl>
        {rows.map(([label, value]) => (
          <div key={label} className={cx(rowClass, "min-h-12 after:left-4")}>
            <dt className="flex-1 text-ink-2">{label}</dt>
            <dd className="text-right font-medium">{value}</dd>
          </div>
        ))}
      </dl>
      {hasLink && (
        <a href={job.url} target="_blank" rel="noopener noreferrer" className={cx(rowClass, "min-h-12 font-medium text-accent after:left-4 hover:bg-subtle/50")}>
          <span className="flex-1">View the original posting</span>
          <ExternalLink className="size-4" aria-hidden />
          <span className="sr-only">(opens in a new tab)</span>
        </a>
      )}
    </Group>
  );
}

function Description({ text }: { text: string }) {
  const [open, setOpen] = useState(false);
  const long = text.length > DESCRIPTION_PREVIEW;
  const shown = open || !long ? text : `${text.slice(0, DESCRIPTION_PREVIEW).trimEnd()}…`;
  return (
    <Section title="About the role">
      <p className="leading-relaxed whitespace-pre-line text-ink-2">{shown}</p>
      {long && (
        <button type="button" className="mt-2 text-sm font-medium text-accent hover:underline" onClick={() => setOpen((v) => !v)} aria-expanded={open}>
          {open ? "Show less" : "Show the full description"}
        </button>
      )}
    </Section>
  );
}

function Materials({ job, tailor }: { job: Job; tailor: ReturnType<typeof useTailor> }) {
  const profile = useProfile();
  const p = profile.data;

  return (
    <>
      <Section
        title="Your application"
        action={tailor.isSuccess && <CopyButton text={tailor.data.cover_letter} label="Copy letter" />}
      >
        {tailor.isSuccess ? (
          <div className="flex flex-col gap-4">
            <div className="flex items-center gap-2 rounded-md bg-ok-soft px-3.5 py-2.5 font-medium text-ok">
              <FileText className="size-4 flex-none" aria-hidden />
              Resume tailored for {job.company}. It's attached when you apply.
            </div>
            <ResumeChanges jobId={job.job_id} changes={tailor.data.resume_changes ?? []} initial={tailor.data.resume_wording ?? "ai"} />
            <div>
              <h3 className="mb-1.5 text-sm font-semibold">Cover letter</h3>
              <div className="max-h-96 overflow-y-auto rounded-md bg-subtle px-4 py-3 leading-relaxed whitespace-pre-wrap">
                {tailor.data.cover_letter}
              </div>
              <p className="mt-1.5 text-xs text-ink-3">The letter is written fresh for each application, so it may differ slightly when it's sent.</p>
            </div>
          </div>
        ) : (
          <div className="flex flex-col items-start gap-3">
            <p className="text-ink-2">
              We'll tailor your resume to this role and draft a cover letter, so you can read them before anything is sent.
            </p>
            {tailor.error && <Alert>Couldn't prepare your application: {tailor.error.message}</Alert>}
            <Button variant="primary" loading={tailor.isPending} onClick={() => tailor.mutate()}>
              {tailor.isPending ? "Preparing" : tailor.isError ? "Try again" : "Prepare my application"}
            </Button>
          </div>
        )}
      </Section>

      {p && (
        <Section
          title="What we'll fill in"
          action={
            <Link to="/profile" className="text-sm font-medium text-accent hover:underline">
              Edit in Profile
            </Link>
          }
        >
          <dl className="grid gap-x-6 gap-y-3 sm:grid-cols-2">
            {[
              ["Name", p.full_name],
              ["Email", p.email],
              ["Phone", p.phone],
              ["Location", p.location],
              ["Expected salary", p.preferences.expected_ctc],
              ["Can start", noticeLabel(p.preferences.notice_period_days)],
              ["Work authorization", p.preferences.work_authorization],
            ].map(([label, value]) => (
              <div key={label}>
                <dt className="text-xs text-ink-3">{label}</dt>
                <dd className="break-words">{value || <span className="text-ink-3">Not set</span>}</dd>
              </div>
            ))}
          </dl>
        </Section>
      )}
    </>
  );
}

/** The AI's rewording of your resume bullets, next to your own, with the choice of which to send. */
function ResumeChanges({ jobId, changes, initial }: { jobId: string; changes: ResumeChange[]; initial: ResumeWording }) {
  const setWording = useSetResumeWording(jobId);
  const [choice, setChoice] = useState<ResumeWording>(initial);
  if (changes.length === 0)
    return <p className="text-ink-2">Your resume bullets are reordered to put the most relevant first. The wording is your own.</p>;
  const pick = (next: ResumeWording) => {
    const before = choice;
    setChoice(next);
    setWording.mutate(next, { onError: () => setChoice(before) });
  };
  return (
    <div>
      <h3 className="text-sm font-semibold">Changes to your resume</h3>
      <p className="mb-2.5 text-ink-2">
        We reworded {changes.length === 1 ? "one bullet" : `${changes.length} bullets`} to fit this job. Check each one is true before you apply.
      </p>
      <ul className="flex flex-col gap-2.5">
        {changes.map((c, i) => (
          <li key={i} className="rounded-md bg-subtle">
            <p className="border-b border-line px-3 py-1.5 text-xs text-ink-3">
              {c.role} · {c.company}
            </p>
            <div className="grid sm:grid-cols-2">
              <div className={cx("px-3 py-2", choice === "original" && "bg-accent-soft")}>
                <p className="mb-0.5 text-xs font-medium text-ink-3">Your words</p>
                <p>{c.before}</p>
              </div>
              <div className={cx("border-t border-line px-3 py-2 sm:border-t-0 sm:border-l", choice === "ai" && "bg-accent-soft")}>
                <p className="mb-0.5 text-xs font-medium text-ink-3">Reworded</p>
                <p>{c.after}</p>
              </div>
            </div>
          </li>
        ))}
      </ul>
      <div className="mt-3">
        <ChoiceChips
          label="Which wording should we send?"
          value={choice}
          onChange={pick}
          options={[
            { value: "ai", label: "Reworded" },
            { value: "original", label: "My own words" },
          ]}
        />
      </div>
      {setWording.error && (
        <div className="mt-2">
          <Alert>Couldn't save your choice: {setWording.error.message}</Alert>
        </div>
      )}
    </div>
  );
}

function ApplyPanel({ job, prepared, onStarted }: { job: Job; prepared: boolean; onStarted: (taskId: string) => void }) {
  const consent = useLiveConsent();
  const setConsent = useSetLiveConsent();
  const start = useStartApply(job.job_id);
  const [mode, setMode] = useState<SubmissionMode>("DRY_RUN");
  const [reviewed, setReviewed] = useState(false);
  // A new key per approval click; reused if the same click's request is retried.
  const [key, setKey] = useState(newKey);

  if (isTracked(job)) {
    const meta = STATUS_META[job.status];
    return (
      <Card className="p-5">
        <h2 className="text-base font-semibold">Already in your applications</h2>
        <p className="mt-1 mb-3 text-ink-2">This job is past the review step.</p>
        <Badge tone={meta?.tone}>{meta?.label ?? job.status}</Badge>
        <Link to="/applications" className={buttonClass("secondary", "md", "mt-4 w-full")}>
          Go to Applications
        </Link>
      </Card>
    );
  }

  const live = mode === "LIVE";
  const hasConsent = consent.data === true;
  const canApply = live ? prepared && reviewed && hasConsent : true;

  const submit = () =>
    start.mutate(
      { mode, key },
      {
        onSuccess: ({ task_id }) => onStarted(task_id),
        onError: () => setKey(newKey()),
      },
    );

  return (
    <Card className="flex flex-col gap-5 p-5">
      <div>
        <h2 className="text-base font-semibold">Apply</h2>
        <p className="mt-0.5 text-ink-2">Nothing is sent until you approve it here.</p>
      </div>

      <div className="flex flex-col gap-2">
        <Segmented
          label="How"
          value={mode}
          onChange={setMode}
          options={[
            { value: "DRY_RUN", label: "Practice run" },
            { value: "LIVE", label: "Submit for real" },
          ]}
        />
        <p className="text-xs text-ink-3">
          {live
            ? "We fill in the employer's form and submit it for you, after these three steps."
            : "We fill in the form to check everything works, then stop. Nothing is submitted."}
        </p>
      </div>

      {live && (
        <ol className="flex flex-col gap-4">
          <ApprovalStep n={1} done={prepared} title="Read what will be sent">
            {prepared ? (
              <p className="text-ink-2">Your resume and cover letter are ready under "Your application".</p>
            ) : (
              <Alert tone="warn">
                <span className="inline-flex gap-1.5">
                  <CircleAlert className="mt-0.5 size-4 flex-none" aria-hidden />
                  Prepare your application first so you can read it.
                </span>
              </Alert>
            )}
          </ApprovalStep>
          <ApprovalStep n={2} done={reviewed} title="Confirm it's right">
            <CheckRow
              checked={reviewed}
              disabled={!prepared}
              onChange={setReviewed}
              title="I've read the cover letter and my details"
              detail="They're accurate and I want to apply to this job."
            />
          </ApprovalStep>
          <ApprovalStep n={3} done={hasConsent} title="Allow JobCopilot to send it">
            {consent.isPending ? null : (
              <CheckRow
                checked={hasConsent}
                disabled={setConsent.isPending}
                onChange={(on) => setConsent.mutate(on)}
                title="Let JobCopilot submit applications for me"
                detail="Applies to every real submission. Uncheck it any time to turn it off."
              />
            )}
            {setConsent.error && <Alert>Couldn't save that: {setConsent.error.message}</Alert>}
          </ApprovalStep>
        </ol>
      )}

      {start.error && <Alert>{start.error.message}</Alert>}

      <div className="flex flex-col gap-2">
        {/* Until materials are prepared, "Prepare my application" is the screen's main action. */}
        <Button variant={prepared ? "primary" : "secondary"} size="lg" loading={start.isPending} disabled={!canApply} onClick={submit}>
          {live ? "Approve and submit" : "Start practice run"}
        </Button>
        <p className="flex gap-1.5 text-xs text-ink-3">
          <ShieldCheck className="size-3.5 flex-none" aria-hidden />
          We stop and ask you if the form has a question we can't answer or a security check.
        </p>
      </div>
    </Card>
  );
}

/** One numbered step of approving a real submission; the number becomes a tick when done. */
function ApprovalStep({ n, done, title, children }: { n: number; done: boolean; title: string; children: ReactNode }) {
  return (
    <li className="flex gap-3">
      <span
        className={cx(
          "mt-0.5 grid size-6 flex-none place-items-center rounded-full text-xs font-semibold",
          done ? "bg-ok text-on-solid" : "bg-subtle text-ink-2",
        )}
        aria-hidden
      >
        {done ? <Check className="size-3.5" strokeWidth={2.5} /> : n}
      </span>
      <div className="flex min-w-0 flex-1 flex-col gap-2">
        <p className="font-semibold">
          {title}
          <span className="sr-only">{done ? " (done)" : " (to do)"}</span>
        </p>
        {children}
      </div>
    </li>
  );
}

function SaveButton({ job }: { job: Job }) {
  const save = useSetMatchSaved();
  if (job.status !== "DISCOVERED" && job.status !== "SAVED") return null;
  const saved = job.status === "SAVED";
  return (
    <Button
      size="sm"
      aria-pressed={saved}
      onClick={() => {
        save.mutate({ jobId: job.job_id, saved: !saved });
        toast(saved ? "Removed from saved" : "Saved for later");
      }}
    >
      {saved ? <BookmarkCheck className="size-3.5 text-accent" aria-hidden /> : <Bookmark className="size-3.5" aria-hidden />}
      {saved ? "Saved" : "Save"}
    </Button>
  );
}

function HideButton({ job }: { job: Job }) {
  const hide = useSetMatchHidden();
  if (job.status !== "DISCOVERED" && job.status !== "SAVED") return null;
  return (
    <Button size="sm" variant="ghost" title="Not interested" onClick={() => hide.mutate({ jobId: job.job_id, hidden: true })}>
      <EyeOff className="size-3.5" aria-hidden />
      <span className="max-sm:sr-only">Not interested</span>
    </Button>
  );
}

function HiddenNotice({ job }: { job: Job }) {
  const unhide = useSetMatchHidden();
  return (
    <div className="mb-4 flex flex-wrap items-center gap-3 rounded-lg bg-surface px-4 py-3">
      <p className="flex-1 text-ink-2">You marked this job "Not interested", so it's hidden from your matches.</p>
      <Button size="sm" loading={unhide.isPending} onClick={() => unhide.mutate({ jobId: job.job_id, hidden: false })}>
        Show it again
      </Button>
    </div>
  );
}

/** Free plan, or a site we never apply on for you: apply there, then track it here. */
function ApplyYourself({ job }: { job: Job }) {
  const site = applyOnSiteOnly(job);
  const setStatus = useSetStatus(job.job_id);
  const applied = isTracked(job) || setStatus.isSuccess;

  return (
    <div className="flex flex-col gap-4">
      <Card className="flex flex-col gap-3 p-5">
        <h2 className="text-base font-semibold">Apply</h2>
        {applied ? (
          <>
            <p className="flex items-center gap-1.5 font-medium text-ok" role="status">
              <Check className="size-4" aria-hidden />
              Added to your applications
            </p>
            <Link to={`/applications/${encodeURIComponent(job.job_id)}`} className={buttonClass("secondary")}>
              Open in Applications
            </Link>
          </>
        ) : (
          <>
            <p className="text-ink-2">
              {site
                ? `This job is on ${site}, where you apply with your own ${site} account. Apply there, then come back and mark it applied so we can track it for you.`
                : `Apply on ${job.company}'s site, then come back and mark it applied so we can track it for you.`}
            </p>
            <a href={job.url} target="_blank" rel="noopener noreferrer" className={buttonClass("primary", "md", "max-md:hidden")}>
              Open the application
              <ExternalLink className="size-3.5" aria-hidden />
              <span className="sr-only">(opens in a new tab)</span>
            </a>
            {/* Phones: the main action stays within reach, pinned above the tab bar. */}
            <div className="fixed inset-x-0 bottom-16 z-10 border-t border-line bg-canvas px-4 py-2.5 md:hidden">
              <a href={job.url} target="_blank" rel="noopener noreferrer" className={buttonClass("primary", "lg", "w-full")}>
                Open the application
                <ExternalLink className="size-4" aria-hidden />
                <span className="sr-only">(opens in a new tab)</span>
              </a>
            </div>
            {setStatus.error && <Alert>Couldn't save: {setStatus.error.message}</Alert>}
            <Button loading={setStatus.isPending} onClick={() => setStatus.mutate("SUBMITTED")}>
              I've applied
            </Button>
          </>
        )}
      </Card>
      {/* One box for everything Premium adds here; two competed with the Apply button. */}
      {!site && (
        <PremiumLock
          title="Let JobCopilot apply for you"
          points={[
            "A resume and cover letter written for this job",
            "The application filled in and sent, after you approve it",
          ]}
        />
      )}
    </div>
  );
}

function Progress({ taskId, job, onRetry }: { taskId: string; job: Job; onRetry: () => void }) {
  const task = useApplyTask(taskId);
  const phase = taskPhase(task.data);
  const [elapsed, setElapsed] = useState(0);

  useEffect(() => {
    if (phase !== "running") return;
    const t = setInterval(() => setElapsed((s) => s + 1), 1000);
    return () => clearInterval(t);
  }, [phase]);

  if (task.error) {
    return (
      <Card className="flex flex-col gap-3 p-5">
        <Alert>Lost track of this application: {task.error.message}</Alert>
        <Link to="/applications" className={buttonClass("secondary")}>
          Check Applications
        </Link>
      </Card>
    );
  }

  if (phase === "running") {
    const pctDone = task.data?.progress_percent ?? 10;
    return (
      <Card className="flex flex-col gap-3 p-5" aria-live="polite">
        <h2 className="text-base font-semibold">Working on it…</h2>
        <div className="h-2 overflow-hidden rounded-full bg-subtle" role="progressbar" aria-valuenow={pctDone} aria-valuemin={0} aria-valuemax={100}>
          <div className="h-full rounded-full bg-accent transition-all" style={{ width: `${pctDone}%` }} />
        </div>
        <p className="text-ink-2">
          {pctDone < 50 ? "Waiting for a free worker" : "Filling in the application"}
          {elapsed > 0 && <span className="text-ink-3"> · {elapsed}s</span>}
        </p>
        <p className="text-xs text-ink-3">You can leave this page. It keeps going and shows up in Applications.</p>
      </Card>
    );
  }

  const o = outcome(task.data!);
  return (
    <Card className="flex flex-col gap-4 p-5" aria-live="polite">
      <div>
        <h2 className={cx("flex items-center gap-2 text-base font-semibold", toneText[o.tone])}>
          {task.data?.result?.submitted && <Check className="size-5" strokeWidth={2.25} aria-hidden />}
          {o.title}
        </h2>
        <p className="mt-1 text-ink-2">{o.detail}</p>
      </div>
      {/* The receipt: what went, and where. Only for a real submission. */}
      {task.data?.result?.submitted && (
        <dl className="overflow-hidden rounded-md bg-subtle">
          {[
            ["Sent to", job.company],
            ["Role", job.title],
            ["With", "Your tailored resume and cover letter"],
          ].map(([label, value]) => (
            <div key={label} className="flex gap-3 px-3.5 py-2.5">
              <dt className="w-16 flex-none text-ink-2">{label}</dt>
              <dd className="min-w-0 flex-1 font-medium">{value}</dd>
            </div>
          ))}
        </dl>
      )}
      <div className="flex flex-col gap-2">
        <Link to="/applications" className={buttonClass(phase === "succeeded" ? "primary" : "secondary")}>
          Go to Applications
        </Link>
        {o.tone === "danger" && (
          <Button variant="ghost" onClick={onRetry}>
            Try again
          </Button>
        )}
        {phase === "succeeded" && !task.data?.result?.submitted && (
          <Button variant="ghost" onClick={onRetry}>
            Back to apply options
          </Button>
        )}
      </div>
    </Card>
  );
}
