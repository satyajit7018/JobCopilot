import { useState, type ReactNode } from "react";
import { Link, Navigate } from "react-router";
import { ArrowLeft, ChevronRight } from "lucide-react";
import { PageHeader } from "../components/AppShell";
import { Alert, Badge, Button, Card, ChoiceChips, Field, Group, SkeletonRows, Spinner, Textarea, cx, rowClass } from "../components/ui";
import { usePublicConfig } from "../lib/auth";
import { relativeTime } from "../lib/jobs";
import {
  PREFER_NOT_TO_SAY,
  useApplicationAnswers,
  useDeleteAnswer,
  useEditAnswer,
  usePreparedApplications,
  useSaveCommonAnswer,
  type CommonQuestion,
  type ProfileFact,
  type SavedAnswer,
} from "../lib/answers";

/** Profile → Application answers: everything the app may put on an employer's form. */
export function AnswersPage() {
  const config = usePublicConfig();
  const enabled = usePreparedApplications();
  const answers = useApplicationAnswers();
  if (config.isPending) return <Spinner />;
  if (!enabled) return <Navigate to="/profile" replace />;

  return (
    <>
      <PageHeader width="max-w-3xl" title="Application answers" subtitle="Used to fill in application forms. You check every application before you send it." />
      <div className="mx-auto flex max-w-3xl flex-col gap-8 px-4 py-5 pb-28 md:px-7 md:py-8">
        <Link to="/profile" className="inline-flex items-center gap-1 self-start text-sm font-medium text-ink-2 hover:text-ink">
          <ArrowLeft className="size-4" aria-hidden />
          Profile
        </Link>
        {answers.isPending ? (
          <SkeletonRows rows={4} avatar={false} label="Loading your answers" />
        ) : answers.error ? (
          <Alert>Couldn't load your answers: {answers.error.message}</Alert>
        ) : (
          <>
            <ProfileFacts facts={answers.data.profile} />
            <Section title="Common questions" note="Your answer is used when a form asks the same question.">
              <ul className="flex flex-col divide-y divide-line">
                {answers.data.common.map((q) => (
                  <CommonRow key={q.key} q={q} />
                ))}
              </ul>
            </Section>
            <Section title="Your other answers" note="Answers you give to new questions on application forms are kept here and reused.">
              {answers.data.saved.length === 0 ? (
                <p className="text-ink-2">Nothing yet.</p>
              ) : (
                <ul className="flex flex-col divide-y divide-line">
                  {answers.data.saved.map((a) => (
                    <SavedRow key={a.id} a={a} />
                  ))}
                </ul>
              )}
            </Section>
          </>
        )}
      </div>
    </>
  );
}

function Section({ title, note, children }: { title: string; note?: string; children: ReactNode }) {
  const id = `ans-${title.toLowerCase().replace(/\W+/g, "-")}`;
  return (
    <section aria-labelledby={id}>
      <h2 id={id} className="px-1 text-xs font-normal text-ink-2">
        {title}
      </h2>
      <Card className="mt-2 p-5 sm:p-6">{children}</Card>
      {note && <p className="mt-2 px-1 text-xs text-ink-3">{note}</p>}
    </section>
  );
}

/** Salary, notice period and the rest live in Profile: shown here, edited there. */
function ProfileFacts({ facts }: { facts: ProfileFact[] }) {
  return (
    <Group label="From your profile" note="Forms only get what you've saved in Profile. Anything not saved yet is left for you to answer.">
      <ul>
        {facts.map((f) => (
          <li key={f.key} className={cx(rowClass, "min-h-12 flex-wrap gap-x-3 gap-y-0 after:left-4")}>
            <span className="flex-1">{f.label}</span>
            <span className={cx("max-w-full truncate sm:max-w-[60%]", f.value ? "font-medium" : "text-ink-3")}>{f.value ?? "Not saved yet"}</span>
          </li>
        ))}
        <li>
          <Link to="/profile" className={cx(rowClass, "min-h-12 font-medium text-accent after:left-4 hover:bg-subtle/50")}>
            <span className="flex-1">Edit in Profile</span>
            <ChevronRight className="size-4 text-ink-3" aria-hidden />
          </Link>
        </li>
      </ul>
    </Group>
  );
}

function Updated({ at }: { at: string | null }) {
  const when = relativeTime(at ?? undefined);
  return when ? <p className="mt-1 text-xs text-ink-3">Updated {when}</p> : null;
}

