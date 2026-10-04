// Profile building blocks shared by the setup flow and the Profile page.
import { useRef, useState, type DragEvent } from "react";
import { FileText, Upload } from "lucide-react";
import { Alert, Button, CheckRow, ChoiceChips, Field, Select, Textarea, cx } from "./ui";
import {
  NOTICE_PERIODS,
  RESUME_TYPES,
  SOURCES,
  WORK_MODES,
  noticeLabel,
  resumeFileError,
  withCurrent,
  type Answers,
  type Question,
  type SourceState,
} from "../lib/profile";

/** Drop or pick a resume file, or paste the text. Calls onSubmit with whichever was given. */
export function ResumeDrop({
  onSubmit,
  busy,
  error,
  compact,
}: {
  onSubmit: (input: File | string) => void;
  busy: boolean;
  error?: string | null;
  compact?: boolean;
}) {
  const input = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);
  const [pasting, setPasting] = useState(false);
  const [text, setText] = useState("");
  const [fileError, setFileError] = useState<string | null>(null);
  const [fileName, setFileName] = useState<string | null>(null);

  const take = (file: File | undefined) => {
    if (!file) return;
    const problem = resumeFileError(file);
    setFileError(problem);
    setFileName(file.name);
    if (!problem) onSubmit(file);
  };

  const onDrop = (e: DragEvent) => {
    e.preventDefault();
    setDragging(false);
    if (!busy) take(e.dataTransfer.files[0]);
  };

  const shown = fileError ?? error;

  if (pasting) {
    return (
      <div className="flex flex-col gap-3">
        <Textarea
          label="Resume text"
          rows={compact ? 6 : 10}
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="Paste the full text of your resume"
          autoFocus
        />
        {error && <Alert>{error}</Alert>}
        <div className="flex flex-wrap justify-between gap-2">
          <Button variant="ghost" onClick={() => setPasting(false)} disabled={busy}>
            Upload a file instead
          </Button>
          <Button variant="primary" loading={busy} disabled={text.trim().length < 50} onClick={() => onSubmit(text.trim())}>
            {busy ? "Reading your resume" : "Use this text"}
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-3">
      <div
        onDragOver={(e) => {
          e.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
        className={cx(
          "flex flex-col items-center rounded-lg border-2 border-dashed px-6 text-center transition-colors",
          compact ? "py-6" : "py-10",
          dragging ? "border-accent bg-accent-soft" : "border-line-strong bg-canvas",
        )}
      >
        <div className="mb-3 grid size-11 place-items-center rounded-full bg-accent-soft text-accent">
          {busy ? <FileText className="size-5" aria-hidden /> : <Upload className="size-5" aria-hidden />}
        </div>
        {busy ? (
          <p className="font-medium" role="status">
            Reading {fileName ?? "your resume"}…
          </p>
        ) : (
          <>
            <p className="font-medium">Drop your resume here</p>
            <p className="mt-0.5 text-ink-3">PDF, Word or plain text, up to 10 MB</p>
          </>
        )}
        <input
          ref={input}
          type="file"
          accept={RESUME_TYPES}
          className="sr-only"
          tabIndex={-1}
          aria-hidden
          onChange={(e) => {
            take(e.target.files?.[0]);
            e.target.value = "";
          }}
        />
        <Button className="mt-4" variant={compact ? "secondary" : "primary"} loading={busy} onClick={() => input.current?.click()}>
          {busy ? "Reading" : "Choose a file"}
        </Button>
      </div>
      {shown && <Alert>{shown}</Alert>}
      <button type="button" className="self-center text-sm font-medium text-accent hover:underline" onClick={() => setPasting(true)} disabled={busy}>
        No file handy? Paste the text instead
      </button>
    </div>
  );
}

/** What the user is looking for: work mode, place, pay, start date, authorization, experience. */
export function PreferenceFields({
  value,
  onChange,
  questions,
}: {
  value: Answers;
  onChange: (patch: Partial<Answers>) => void;
  questions: Question[];
}) {
  const authOptions = questions.find((q) => q.id === "work_authorization")?.options ?? [];
  const notice = NOTICE_PERIODS.includes(value.notice_period_days) ? NOTICE_PERIODS : [value.notice_period_days, ...NOTICE_PERIODS];
  const modes = WORK_MODES.some((m) => m.value === value.remote_preference)
    ? WORK_MODES
    : [{ value: value.remote_preference, label: value.remote_preference }, ...WORK_MODES];

  return (
    <div className="flex flex-col gap-5">
      <ChoiceChips label="Work mode" value={value.remote_preference} options={modes} onChange={(v) => onChange({ remote_preference: v })} />
      <div className="grid gap-5 sm:grid-cols-2">
        <Field label="Where you live" name="location" value={value.location} onChange={(e) => onChange({ location: e.target.value })} placeholder="City, country" />
        <Field
          label="Years of experience"
          name="years_of_experience"
          type="number"
          min={0}
          max={60}
          step={0.5}
          value={Number.isFinite(value.years_of_experience) ? value.years_of_experience : ""}
          onChange={(e) => onChange({ years_of_experience: e.target.valueAsNumber })}
        />
      </div>
      <CheckRow
        checked={value.willing_to_relocate}
        onChange={(v) => onChange({ willing_to_relocate: v })}
        title="Open to relocating"
        detail="Include hybrid and on-site roles in other cities."
      />
      <div className="grid gap-5 sm:grid-cols-2">
        <Field
          label="Expected salary"
          name="expected_ctc"
          value={value.expected_ctc}
          onChange={(e) => onChange({ expected_ctc: e.target.value })}
          placeholder="e.g. 28 LPA or $140k"
          hint="Used to answer salary questions on applications."
        />
        <Select
          label="Can start"
          name="notice_period_days"
          value={value.notice_period_days}
          onChange={(e) => onChange({ notice_period_days: Number(e.target.value) })}
          options={notice.map((d) => ({ value: d, label: noticeLabel(d) }))}
        />
      </div>
      <Select
        label="Work authorization"
        name="work_authorization"
        value={value.work_authorization}
        onChange={(e) => onChange({ work_authorization: e.target.value })}
        options={withCurrent(authOptions, value.work_authorization).map((o) => ({ value: o, label: o }))}
      />
    </div>
  );
}

/** Which job sources to show matches from. */
export function SourceFields({ value, onChange, disabled }: { value: SourceState; onChange: (next: SourceState) => void; disabled?: boolean }) {
  const count = SOURCES.filter((s) => value[s.id]).length;
  return (
    <fieldset>
      <legend className="sr-only">Job sources</legend>
      <div className="grid gap-2.5 sm:grid-cols-2">
        {SOURCES.map((s) => (
          <CheckRow
            key={s.id}
            title={s.name}
            detail={s.detail}
            checked={value[s.id]}
            disabled={disabled}
            onChange={(on) => {
              // Keep at least one source on; an empty list would hide every match.
              if (!on && count === 1) return;
              onChange({ ...value, [s.id]: on });
            }}
          />
        ))}
      </div>
    </fieldset>
  );
}
