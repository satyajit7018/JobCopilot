import { useEffect, useRef, useState, type FormEvent } from "react";
import { Navigate, useLocation } from "react-router";
import { useQuery } from "@tanstack/react-query";
import { KeyRound } from "lucide-react";
import { api } from "../lib/api";
import { useAuth, type PublicConfig, type SignInResult } from "../lib/auth";
import { Alert, Button, Card, Field } from "../components/ui";

const PASSWORD_MIN = 12; // backend settings.PASSWORD_MIN_LENGTH

type Mode = "signin" | "register";

export function LoginPage() {
  const auth = useAuth();
  const location = useLocation();
  const [mode, setMode] = useState<Mode>("signin");
  const [mfaToken, setMfaToken] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const { data: config } = useQuery({
    queryKey: ["public-config"],
    queryFn: () => api<PublicConfig>("/auth/public-config", { auth: false }),
    staleTime: Infinity,
  });

  if (auth.status === "authenticated") {
    const from = (location.state as { from?: string } | null)?.from ?? "/";
    return <Navigate to={from} replace />;
  }

  const run = async (fn: () => Promise<SignInResult | void>) => {
    setError(null);
    setBusy(true);
    try {
      const result = await fn();
      if (result && !result.done) setMfaToken(result.mfaToken);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong. Please try again.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="flex min-h-dvh flex-col items-center justify-center px-4 py-10">
      <div className="mb-8 flex items-center gap-2 text-lg font-bold">
        <img src="/favicon.svg" alt="" className="size-8" />
        JobCopilot
      </div>
      <Card className="w-full max-w-100 p-6 sm:p-8">
        {mfaToken ? (
          <MfaStep busy={busy} error={error} onSubmit={(code) => run(() => auth.completeMfa(mfaToken, code))} onBack={() => setMfaToken(null)} />
        ) : (
          <>
            <h1 className="text-xl font-semibold">{mode === "signin" ? "Welcome back" : "Create your account"}</h1>
            <p className="mt-1 text-ink-2">
              {mode === "signin" ? "Sign in to see your matches and applications." : "Find better-fit jobs and apply with a tailored resume."}
            </p>

            {config?.google_client_id && (
              <>
                <div className="mt-6">
                  <GoogleButton clientId={config.google_client_id} onCredential={(id_token) => run(() => auth.google({ id_token }))} />
                </div>
                <Divider />
              </>
            )}

            <CredentialsForm
              mode={mode}
              busy={busy}
              error={error}
              onSubmit={(v) => run(() => (mode === "signin" ? auth.login(v.email, v.password) : auth.register(v.name, v.email, v.password)))}
            />

            <p className="mt-6 text-center text-ink-2">
              {mode === "signin" ? "New to JobCopilot? " : "Already have an account? "}
              <button
                type="button"
                className="font-medium text-accent hover:text-accent-hover"
                onClick={() => {
                  setMode(mode === "signin" ? "register" : "signin");
                  setError(null);
                }}
              >
                {mode === "signin" ? "Create an account" : "Sign in"}
              </button>
            </p>

            {config?.demo_enabled && <DemoSignIn busy={busy} onSubmit={(email) => run(() => auth.google({ email }))} />}
          </>
        )}
      </Card>
    </div>
  );
}

function CredentialsForm({
  mode,
  busy,
  error,
  onSubmit,
}: {
  mode: Mode;
  busy: boolean;
  error: string | null;
  onSubmit: (v: { name: string; email: string; password: string }) => void;
}) {
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [touched, setTouched] = useState(false);

  const passwordError = mode === "register" && touched && password.length < PASSWORD_MIN ? `Use at least ${PASSWORD_MIN} characters.` : null;

  const submit = (e: FormEvent) => {
    e.preventDefault();
    setTouched(true);
    if (mode === "register" && password.length < PASSWORD_MIN) return;
    onSubmit({ name: name.trim(), email: email.trim(), password });
  };

  return (
    <form onSubmit={submit} className="mt-6 flex flex-col gap-4" noValidate>
      {mode === "register" && (
        <Field label="Full name" name="name" autoComplete="name" value={name} onChange={(e) => setName(e.target.value)} />
      )}
      <Field label="Email" name="email" type="email" autoComplete="email" required value={email} onChange={(e) => setEmail(e.target.value)} />
      <Field
        label="Password"
        name="password"
        type="password"
        autoComplete={mode === "signin" ? "current-password" : "new-password"}
        required
        value={password}
        onChange={(e) => setPassword(e.target.value)}
        hint={mode === "register" ? `At least ${PASSWORD_MIN} characters.` : undefined}
        error={passwordError}
      />
      {error && <Alert>{error}</Alert>}
      <Button type="submit" variant="primary" size="lg" loading={busy} disabled={!email || !password}>
        {mode === "signin" ? "Sign in" : "Create account"}
      </Button>
    </form>
  );
}

function MfaStep({ busy, error, onSubmit, onBack }: { busy: boolean; error: string | null; onSubmit: (code: string) => void; onBack: () => void }) {
  const [code, setCode] = useState("");
  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        onSubmit(code);
      }}
      className="flex flex-col gap-4"
    >
      <div className="grid size-11 place-items-center rounded-full bg-accent-soft text-accent">
        <KeyRound className="size-5" aria-hidden />
      </div>
      <div>
        <h1 className="text-xl font-semibold">Two-step verification</h1>
        <p className="mt-1 text-ink-2">Enter the 6-digit code from your authenticator app, or one of your backup codes.</p>
      </div>
      <Field
        label="Verification code"
        name="code"
        inputMode="numeric"
        autoComplete="one-time-code"
        autoFocus
        value={code}
        onChange={(e) => setCode(e.target.value)}
      />
      {error && <Alert>{error}</Alert>}
      <Button type="submit" variant="primary" size="lg" loading={busy} disabled={!code.trim()}>
        Verify
      </Button>
      <Button variant="ghost" onClick={onBack}>
        Use a different account
      </Button>
    </form>
  );
}

