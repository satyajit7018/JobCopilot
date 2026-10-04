import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router";
import { useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, ArrowRight, Check, Sparkles } from "lucide-react";
import { Logo } from "../components/AppShell";
import { PreferenceFields, ResumeDrop, SourceFields } from "../components/profile";
import { Alert, Button, Card, Spinner, buttonClass, cx } from "../components/ui";
import { api } from "../lib/api";
import {
  answersFromProfile,
  loadSources,
  needsSetup,
  saveSources,
  setupLater,
  useProfile,
  useQuestionnaire,
  useSaveAnswers,
  useUploadResume,
  type Answers,
  type Profile,
} from "../lib/profile";

const STEPS = ["Your resume", "What you're looking for", "Where to look"];

interface DiscoveryResult {
  status?: string;
  message?: string;
  matched_and_saved?: number;
}

function Stepper({ current }: { current: number }) {
  return (
    <ol className="mb-6 flex items-center justify-center gap-2 sm:mb-8 sm:gap-3" aria-label="Setup progress">
      {STEPS.map((label, i) => {
        const done = i < current;
        const here = i === current;
        return (
          <li key={label} className="flex items-center gap-2 sm:gap-3" aria-current={here ? "step" : undefined}>
            {i > 0 && <span className="h-px w-5 bg-line-strong sm:w-10" aria-hidden />}
            <span className={cx("flex items-center gap-2 font-medium", here ? "text-ink" : done ? "text-ink-2" : "text-ink-3")}>
              <span
                className={cx(
                  "grid size-6 flex-none place-items-center rounded-full border text-xs",
                  done && "border-ok bg-ok text-white",
                  here && "border-accent bg-accent text-white",
                  !done && !here && "border-line-strong",
                )}
              >
                {done ? <Check className="size-3.5" aria-label="done" /> : i + 1}
              </span>
              {/* Only the current step's name shows on phones. */}
              <span className={cx(!here && "hidden sm:inline")}>{label}</span>
            </span>
          </li>
        );
      })}
    </ol>
  );
}

export function SetupPage() {
  const navigate = useNavigate();
  const profile = useProfile();
  const [step, setStep] = useState<number | null>(null);

  // Start at preferences when a resume is already on file.
  useEffect(() => {
    if (step === null && profile.isSuccess) setStep(needsSetup(profile.data) ? 0 : 1);
  }, [step, profile.isSuccess, profile.data]);

  const later = () => {
    setupLater.set();
    navigate("/");
  };

  return (
    <div className="min-h-dvh bg-canvas">
      <header className="flex h-14 items-center px-4 md:px-7">
        <Logo />
        <Button variant="ghost" size="sm" className="ml-auto" onClick={later}>
          Finish later
        </Button>
      </header>
      <main className="mx-auto max-w-2xl px-4 pt-4 pb-16 md:pt-8">
        {profile.isError ? (
          <Alert>Couldn't load your profile: {profile.error.message}</Alert>
        ) : step === null ? (
          <Spinner />
        ) : (
          <>
            <Stepper current={step} />
            {step === 0 && <ResumeStep onDone={() => setStep(1)} />}
            {step === 1 && profile.data && <PreferencesStep profile={profile.data} onBack={() => setStep(0)} onDone={() => setStep(2)} />}
            {step === 2 && <SourcesStep onBack={() => setStep(1)} />}
          </>
        )}
      </main>
    </div>
  );
}

function ResumeStep({ onDone }: { onDone: () => void }) {
  const upload = useUploadResume();
  return (
    <Card className="p-5 sm:p-8">
      <h1 className="text-xl font-semibold sm:text-2xl">Start with your resume</h1>
      <p className="mt-1.5 mb-6 text-ink-2">We'll read it to fill in your profile and find roles that fit. You can change anything afterwards.</p>
      <ResumeDrop busy={upload.isPending} error={upload.error?.message} onSubmit={(input) => upload.mutate(input, { onSuccess: onDone })} />
    </Card>
  );
}

function FoundSummary({ profile }: { profile: Profile }) {
  const parts = [
    profile.skills.length ? `${profile.skills.length} skills` : null,
    profile.experience.length ? `${profile.experience.length} ${profile.experience.length === 1 ? "role" : "roles"}` : null,
    profile.education.length ? "education" : null,
  ].filter(Boolean);
  if (!parts.length) return null;
  return (
    <div className="mb-6 flex items-center gap-2 rounded-md bg-ok-soft px-3.5 py-2.5 font-medium text-ok">
      <Sparkles className="size-4 flex-none" aria-hidden />
      From your resume: {parts.join(", ")}
    </div>
  );
}

