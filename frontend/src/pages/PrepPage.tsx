import { useEffect, useMemo, useState, type ReactNode } from "react";
import { useSearchParams } from "react-router";
import { CalendarClock, Check, Mic } from "lucide-react";
import { PageHeader } from "../components/AppShell";
import { PremiumLock } from "../components/PremiumLock";
import { useIsPremium } from "../lib/billing";
import { Alert, Badge, Button, Card, CopyButton, Field, Select, Spinner, Textarea, cx } from "../components/ui";
import { useJobs, type Job } from "../lib/jobs";
import {
  DIMENSION_LABELS,
  plainText,
  useAnswerFeedback,
  useAskThem,
  useDossier,
  usePracticeQuestions,
  type PracticeQuestion,
} from "../lib/prep";

const OTHER = "__other";

/** The value once it has stopped changing for `ms`, so typing doesn't fire a request per keystroke. */
function useSettled<T>(value: T, ms = 500): T {
  const [settled, setSettled] = useState(value);
  useEffect(() => {
    const t = setTimeout(() => setSettled(value), ms);
    return () => clearTimeout(t);
  }, [value, ms]);
  return settled;
}

function Section({ title, description, action, children }: { title: string; description?: string; action?: ReactNode; children: ReactNode }) {
  const id = `sec-${title.toLowerCase().replace(/\W+/g, "-")}`;
  return (
    <section aria-labelledby={id}>
      <div className="mb-3 flex items-end justify-between gap-3">
        <div>
          <h2 id={id} className="text-base font-semibold">
            {title}
          </h2>
          {description && <p className="text-ink-2">{description}</p>}
        </div>
        {action}
      </div>
      <Card className="p-4 sm:p-5">{children}</Card>
    </section>
  );
}

function interviewLabel(j: Job) {
  const at = j.interview_date ? new Date(j.interview_date) : null;
  const when = at && !Number.isNaN(at.getTime()) ? ` · ${at.toLocaleString(undefined, { weekday: "short", month: "short", day: "numeric" })}` : "";
  return `${j.company}, ${j.title}${when}`;
}

export function PrepPage() {
  const premium = useIsPremium();
  return premium ? <PrepTools /> : <PrepLocked />;
}

const SAMPLE = [
  { label: "A likely question", text: "Tell me about a time you made a slow service faster. What did you measure before and after?" },
  { label: "Feedback on your practice answer", text: "Clear structure. Add the numbers: how slow was it, and how fast did it get? Say which part was your work." },
  { label: "A question to ask them", text: "What does the on-call rotation look like for this team, and how often does it page?" },
];

function PrepLocked() {
  return (
    <>
      <PageHeader width="max-w-3xl" title="Prep" />
      <div className="mx-auto max-w-3xl px-4 py-5 md:px-7 md:py-8">
        <PremiumLock title="Get ready for every interview">
          Likely questions for each role, practice answers with feedback, and questions to ask them. Your upcoming interviews show
          here with everything you need.
        </PremiumLock>

        {/* A fixed sample so the page shows what Prep is, not just that it's locked. */}
        <section aria-labelledby="prep-sample" className="mt-8">
          <h2 id="prep-sample" className="text-base font-semibold">
            What it looks like
          </h2>
          <p className="text-ink-2">An example for a backend engineer interview. Yours are written for the job you're interviewing for.</p>
          <Card className="mt-3 divide-y divide-line">
            {SAMPLE.map((s) => (
              <div key={s.label} className="px-4 py-3.5 sm:px-5">
                <p className="text-xs font-medium tracking-wide text-ink-3 uppercase">{s.label}</p>
                <p className="mt-1">{s.text}</p>
              </div>
            ))}
          </Card>
        </section>
      </div>
    </>
  );
}

