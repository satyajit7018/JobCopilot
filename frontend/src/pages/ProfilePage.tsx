import { useEffect, useState, type ReactNode } from "react";
import { Navigate } from "react-router";
import { Check, FileText, X } from "lucide-react";
import { PageHeader } from "../components/AppShell";
import { BackgroundEditor, PreferenceFields, ResumeDrop, SourceFields } from "../components/profile";
import { Alert, Badge, Button, Card, Field, Spinner, Textarea } from "../components/ui";
import { relativeTime, useRemoveSkipRule, useSkipRules } from "../lib/jobs";
import {
  answersFromProfile,
  needsSetup,
  useSources,
  saveSources,
  useProfile,
  useQuestionnaire,
  useSaveAnswers,
  useUploadResume,
  type Answers,
  type Profile,
} from "../lib/profile";

const SKILLS_SHOWN = 18;

// Re-uploading a resume rebuilds the profile from scratch, so these are carried over.
const PREFERENCE_KEYS = [
  "expected_ctc",
  "current_ctc",
  "notice_period_days",
  "work_authorization",
  "willing_to_relocate",
  "remote_preference",
  "years_of_experience",
  "why_looking_for_role",
  "current_employer",
] as const satisfies readonly (keyof Answers)[];

function Section({ title, description, children }: { title: string; description?: string; children: ReactNode }) {
  const id = title.toLowerCase().replace(/\W+/g, "-");
  return (
    <section aria-labelledby={id}>
      <h2 id={id} className="text-base font-semibold">
        {title}
      </h2>
      {description && <p className="text-ink-2">{description}</p>}
      <Card className="mt-3 p-4 sm:p-6">{children}</Card>
    </section>
  );
}

export function ProfilePage() {
  const profile = useProfile();
  // Bumped after a resume replacement so the details form reloads from the new profile.
  const [version, setVersion] = useState(0);

  if (profile.isPending) return <Spinner />;
  if (profile.isError)
    return (
      <div className="px-4 py-5 md:px-7">
        <Alert>Couldn't load your profile: {profile.error.message}</Alert>
      </div>
    );
  if (needsSetup(profile.data)) return <Navigate to="/setup" replace />;

  const p = profile.data!;
  const updated = relativeTime(p.updated_at);
  return (
    <>
      <PageHeader title="Profile" subtitle={updated ? `Updated ${updated}` : undefined} />
      <div className="mx-auto flex max-w-3xl flex-col gap-8 px-4 py-5 pb-28 md:px-7 md:py-8">
        <ResumeSection profile={p} onReplaced={() => setVersion((v) => v + 1)} />
        <DetailsForm key={version} profile={p} />
        <Section title="Job sources" description="Matches from sites you turn off are hidden from Jobs.">
          <SourcesEditor />
        </Section>
        <SkipRulesSection />
      </div>
    </>
  );
}

