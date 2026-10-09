// Profile building blocks shared by the setup flow and the Profile page.
import { useRef, useState, type DragEvent } from "react";
import { FileText, Plus, Upload, X } from "lucide-react";
import { Alert, Button, CheckRow, ChoiceChips, Field, Select, Textarea, cx } from "./ui";
import {
  NOTICE_PERIODS,
  RESUME_TYPES,
  SOURCES,
  WORK_MODES,
  noticeLabel,
  resumeFileError,
  withCurrent,
  splitSkills,
  useSaveBackground,
  type Answers,
  type Education,
  type Experience,
  type Profile,
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

// --- Skills, work history and education ---------------------------------------------

const blankJob = (): Experience => ({ title: "", company: "", start_date: "", end_date: "", highlights: [] });
const blankSchool = (): Education => ({ degree: "", institution: "", graduation_year: "" });

/** Edit what was read from the resume. Used in setup ("check what we read") and on Profile. */
export function BackgroundEditor({
  profile,
  submitLabel,
  onSaved,
  onCancel,
}: {
  profile: Profile;
  submitLabel: string;
  onSaved: () => void;
  onCancel?: () => void;
}) {
  const save = useSaveBackground();
  const [skills, setSkills] = useState<string[]>(profile.skills);
  const [newSkill, setNewSkill] = useState("");
  const [jobs, setJobs] = useState<Experience[]>(profile.experience.length ? profile.experience : [blankJob()]);
  const [schools, setSchools] = useState<Education[]>(profile.education.length ? profile.education : [blankSchool()]);

  const addSkills = () => {
    const extra = splitSkills(newSkill).filter((s) => !skills.some((k) => k.toLowerCase() === s.toLowerCase()));
    if (extra.length) setSkills([...skills, ...extra]);
    setNewSkill("");
  };
  const editJob = (i: number, patch: Partial<Experience>) => setJobs(jobs.map((j, k) => (k === i ? { ...j, ...patch } : j)));
  const editSchool = (i: number, patch: Partial<Education>) => setSchools(schools.map((e, k) => (k === i ? { ...e, ...patch } : e)));

  return (
    <form
      className="flex flex-col gap-6"
      onSubmit={(e) => {
        e.preventDefault();
        const pending = splitSkills(newSkill).filter((s) => !skills.some((k) => k.toLowerCase() === s.toLowerCase()));
        save.mutate({ skills: [...skills, ...pending], experience: jobs, education: schools }, { onSuccess: onSaved });
      }}
    >
      <fieldset>
        <legend className="mb-2 font-semibold">Skills</legend>
        <ul className="mb-2 flex flex-wrap gap-1.5" aria-label="Your skills">
          {skills.map((s) => (
            <li key={s} className="inline-flex h-7 items-center gap-1 rounded-full border border-line bg-subtle pr-1 pl-2.5 text-sm">
              {s}
              <button
                type="button"
                className="grid size-5 place-items-center rounded-full text-ink-3 hover:bg-line hover:text-ink"
                onClick={() => setSkills(skills.filter((k) => k !== s))}
              >
                <X className="size-3" aria-hidden />
                <span className="sr-only">Remove {s}</span>
              </button>
            </li>
          ))}
          {skills.length === 0 && <li className="text-ink-3">No skills yet.</li>}
        </ul>
        <div className="flex gap-2">
          <Field
            label="Add skills"
            hint="Separate several with commas."
            name="new-skill"
            value={newSkill}
            className="flex-1"
            onChange={(e) => setNewSkill(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                e.preventDefault();
                addSkills();
              }
            }}
          />
          <Button className="mt-6.5 self-start" onClick={addSkills} disabled={!newSkill.trim()}>
            Add
          </Button>
        </div>
      </fieldset>

      <fieldset className="flex flex-col gap-3">
        <legend className="mb-2 font-semibold">Work history</legend>
        {jobs.map((j, i) => (
          <div key={i} className="grid gap-2 rounded-md border border-line p-3 sm:grid-cols-2">
            <Field label="Job title" name={`job-title-${i}`} value={j.title} onChange={(e) => editJob(i, { title: e.target.value })} />
            <Field label="Company" name={`job-company-${i}`} value={j.company} onChange={(e) => editJob(i, { company: e.target.value })} />
            <Field label="Started" hint="e.g. Jan 2022" name={`job-start-${i}`} value={j.start_date} onChange={(e) => editJob(i, { start_date: e.target.value })} />
            <Field label="Ended" hint="Leave as Present if you work there now" name={`job-end-${i}`} value={j.end_date} onChange={(e) => editJob(i, { end_date: e.target.value })} />
            <button type="button" className="justify-self-start text-sm font-medium text-ink-2 hover:text-danger" onClick={() => setJobs(jobs.filter((_, k) => k !== i))}>
              Remove this job
            </button>
          </div>
        ))}
        <Button className="self-start" onClick={() => setJobs([...jobs, { ...blankJob(), end_date: "Present" }])}>
          <Plus className="size-4" aria-hidden />
          Add a job
        </Button>
      </fieldset>

      <fieldset className="flex flex-col gap-3">
        <legend className="mb-2 font-semibold">Education</legend>
        {schools.map((e, i) => (
          <div key={i} className="grid gap-2 rounded-md border border-line p-3 sm:grid-cols-[1fr_1fr_8rem]">
            <Field label="Degree" name={`edu-degree-${i}`} value={e.degree} onChange={(ev) => editSchool(i, { degree: ev.target.value })} />
            <Field label="School" name={`edu-school-${i}`} value={e.institution} onChange={(ev) => editSchool(i, { institution: ev.target.value })} />
            <Field label="Year" name={`edu-year-${i}`} inputMode="numeric" value={e.graduation_year ?? ""} onChange={(ev) => editSchool(i, { graduation_year: ev.target.value })} />
            <button type="button" className="justify-self-start text-sm font-medium text-ink-2 hover:text-danger" onClick={() => setSchools(schools.filter((_, k) => k !== i))}>
              Remove
            </button>
          </div>
        ))}
        <Button className="self-start" onClick={() => setSchools([...schools, blankSchool()])}>
          <Plus className="size-4" aria-hidden />
          Add education
        </Button>
      </fieldset>

      {save.error && <Alert>Couldn't save: {save.error.message}</Alert>}
      <div className="flex flex-wrap gap-2">
        <Button type="submit" variant="primary" loading={save.isPending}>
          {submitLabel}
        </Button>
        {onCancel && (
          <Button variant="ghost" onClick={onCancel} disabled={save.isPending}>
            Cancel
          </Button>
        )}
      </div>
    </form>
  );
}
