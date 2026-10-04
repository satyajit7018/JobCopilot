// Questions an application paused on. Answering one resumes that application.
import { useState } from "react";
import { ExternalLink, MessageCircleQuestion } from "lucide-react";
import { Alert, Button, Card, CheckRow, CompanyMark, Select, Textarea, buttonClass } from "./ui";
import { useAnswerHeld, useHeldQuestions, type HeldQuestion } from "../lib/apply";
import { useJobs } from "../lib/jobs";

// The bot can't take these from a text box; the user has to finish them on the site.
const ON_SITE_ONLY = new Set(["captcha", "file"]);

export function HeldQuestions() {
  const { data } = useHeldQuestions();
  if (!data?.length) return null;

  return (
    <section aria-labelledby="held" className="mb-6">
      <h2 id="held" className="mb-1 flex items-center gap-2 text-base font-semibold">
        <MessageCircleQuestion className="size-4 text-warn" aria-hidden />
        Needs your answer
        <span className="font-normal text-ink-3">{data.length}</span>
      </h2>
      <p className="mb-3 text-ink-2">These applications are paused on a question we couldn't answer for you.</p>
      <div className="grid gap-3 lg:grid-cols-2">
        {data.map((q) => (
          <QuestionCard key={q.event_id} q={q} />
        ))}
      </div>
    </section>
  );
}

function QuestionCard({ q }: { q: HeldQuestion }) {
  const answer = useAnswerHeld();
  const { data: jobs } = useJobs();
  const url = jobs?.find((j) => j.job_id === q.job_id)?.url;
  // Never preselect an option: the user has to choose what's sent to the employer.
  const [text, setText] = useState(q.input_type === "select" ? "" : q.ai_suggested_draft);
  const [remember, setRemember] = useState(true);
  const onSite = ON_SITE_ONLY.has(q.input_type);

  return (
    <Card className="flex flex-col gap-3 p-4">
      <div className="flex items-start gap-3">
        <CompanyMark name={q.company} size="sm" />
        <div className="min-w-0">
          <p className="font-semibold">{q.company}</p>
          <p className="truncate text-ink-2">{q.role_title}</p>
        </div>
      </div>

      {onSite ? (
        <>
          <p>
            {q.input_type === "captcha" ? "The site showed a security check." : "The form asked for a file we don't have."} Finish this step on
            the employer's site.
          </p>
          {url && (
            <a href={url} target="_blank" rel="noopener noreferrer" className={buttonClass("secondary", "md", "self-start")}>
              Open the application
              <ExternalLink className="size-3.5" aria-hidden />
              <span className="sr-only">(opens in a new tab)</span>
            </a>
          )}
        </>
      ) : (
        <form
          className="flex flex-col gap-3"
          onSubmit={(e) => {
            e.preventDefault();
            if (text.trim()) answer.mutate({ event_id: q.event_id, user_answer: text.trim(), save_to_vault: remember });
          }}
        >
          {q.input_type === "select" && q.options.length ? (
            <Select
              label={q.question_text}
              value={text}
              onChange={(e) => setText(e.target.value)}
              options={[{ value: "", label: "Choose an answer" }, ...q.options.map((o) => ({ value: o, label: o }))]}
            />
          ) : (
            <Textarea
              label={q.question_text}
              rows={q.input_type === "text" ? 2 : 4}
              value={text}
              onChange={(e) => setText(e.target.value)}
              hint={q.ai_suggested_draft ? "We drafted this. Edit it so it's true for you." : undefined}
            />
          )}
          <CheckRow checked={remember} onChange={setRemember} title="Remember this answer" detail="Reuse it when another form asks the same thing." />
          {answer.error && <Alert>Couldn't send your answer: {answer.error.message}</Alert>}
          <Button type="submit" variant="primary" className="self-start" loading={answer.isPending} disabled={!text.trim()}>
            Answer and continue
          </Button>
        </form>
      )}
    </Card>
  );
}