function ResumeSection({ profile, onReplaced }: { profile: Profile; onReplaced: () => void }) {
  const [replacing, setReplacing] = useState(false);
  const [editing, setEditing] = useState(false);
  const upload = useUploadResume();
  const save = useSaveAnswers();

  const replace = (input: File | string) => {
    const before = answersFromProfile(profile);
    const keep = Object.fromEntries(PREFERENCE_KEYS.map((k) => [k, before[k]])) as Partial<Answers>;
    upload.mutate(input, {
      onSuccess: () =>
        save.mutate(keep, {
          onSuccess: () => {
            setReplacing(false);
            onReplaced();
          },
        }),
    });
  };

  const extra = profile.skills.length - SKILLS_SHOWN;
  return (
    <Section title="Resume" description="What we read from your resume. It's used to match jobs and fill in applications, so fix anything we got wrong.">
      {replacing ? (
        <>
          <ResumeDrop compact busy={upload.isPending || save.isPending} error={upload.error?.message ?? save.error?.message} onSubmit={replace} />
          <div className="mt-3 flex justify-end">
            <Button variant="ghost" size="sm" onClick={() => setReplacing(false)} disabled={upload.isPending || save.isPending}>
              Cancel
            </Button>
          </div>
        </>
      ) : editing ? (
        <BackgroundEditor profile={profile} submitLabel="Save changes" onSaved={() => setEditing(false)} onCancel={() => setEditing(false)} />
      ) : (
        <div className="flex flex-col gap-5">
          <div className="flex items-start gap-3">
            <div className="grid size-10 flex-none place-items-center rounded-md bg-accent-soft text-accent">
              <FileText className="size-5" aria-hidden />
            </div>
            <div className="min-w-0 flex-1">
              <p className="font-semibold">{profile.full_name}</p>
              <p className="text-ink-2">{[profile.location, profile.email].filter(Boolean).join(" · ")}</p>
            </div>
            <div className="flex gap-2">
              <Button size="sm" onClick={() => setEditing(true)}>
                Edit
              </Button>
              <Button size="sm" variant="ghost" onClick={() => setReplacing(true)}>
                Replace
              </Button>
            </div>
          </div>

          {profile.summary && <p className="text-ink-2">{profile.summary}</p>}

          {profile.skills.length > 0 && (
            <div>
              <h3 className="mb-2 text-sm font-semibold">Skills</h3>
              <div className="flex flex-wrap gap-1.5">
                {profile.skills.slice(0, SKILLS_SHOWN).map((s) => (
                  <Badge key={s}>{s}</Badge>
                ))}
                {extra > 0 && <Badge tone="accent">+{extra} more</Badge>}
              </div>
            </div>
          )}

          {profile.experience.length > 0 && (
            <div>
              <h3 className="mb-2 text-sm font-semibold">Experience</h3>
              <ul className="flex flex-col gap-2.5">
                {profile.experience.map((x, i) => (
                  <li key={`${x.company}-${i}`} className="flex flex-wrap justify-between gap-x-4">
                    <span>
                      <span className="font-medium">{x.title}</span>
                      <span className="text-ink-2"> · {x.company}</span>
                    </span>
                    <span className="text-ink-3">{[x.start_date, x.end_date].filter(Boolean).join(" – ")}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {profile.education.length > 0 && (
            <div>
              <h3 className="mb-2 text-sm font-semibold">Education</h3>
              <ul className="flex flex-col gap-1.5">
                {profile.education.map((e, i) => (
                  <li key={`${e.institution}-${i}`}>
                    <span className="font-medium">{e.degree}</span>
                    <span className="text-ink-2"> · {e.institution}</span>
                    {e.graduation_year && <span className="text-ink-3"> · {e.graduation_year}</span>}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </Section>
  );
}

function sameAnswers(a: Answers, b: Answers) {
  return (Object.keys(a) as (keyof Answers)[]).every((k) => Object.is(a[k], b[k]));
}

/** Contact details and preferences, saved together with one button. */
function DetailsForm({ profile }: { profile: Profile }) {
  const questionnaire = useQuestionnaire();
  const save = useSaveAnswers();
  const [baseline, setBaseline] = useState(() => answersFromProfile(profile));
  const [answers, setAnswers] = useState(baseline);
  const [saved, setSaved] = useState(false);

  // The "Saved" confirmation clears itself so the bar doesn't cover the page.
  useEffect(() => {
    if (!saved) return;
    const t = setTimeout(() => setSaved(false), 2500);
    return () => clearTimeout(t);
  }, [saved]);

  const set = (patch: Partial<Answers>) => {
    setSaved(false);
    setAnswers((a) => ({ ...a, ...patch }));
  };

  const dirty = !sameAnswers(answers, baseline);
  const nameError = answers.full_name.trim() ? null : "Enter your name.";
  const emailError = /^\S+@\S+\.\S+$/.test(answers.email.trim()) ? null : "Enter a valid email address.";
  const invalid = Boolean(nameError || emailError);

  const submit = () => {
    if (invalid) return;
    const { years_of_experience, ...rest } = answers;
    save.mutate(Number.isFinite(years_of_experience) ? answers : rest, {
      onSuccess: ({ profile: next }) => {
        const fresh = answersFromProfile(next);
        setBaseline(fresh);
        setAnswers(fresh);
        setSaved(true);
      },
    });
  };

  return (
    <form
      className="contents"
      onSubmit={(e) => {
        e.preventDefault();
        submit();
      }}
    >
      <Section title="Contact details" description="Used to fill in application forms.">
        <div className="grid gap-5 sm:grid-cols-2">
          <Field label="Full name" name="full_name" autoComplete="name" value={answers.full_name} error={dirty ? nameError : null} onChange={(e) => set({ full_name: e.target.value })} />
          <Field label="Email" name="email" type="email" autoComplete="email" value={answers.email} error={dirty ? emailError : null} onChange={(e) => set({ email: e.target.value })} />
          <Field label="Phone" name="phone" type="tel" autoComplete="tel" value={answers.phone} onChange={(e) => set({ phone: e.target.value })} />
          <Field label="LinkedIn" name="linkedin_url" type="url" placeholder="https://linkedin.com/in/…" value={answers.linkedin_url} onChange={(e) => set({ linkedin_url: e.target.value })} />
          <Field label="GitHub" name="github_url" type="url" placeholder="https://github.com/…" value={answers.github_url} onChange={(e) => set({ github_url: e.target.value })} />
        </div>
      </Section>

      <Section title="What you're looking for" description="Shapes which jobs you see and how we answer recruiter questions.">
        {questionnaire.isPending ? (
          <Spinner />
        ) : (
          <div className="flex flex-col gap-5">
            <PreferenceFields value={answers} onChange={set} questions={questionnaire.data?.questions_schema ?? []} />
            <Field
              label="Current salary"
              name="current_ctc"
              value={answers.current_ctc}
              onChange={(e) => set({ current_ctc: e.target.value })}
              placeholder="e.g. 18 LPA or $95k"
              hint="Only given when a form asks for it. Left blank, we answer “Prefer not to say”."
            />
            <Field
              label="Current employer"
              name="current_employer"
              value={answers.current_employer}
              onChange={(e) => set({ current_employer: e.target.value })}
              hint="We'll never apply there or show you its jobs."
            />
            <Textarea
              label="Why you're looking"
              name="why_looking_for_role"
              rows={4}
              value={answers.why_looking_for_role}
              onChange={(e) => set({ why_looking_for_role: e.target.value })}
              hint="A few sentences in your own words. We use it as the starting point for “Why this company?” answers."
            />
          </div>
        )}
      </Section>

      {/* Save bar: appears once something changed, stays above the mobile tab bar. */}
      {(dirty || saved || save.error) && (
        <div className="fixed inset-x-0 bottom-18 z-20 px-4 md:bottom-6 md:left-58 md:px-7">
          <div className="mx-auto flex max-w-3xl items-center gap-3 rounded-lg border border-line bg-surface px-4 py-3 shadow-pop">
            <p className="flex-1 text-ink-2" role="status">
              {save.error ? (
                <span className="text-danger">Couldn't save: {save.error.message}</span>
              ) : dirty ? (
                "Unsaved changes"
              ) : (
                <span className="inline-flex items-center gap-1.5 text-ok">
                  <Check className="size-4" aria-hidden />
                  Saved
                </span>
              )}
            </p>
            {dirty && (
              <>
                <Button variant="ghost" onClick={() => setAnswers(baseline)} disabled={save.isPending}>
                  Discard
                </Button>
                <Button type="submit" variant="primary" loading={save.isPending} disabled={invalid}>
                  Save changes
                </Button>
              </>
            )}
          </div>
        </div>
      )}
    </form>
  );
}

function SourcesEditor() {
  return <SourceFields value={useSources()} onChange={saveSources} />;
}

/** What new searches skip, from the reasons given for "Not interested". Hidden until there's something. */
function SkipRulesSection() {
  const rules = useSkipRules();
  const remove = useRemoveSkipRule();
  if (!rules.data?.length) return null;
  return (
    <Section title="Skipped in new searches" description="From the reasons you gave for hiding jobs. Remove one to see those jobs again.">
      <ul className="flex flex-col divide-y divide-line">
        {rules.data.map((r) => (
          <li key={r.id} className="flex items-center gap-3 py-2 first:pt-0 last:pb-0">
            <span className="flex-1">{r.label}</span>
            <Button size="sm" variant="ghost" loading={remove.isPending && remove.variables === r.id} onClick={() => remove.mutate(r.id)}>
              <X className="size-3.5" aria-hidden />
              Remove<span className="sr-only"> {r.label}</span>
            </Button>
          </li>
        ))}
      </ul>
      {remove.error && (
        <div className="mt-3">
          <Alert>Couldn't remove that: {remove.error.message}</Alert>
        </div>
      )}
    </Section>
  );
}