function CommonRow({ q }: { q: CommonQuestion }) {
  const [editing, setEditing] = useState(false);
  const save = useSaveCommonAnswer();
  const submit = (answer: string) =>
    save.mutate({ key: q.key, question: q.question, answer }, { onSuccess: () => setEditing(false) });

  return (
    <li className="py-4 first:pt-0 last:pb-0">
      <div className="flex items-start gap-3">
        <div className="min-w-0 flex-1">
          <p className="font-medium">
            {q.question}
            {q.optional && (
              <Badge className="ml-2 align-middle">Optional</Badge>
            )}
          </p>
          {!editing && (
            <>
              <p className={cx("mt-1 whitespace-pre-line", q.answer ? "text-ink-2" : "text-ink-3")}>{q.answer ?? "Not answered yet"}</p>
              <Updated at={q.confirmed_at} />
            </>
          )}
        </div>
        {!editing && (
          <Button size="sm" onClick={() => setEditing(true)}>
            {q.id ? "Edit" : q.answer ? "Change" : "Answer"}
            <span className="sr-only"> {q.question}</span>
          </Button>
        )}
      </div>
      {editing && (
        <AnswerEditor
          label={q.question}
          initial={q.answer ?? ""}
          options={q.options}
          multiline={q.kind === "text"}
          saving={save.isPending}
          error={save.error?.message}
          onSave={submit}
          onCancel={() => setEditing(false)}
        />
      )}
    </li>
  );
}

function SavedRow({ a }: { a: SavedAnswer }) {
  const [editing, setEditing] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const edit = useEditAnswer();
  const remove = useDeleteAnswer();

  return (
    <li className="py-4 first:pt-0 last:pb-0">
      <div className="flex items-start gap-3">
        <div className="min-w-0 flex-1">
          <p className="font-medium">{a.question}</p>
          {a.for_job && (
            <p className="text-xs text-ink-2">
              Only for{" "}
              <Link to={`/jobs/${a.for_job.job_id}`} className="font-medium text-accent hover:underline">
                {a.for_job.title} at {a.for_job.company}
              </Link>
            </p>
          )}
          {!editing && (
            <>
              <p className="mt-1 whitespace-pre-line text-ink-2">{a.answer}</p>
              {a.wordings.length > 0 && (
                <p className="mt-1 text-xs text-ink-3">Also used for: {a.wordings.map((w) => `“${w}”`).join(", ")}</p>
              )}
              <Updated at={a.confirmed_at ?? a.last_used_at} />
            </>
          )}
        </div>
        {!editing && !confirming && (
          <div className="flex flex-none gap-1">
            <Button size="sm" onClick={() => setEditing(true)}>
              Edit<span className="sr-only"> {a.question}</span>
            </Button>
            <Button size="sm" variant="ghost" onClick={() => setConfirming(true)}>
              Delete<span className="sr-only"> {a.question}</span>
            </Button>
          </div>
        )}
      </div>
      {confirming && (
        <div className="mt-3 flex flex-wrap items-center gap-2">
          <p className="w-full text-ink-2">Delete this answer? The next form that asks will leave it for you.</p>
          <Button variant="danger" size="sm" loading={remove.isPending} onClick={() => remove.mutate(a.id)}>
            Delete
          </Button>
          <Button variant="ghost" size="sm" onClick={() => setConfirming(false)} disabled={remove.isPending}>
            Keep it
          </Button>
          {remove.error && <Alert>Couldn't delete it: {remove.error.message}</Alert>}
        </div>
      )}
      {editing && (
        <AnswerEditor
          label={a.question}
          initial={a.answer}
          multiline
          saving={edit.isPending}
          error={edit.error?.message}
          onSave={(answer) => edit.mutate({ id: a.id, answer }, { onSuccess: () => setEditing(false) })}
          onCancel={() => setEditing(false)}
        />
      )}
    </li>
  );
}

/** Inline editor: chips for a personal question's usual answers, a text box for the rest. */
function AnswerEditor({
  label,
  initial,
  options,
  multiline,
  saving,
  error,
  onSave,
  onCancel,
}: {
  label: string;
  initial: string;
  options?: string[];
  multiline?: boolean;
  saving: boolean;
  error?: string;
  onSave: (answer: string) => void;
  onCancel: () => void;
}) {
  const [value, setValue] = useState(initial);
  const choices = options && options.length > 1 ? options : null;
  const typed = !choices || !choices.includes(value);
  const trimmed = value.trim();

  return (
    <form
      className="mt-3 flex flex-col gap-3"
      onSubmit={(e) => {
        e.preventDefault();
        if (trimmed) onSave(trimmed);
      }}
    >
      {choices && (
        <ChoiceChips label={`Your answer to “${label}”`} value={typed ? "" : value} options={choices.map((o) => ({ value: o, label: o }))} onChange={setValue} />
      )}
      {!choices && options?.length === 1 ? (
        <Field label="Your answer" value={value} placeholder={PREFER_NOT_TO_SAY} onChange={(e) => setValue(e.target.value)} hint={`Leave it as “${PREFER_NOT_TO_SAY}” if you'd rather not say.`} />
      ) : (
        !choices &&
        (multiline ? (
          <Textarea label="Your answer" rows={4} value={value} onChange={(e) => setValue(e.target.value)} />
        ) : (
          <Field label="Your answer" value={value} onChange={(e) => setValue(e.target.value)} />
        ))
      )}
      {error && <Alert>Couldn't save: {error}</Alert>}
      <div className="flex gap-2">
        <Button type="submit" variant="primary" size="sm" loading={saving} disabled={!trimmed}>
          Save
        </Button>
        <Button variant="ghost" size="sm" onClick={onCancel} disabled={saving}>
          Cancel
        </Button>
      </div>
    </form>
  );
}