function PrepTools() {
  const [params, setParams] = useSearchParams();
  const { data: jobs, isPending: jobsPending } = useJobs();
  const interviews = useMemo(
    () =>
      (jobs ?? [])
        .filter((j) => j.status === "INTERVIEW")
        .sort((a, b) => new Date(a.interview_date ?? 8e15).getTime() - new Date(b.interview_date ?? 8e15).getTime()),
    [jobs],
  );

  // ?job=<id> picks an interview; otherwise the soonest one, or a company/role typed in.
  const picked = params.get("job") ?? interviews[0]?.job_id ?? OTHER;
  const job = interviews.find((j) => j.job_id === picked);
  const [company, setCompany] = useState("");
  const [role, setRole] = useState("Software Engineer");
  const typedCompany = useSettled(company.trim());
  const typedRole = useSettled(role.trim() || "Software Engineer");
  const target = job ? { company: job.company, role: job.title } : { company: typedCompany, role: typedRole };

  // Wait for the job list so we don't flash "no interviews" or fetch questions for the wrong role.
  if (jobsPending) return <Spinner />;

  return (
    <>
      <PageHeader width="max-w-4xl" title="Prep" subtitle={interviews.length ? `${interviews.length} upcoming ${interviews.length === 1 ? "interview" : "interviews"}` : undefined} />
      <div className="mx-auto flex max-w-4xl flex-col gap-8 px-4 py-5 md:px-7 md:py-8">
        <Card className="flex flex-col gap-4 p-4 sm:p-5">
          {interviews.length > 0 && (
            <Select
              label="Preparing for"
              value={picked}
              onChange={(e) => setParams(e.target.value === OTHER ? { job: OTHER } : { job: e.target.value }, { replace: true })}
              options={[...interviews.map((j) => ({ value: j.job_id, label: interviewLabel(j) })), { value: OTHER, label: "Something else" }]}
            />
          )}
          {!job && (
            <div className="grid gap-4 sm:grid-cols-2">
              <Field label="Company" name="company" placeholder="e.g. Stripe" value={company} onChange={(e) => setCompany(e.target.value)} />
              <Field label="Role" name="role" value={role} onChange={(e) => setRole(e.target.value)} />
            </div>
          )}
          {interviews.length === 0 && (
            <p className="flex items-center gap-2 text-ink-2">
              <CalendarClock className="size-4 flex-none text-ink-3" aria-hidden />
              No interviews scheduled yet. When one is, it shows up here automatically.
            </p>
          )}
        </Card>

        {target.company ? <CompanyBrief company={target.company} role={target.role} /> : null}
        <Practice role={target.role} />
        {target.company ? <AskThem company={target.company} role={target.role} /> : null}
      </div>
    </>
  );
}

function CompanyBrief({ company, role }: { company: string; role: string }) {
  const { data, isPending, error } = useDossier(company, role);
  return (
    <Section title={`About ${company}`} description="What their engineering team cares about and how they interview.">
      {isPending ? (
        <Spinner />
      ) : error ? (
        <Alert>Couldn't load the brief: {error.message}</Alert>
      ) : (
        <div className="flex flex-col gap-5">
          <p className="leading-relaxed">{data.engineering_focus}</p>
          {data.likely_tech_stack.length > 0 && (
            <div>
              <h3 className="mb-2 text-sm font-semibold">Likely tech stack</h3>
              <div className="flex flex-wrap gap-1.5">
                {data.likely_tech_stack.map((t) => (
                  <Badge key={t}>{t}</Badge>
                ))}
              </div>
            </div>
          )}
          {data.common_interview_rounds.length > 0 && (
            <div>
              <h3 className="mb-2 text-sm font-semibold">Typical rounds</h3>
              <ol className="flex flex-col gap-1.5">
                {data.common_interview_rounds.map((r, i) => (
                  <li key={r} className="flex gap-2.5">
                    <span className="grid size-5 flex-none place-items-center rounded-full bg-subtle text-xs font-medium text-ink-2">{i + 1}</span>
                    {/* The backend prefixes "Round N:"; the number is already shown. */}
                    <span>{r.replace(/^Round \d+:\s*/i, "")}</span>
                  </li>
                ))}
              </ol>
            </div>
          )}
          {data.key_preparation_tips.length > 0 && (
            <div>
              <h3 className="mb-2 text-sm font-semibold">How to prepare</h3>
              <ul className="flex flex-col gap-1.5">
                {data.key_preparation_tips.map((t) => (
                  <li key={t} className="flex gap-2">
                    <Check className="mt-0.5 size-4 flex-none text-ok" aria-hidden />
                    {t}
                  </li>
                ))}
              </ul>
            </div>
          )}
          <p className="text-xs text-ink-3">Based on public information and common patterns. Your interview may differ.</p>
        </div>
      )}
    </Section>
  );
}

function Practice({ role }: { role: string }) {
  const { data, isPending, error } = usePracticeQuestions(role);
  const [open, setOpen] = useState<string | null>(null);
  return (
    <Section title="Practice questions" description="Answer out loud or in writing, then get feedback on structure and substance.">
      {isPending ? (
        <Spinner />
      ) : error ? (
        <Alert>Couldn't load questions: {error.message}</Alert>
      ) : (
        <ul className="flex flex-col divide-y divide-line">
          {data.map((q) => (
            <li key={q.id} className="py-4 first:pt-0 last:pb-0">
              <div className="flex flex-wrap items-center gap-2">
                <Badge>{q.category}</Badge>
                <Badge tone={q.difficulty === "Hard" ? "warn" : "neutral"}>{q.difficulty}</Badge>
              </div>
              <p className="mt-2 font-medium">{q.question}</p>
              {open === q.id ? (
                <AnswerBox q={q} onClose={() => setOpen(null)} />
              ) : (
                <Button size="sm" className="mt-3" onClick={() => setOpen(q.id)}>
                  <Mic className="size-4" aria-hidden />
                  Practice this
                </Button>
              )}
            </li>
          ))}
        </ul>
      )}
    </Section>
  );
}