function PreferencesStep({ profile, onBack, onDone }: { profile: Profile; onBack: () => void; onDone: () => void }) {
  const questionnaire = useQuestionnaire();
  const save = useSaveAnswers();
  const [answers, setAnswers] = useState<Answers>(() => answersFromProfile(profile));

  const submit = () => {
    const { location, remote_preference, willing_to_relocate, expected_ctc, notice_period_days, work_authorization, years_of_experience } = answers;
    save.mutate(
      {
        location,
        remote_preference,
        willing_to_relocate,
        expected_ctc,
        notice_period_days,
        work_authorization,
        ...(Number.isFinite(years_of_experience) ? { years_of_experience } : {}),
      },
      { onSuccess: onDone },
    );
  };

  return (
    <Card className="p-5 sm:p-8">
      <h1 className="text-xl font-semibold sm:text-2xl">What kind of role are you after?</h1>
      <p className="mt-1.5 mb-6 text-ink-2">We filled this in from your resume. Change anything that's off.</p>
      <FoundSummary profile={profile} />
      {questionnaire.isPending ? (
        <Spinner />
      ) : (
        <PreferenceFields value={answers} onChange={(patch) => setAnswers((a) => ({ ...a, ...patch }))} questions={questionnaire.data?.questions_schema ?? []} />
      )}
      {save.error && (
        <div className="mt-5">
          <Alert>Couldn't save: {save.error.message}</Alert>
        </div>
      )}
      <div className="mt-8 flex justify-between gap-2">
        <Button onClick={onBack}>
          <ArrowLeft className="size-4" aria-hidden />
          New resume
        </Button>
        <Button variant="primary" loading={save.isPending} onClick={submit}>
          Continue
          <ArrowRight className="size-4" aria-hidden />
        </Button>
      </div>
    </Card>
  );
}

function SourcesStep({ onBack }: { onBack: () => void }) {
  const navigate = useNavigate();
  const qc = useQueryClient();
  const [sources, setSources] = useState(loadSources);
  const [searching, setSearching] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);

  const finish = async () => {
    saveSources(sources);
    setSearching(true);
    setProblem(null);
    try {
      const result = await api<DiscoveryResult>("/discovery/run", { method: "POST" });
      if (result.status === "error") throw new Error(result.message ?? "The search didn't finish.");
      await qc.invalidateQueries({ queryKey: ["jobs"] });
      navigate("/jobs", { replace: true });
    } catch (err) {
      setProblem((err as Error).message);
      setSearching(false);
    }
  };

  return (
    <Card className="p-5 sm:p-8">
      <h1 className="text-xl font-semibold sm:text-2xl">Where should we look?</h1>
      <p className="mt-1.5 mb-6 text-ink-2">Pick the job sites you want matches from. You can change this later in your profile.</p>
      <SourceFields value={sources} onChange={setSources} disabled={searching} />
      {problem && (
        <div className="mt-5 flex flex-col gap-3">
          <Alert>Couldn't search for jobs right now: {problem}</Alert>
          <Link to="/jobs" className="text-sm font-medium text-accent hover:underline">
            Skip and go to Jobs
          </Link>
        </div>
      )}
      <div className="mt-8 flex justify-between gap-2">
        <Button onClick={onBack} disabled={searching}>
          <ArrowLeft className="size-4" aria-hidden />
          Back
        </Button>
        <Button variant="primary" loading={searching} onClick={finish}>
          {searching ? "Searching job sites" : problem ? "Try again" : "Find my matches"}
        </Button>
      </div>
      {searching && <p className="mt-3 text-right text-xs text-ink-3" role="status">This can take up to a minute.</p>}
    </Card>
  );
}

/** Shown on Home when the user postponed setup. */
export function SetupReminder() {
  return (
    <Card className="flex flex-col gap-3 p-5 sm:flex-row sm:items-center">
      <div className="flex-1">
        <p className="font-semibold">Finish setting up</p>
        <p className="text-ink-2">Add your resume so we can find jobs that match you.</p>
      </div>
      <Link to="/setup" className={buttonClass("primary")}>
        Continue setup
        <ArrowRight className="size-4" aria-hidden />
      </Link>
    </Card>
  );
}