function Divider() {
  return (
    <div className="my-6 flex items-center gap-3 text-xs text-ink-3">
      <span className="h-px flex-1 bg-line" />
      or
      <span className="h-px flex-1 bg-line" />
    </div>
  );
}

/** Dev-only: the backend accepts a bare email on /auth/google-sso when not in production. */
function DemoSignIn({ busy, onSubmit }: { busy: boolean; onSubmit: (email: string) => void }) {
  const [email, setEmail] = useState("");
  return (
    <details className="mt-6 rounded-md border border-dashed border-line-strong px-3.5 py-2.5">
      <summary className="cursor-pointer text-xs font-medium text-ink-3">Development: sign in without a password</summary>
      <form
        className="mt-3 flex gap-2"
        onSubmit={(e) => {
          e.preventDefault();
          if (email.trim()) onSubmit(email.trim());
        }}
      >
        <input
          aria-label="Demo email"
          type="email"
          placeholder="you@example.com"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          className="h-9 min-w-0 flex-1 rounded-md border border-line-strong px-3 text-sm focus:border-accent focus:outline-none"
        />
        <Button type="submit" size="md" loading={busy} disabled={!email.trim()}>
          Continue
        </Button>
      </form>
    </details>
  );
}

// ---- Google Identity Services --------------------------------------------------------------

interface GoogleId {
  initialize(cfg: { client_id: string; callback: (r: { credential: string }) => void }): void;
  renderButton(el: HTMLElement, opts: Record<string, unknown>): void;
}
declare global {
  interface Window {
    google?: { accounts: { id: GoogleId } };
  }
}

let gisLoader: Promise<void> | null = null;
function loadGis(): Promise<void> {
  gisLoader ??= new Promise((resolve, reject) => {
    const s = document.createElement("script");
    s.src = "https://accounts.google.com/gsi/client";
    s.async = true;
    s.onload = () => resolve();
    s.onerror = () => {
      gisLoader = null;
      reject(new Error("Google sign-in failed to load"));
    };
    document.head.appendChild(s);
  });
  return gisLoader;
}

function GoogleButton({ clientId, onCredential }: { clientId: string; onCredential: (idToken: string) => void }) {
  const ref = useRef<HTMLDivElement>(null);
  const cb = useRef(onCredential);
  cb.current = onCredential;
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let cancelled = false;
    loadGis()
      .then(() => {
        const gid = window.google?.accounts.id;
        if (cancelled || !gid || !ref.current) return;
        gid.initialize({ client_id: clientId, callback: (r) => cb.current(r.credential) });
        gid.renderButton(ref.current, { theme: "outline", size: "large", text: "continue_with", width: ref.current.offsetWidth || 320 });
      })
      .catch(() => !cancelled && setFailed(true));
    return () => {
      cancelled = true;
    };
  }, [clientId]);

  if (failed) return <Alert tone="warn">Google sign-in is unavailable right now. Use your email and password instead.</Alert>;
  return <div ref={ref} className="flex min-h-11 justify-center" />;
}