function AnswerBox({ q, onClose }: { q: PracticeQuestion; onClose: () => void }) {
  const evaluate = useAnswerFeedback();
  const [answer, setAnswer] = useState("");
  const result = evaluate.data?.evaluation;
  const tooShort = answer.trim().split(/\s+/).filter(Boolean).length < 15;

  return (
    <div className="mt-3 flex flex-col gap-3">
      <Textarea
        label="Your answer"
        rows={6}
        value={answer}
        onChange={(e) => setAnswer(e.target.value)}
        autoFocus
        hint="Say what the situation was, what you did, and what changed. Numbers help."
      />
      {evaluate.error && <Alert>Couldn't score it: {evaluate.error.message}</Alert>}
      <div className="flex gap-2">
        <Button
          variant="primary"
          loading={evaluate.isPending}
          disabled={tooShort}
          onClick={() => evaluate.mutate({ question: q.question, candidate_answer: answer.trim(), key_concepts: q.key_concepts })}
        >
          {result ? "Score again" : "Get feedback"}
        </Button>
        <Button variant="ghost" onClick={onClose}>
          Close
        </Button>
      </div>

      {result && (
        <div className="mt-1 flex flex-col gap-4 rounded-md border border-line bg-canvas p-4" aria-live="polite">
          <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
            <span className="text-xl font-semibold">{result.overall_score}/100</span>
            <Badge tone={result.overall_score >= 80 ? "ok" : result.overall_score >= 60 ? "neutral" : "warn"}>{plainText(result.rating)}</Badge>
          </div>
          <div className="grid gap-2.5 sm:grid-cols-2">
            {Object.entries(result.dimension_scores).map(([k, v]) => (
              <div key={k}>
                <div className="mb-1 flex justify-between text-xs">
                  <span className="text-ink-2">{DIMENSION_LABELS[k] ?? k}</span>
                  <span className="font-medium">{v}</span>
                </div>
                <div className="h-1.5 overflow-hidden rounded-full bg-subtle" role="meter" aria-label={DIMENSION_LABELS[k] ?? k} aria-valuenow={v} aria-valuemin={0} aria-valuemax={100}>
                  <div className={cx("h-full rounded-full", v >= 75 ? "bg-ok" : v >= 55 ? "bg-accent" : "bg-warn")} style={{ width: `${v}%` }} />
                </div>
              </div>
            ))}
          </div>
          <p>{result.feedback}</p>
          {(result.matched_concepts.length > 0 || result.missing_concepts.length > 0) && (
            <div className="flex flex-col gap-2">
              {result.matched_concepts.length > 0 && (
                <div className="flex flex-wrap items-center gap-1.5">
                  <span className="text-ink-2">You covered:</span>
                  {result.matched_concepts.map((c) => (
                    <Badge key={c} tone="ok">
                      {c}
                    </Badge>
                  ))}
                </div>
              )}
              {result.missing_concepts.length > 0 && (
                <div className="flex flex-wrap items-center gap-1.5">
                  <span className="text-ink-2">Worth mentioning:</span>
                  {result.missing_concepts.map((c) => (
                    <Badge key={c} tone="warn">
                      {c}
                    </Badge>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function AskThem({ company, role }: { company: string; role: string }) {
  const { data, isPending, error } = useAskThem(company, role);
  const all = (data ?? []).map((q) => q.question).join("\n\n");
  return (
    <Section title="Questions to ask them" description="Good questions show you've thought about the job." action={data?.length ? <CopyButton text={all} label="Copy all" /> : undefined}>
      {isPending ? (
        <Spinner />
      ) : error ? (
        <Alert>Couldn't load these: {error.message}</Alert>
      ) : (
        <ul className="flex flex-col gap-4">
          {data.map((q) => (
            <li key={q.question}>
              <p className="text-xs font-medium tracking-wide text-ink-3 uppercase">{plainText(q.theme)}</p>
              <p className="mt-0.5">{q.question}</p>
            </li>
          ))}
        </ul>
      )}
    </Section>
  );
}
