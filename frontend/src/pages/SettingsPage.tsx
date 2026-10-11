import { useEffect, useState, type ReactNode } from "react";
import { Link } from "react-router";
import QRCode from "qrcode";
import { Check, Download, Laptop, ShieldCheck, ShieldOff, Sparkles, TriangleAlert } from "lucide-react";
import { PageHeader } from "../components/AppShell";
import { Alert, Badge, Button, Card, CheckRow, ChoiceChips, CopyButton, Field, Spinner, buttonClass } from "../components/ui";
import { GoogleButton } from "../components/GoogleButton";
import { useLiveConsent, useSetLiveConsent } from "../lib/apply";
import { useAuth, usePublicConfig } from "../lib/auth";
import { subscriptionIsLive, useBillingPlan, useCancelPremium, useIsPremium } from "../lib/billing";
import { relativeTime } from "../lib/jobs";
import {
  eventLabel,
  useConfirmMfa,
  useDeleteAccount,
  useDisableMfa,
  useExportData,
  useRevokeSession,
  useSecurityActivity,
  useSessions,
  useStartMfa,
  type MfaSetup,
} from "../lib/settings";

function Section({ title, description, children, tone }: { title: string; description?: string; children: ReactNode; tone?: "danger" }) {
  const id = `sec-${title.toLowerCase().replace(/\W+/g, "-")}`;
  return (
    <section aria-labelledby={id}>
      <h2 id={id} className={tone === "danger" ? "text-base font-semibold text-danger" : "text-base font-semibold"}>
        {title}
      </h2>
      {description && <p className="text-ink-2">{description}</p>}
      <Card className={tone === "danger" ? "mt-3 border-danger/40 p-4 sm:p-5" : "mt-3 p-4 sm:p-5"}>{children}</Card>
    </section>
  );
}

export function SettingsPage() {
  const premium = useIsPremium();
  return (
    <>
      <PageHeader width="max-w-3xl" title="Settings" />
      <div className="mx-auto flex max-w-3xl flex-col gap-8 px-4 py-5 md:px-7 md:py-8">
        <PlanSection />
        {premium && <AutomationSection />}
        <TwoStepSection />
        <DevicesSection />
        <ActivitySection />
        <DataSection />
      </div>
    </>
  );
}

function formatDay(iso: string | null | undefined) {
  return iso ? new Date(iso).toLocaleDateString(undefined, { day: "numeric", month: "long", year: "numeric" }) : null;
}

function PlanSection() {
  const { user } = useAuth();
  const premium = useIsPremium();
  const plan = useBillingPlan();
  const cancel = useCancelPremium();
  const [confirming, setConfirming] = useState(false);
  const sub = plan.data?.subscription;
  const live = subscriptionIsLive(sub);
  const until = formatDay(sub?.current_end);

  return (
    <Section title="Plan">
      {plan.isPending ? (
        <Spinner />
      ) : !premium ? (
        <div className="flex flex-wrap items-center gap-3">
          <div className="flex-1">
            <p className="text-lg font-semibold">Free</p>
            <p className="text-ink-2">Job matches and tracking. Premium adds tailored applications, automatic applying, inbox tracking and interview prep.</p>
          </div>
          <Link to="/plans" className={buttonClass("primary")}>
            <Sparkles className="size-4" aria-hidden />
            See Premium
          </Link>
        </div>
      ) : (
        <div className="flex flex-col gap-3">
          <p className="flex items-center gap-2 text-lg font-semibold">
            <Sparkles className="size-4 text-accent" aria-hidden />
            Premium
          </p>
          {user?.role === "ADMIN" && !live ? (
            <p className="text-ink-2">Included with your admin account.</p>
          ) : sub?.status === "cancelling" ? (
            <p className="text-ink-2">Cancelled. You keep Premium{until ? ` until ${until}` : " until the end of this month"}, then move to Free.</p>
          ) : sub?.status === "pending" ? (
            <Alert tone="warn">Your last payment didn't go through. Razorpay will retry; update your card from the link in their email.</Alert>
          ) : (
            <p className="text-ink-2">{until ? `Renews on ${until}.` : "Renews monthly."} Payments are handled by Razorpay.</p>
          )}
          {cancel.error && <Alert>{cancel.error.message}</Alert>}
          {live && sub?.status !== "cancelling" &&
            (confirming ? (
              <div className="flex flex-wrap items-center gap-2">
                <p className="w-full text-ink-2">Cancel Premium? You'll keep it until the end of the month you've paid for.</p>
                <Button variant="danger" loading={cancel.isPending} onClick={() => cancel.mutate(undefined, { onSuccess: () => setConfirming(false) })}>
                  Cancel Premium
                </Button>
                <Button variant="ghost" onClick={() => setConfirming(false)}>
                  Keep it
                </Button>
              </div>
            ) : (
              <Button className="self-start" onClick={() => setConfirming(true)}>
                Cancel Premium…
              </Button>
            ))}
        </div>
      )}
    </Section>
  );
}

function AutomationSection() {
  const consent = useLiveConsent();
  const set = useSetLiveConsent();
  return (
    <Section title="Applying for you" description="Whether JobCopilot may submit applications. You still approve each one.">
      {consent.isPending ? (
        <Spinner />
      ) : (
        <div className="flex flex-col gap-3">
          <CheckRow
            checked={consent.data === true}
            disabled={set.isPending}
            onChange={(on) => set.mutate(on)}
            title="Let JobCopilot submit applications for me"
            detail="When off, only practice runs are possible: forms are filled in to check them, never submitted."
          />
          {(set.error ?? consent.error) && <Alert>Couldn't update this: {(set.error ?? consent.error)!.message}</Alert>}
        </div>
      )}
    </Section>
  );
}

function TwoStepSection() {
  const { user, refreshUser } = useAuth();
  const enabled = user?.mfa_enabled === true;
  const start = useStartMfa();
  const [setup, setSetup] = useState<MfaSetup | null>(null);
  const [turningOff, setTurningOff] = useState(false);

  return (
    <Section title="Two-step sign-in" description="Ask for a code from your authenticator app when you sign in.">
      {setup ? (
        <MfaEnroll
          setup={setup}
          onDone={async () => {
            await refreshUser();
            setSetup(null);
          }}
          onCancel={() => setSetup(null)}
        />
      ) : turningOff ? (
        <MfaDisable
          onDone={async () => {
            await refreshUser();
            setTurningOff(false);
          }}
          onCancel={() => setTurningOff(false)}
        />
      ) : (
        <div className="flex flex-wrap items-center gap-3">
          <span className="flex flex-1 items-center gap-2">
            {enabled ? <ShieldCheck className="size-5 text-ok" aria-hidden /> : <ShieldOff className="size-5 text-ink-3" aria-hidden />}
            <span className="font-medium">{enabled ? "On" : "Off"}</span>
          </span>
          {enabled ? (
            <Button onClick={() => setTurningOff(true)}>Turn off</Button>
          ) : (
            <Button variant="primary" loading={start.isPending} onClick={() => start.mutate(undefined, { onSuccess: setSetup })}>
              Turn on
            </Button>
          )}
          {start.error && (
            <div className="w-full">
              <Alert>{start.error.message}</Alert>
            </div>
          )}
        </div>
      )}
    </Section>
  );
}

function MfaEnroll({ setup, onDone, onCancel }: { setup: MfaSetup; onDone: () => Promise<void>; onCancel: () => void }) {
  const confirm = useConfirmMfa();
  const [qr, setQr] = useState<string | null>(null);
  const [code, setCode] = useState("");
  const [savedCodes, setSavedCodes] = useState(false);

  useEffect(() => {
    QRCode.toDataURL(setup.provisioning_uri, { margin: 1, width: 192 })
      .then(setQr)
      .catch(() => setQr(null));
  }, [setup.provisioning_uri]);

  return (
    <div className="flex flex-col gap-5">
      <ol className="flex flex-col gap-5">
        <li>
          <p className="font-medium">1. Scan this with your authenticator app</p>
          <div className="mt-3 flex flex-col gap-3 sm:flex-row sm:items-center">
            {qr ? <img src={qr} alt="QR code for your authenticator app" className="size-40 rounded-md border border-line" /> : <Spinner label="Making the code" />}
            <div className="min-w-0">
              <p className="text-ink-2">Can't scan? Enter this key instead:</p>
              <code className="mt-1 block font-mono break-all">{setup.secret}</code>
            </div>
          </div>
        </li>
        <li>
          <div className="flex items-center justify-between gap-2">
            <p className="font-medium">2. Save your backup codes</p>
            <CopyButton text={setup.backup_codes.join("\n")} label="Copy codes" />
          </div>
          <p className="text-ink-2">Each one works once if you lose your phone. Keep them somewhere safe; you won't see them again.</p>
          <ul className="mt-2 grid grid-cols-2 gap-1.5 rounded-md bg-canvas p-3 font-mono sm:grid-cols-4">
            {setup.backup_codes.map((c) => (
              <li key={c}>{c}</li>
            ))}
          </ul>
          <div className="mt-3">
            <CheckRow checked={savedCodes} onChange={setSavedCodes} title="I've saved my backup codes" />
          </div>
        </li>
        <li>
          <p className="mb-2 font-medium">3. Enter the 6-digit code from the app</p>
          <form
            className="flex flex-col gap-3 sm:flex-row sm:items-start"
            onSubmit={(e) => {
              e.preventDefault();
              confirm.mutate(code, { onSuccess: () => void onDone() });
            }}
          >
            <Field
              label="Code"
              name="totp"
              className="sm:w-40"
              inputMode="numeric"
              autoComplete="one-time-code"
              value={code}
              onChange={(e) => setCode(e.target.value)}
              error={confirm.error?.message}
            />
            <div className="flex gap-2 sm:mt-7">
              <Button type="submit" variant="primary" loading={confirm.isPending} disabled={!savedCodes || code.replace(/\D/g, "").length !== 6}>
                Turn on
              </Button>
              <Button variant="ghost" onClick={onCancel}>
                Cancel
              </Button>
            </div>
          </form>
        </li>
      </ol>
    </div>
  );
}

function MfaDisable({ onDone, onCancel }: { onDone: () => Promise<void>; onCancel: () => void }) {
  const disable = useDisableMfa();
  // Google sign-in accounts have no password they know, so a code from the app works too.
  const [method, setMethod] = useState<"password" | "code">("password");
  const [value, setValue] = useState("");
  return (
    <form
      className="flex flex-col gap-3"
      onSubmit={(e) => {
        e.preventDefault();
        disable.mutate(method === "password" ? { password: value } : { code: value.replace(/\s/g, "") }, { onSuccess: () => void onDone() });
      }}
    >
      <p>{method === "password" ? "Enter your password to turn off two-step sign-in." : "Enter the 6-digit code from your authenticator app."}</p>
      {method === "password" ? (
        <Field key="pw" label="Password" name="current-password" type="password" autoComplete="current-password" value={value} onChange={(e) => setValue(e.target.value)} error={disable.error?.message} />
      ) : (
        <Field key="code" label="Code" name="mfa-off-code" className="sm:w-40" inputMode="numeric" autoComplete="one-time-code" value={value} onChange={(e) => setValue(e.target.value)} error={disable.error?.message} />
      )}
      <button
        type="button"
        className="self-start text-sm font-medium text-accent hover:underline"
        onClick={() => {
          setMethod((m) => (m === "password" ? "code" : "password"));
          setValue("");
          disable.reset();
        }}
      >
        {method === "password" ? "Use a code from your app instead" : "Use your password instead"}
      </button>
      <div className="flex gap-2">
        <Button type="submit" variant="primary" loading={disable.isPending} disabled={!value.trim()}>
          Turn off
        </Button>
        <Button variant="ghost" onClick={onCancel}>
          Cancel
        </Button>
      </div>
    </form>
  );
}

function DevicesSection() {
  const sessions = useSessions();
  const revoke = useRevokeSession();
  const others = (sessions.data ?? []).filter((s) => !s.is_current);
  return (
    <Section title="Signed-in devices" description="Sign out anything you don't recognize.">
      {sessions.isPending ? (
        <Spinner />
      ) : sessions.error ? (
        <Alert>Couldn't load devices: {sessions.error.message}</Alert>
      ) : (
        <div className="flex flex-col gap-3">
          <ul className="flex flex-col divide-y divide-line">
            {sessions.data.map((s) => (
              <li key={s.session_id} className="flex items-center gap-3 py-3 first:pt-0 last:pb-0">
                <Laptop className="size-5 flex-none text-ink-3" aria-hidden />
                <div className="min-w-0 flex-1">
                  <p className="flex flex-wrap items-center gap-2 font-medium">
                    {s.device_name}
                    {s.is_current && <Badge tone="ok">This device</Badge>}
                  </p>
                  <p className="text-ink-2">{[s.ip_address, `active ${relativeTime(s.last_active) ?? "recently"}`].filter(Boolean).join(" · ")}</p>
                </div>
                {!s.is_current && (
                  <Button size="sm" variant="ghost" loading={revoke.isPending && revoke.variables === s.session_id} onClick={() => revoke.mutate(s.session_id)}>
                    Sign out
                  </Button>
                )}
              </li>
            ))}
          </ul>
          {revoke.error && <Alert>Couldn't sign that device out: {revoke.error.message}</Alert>}
          {others.length > 1 && (
            <Button className="self-start" loading={revoke.isPending && revoke.variables === "others"} onClick={() => revoke.mutate("others")}>
              Sign out all other devices
            </Button>
          )}
        </div>
      )}
    </Section>
  );
}

function ActivitySection() {
  const activity = useSecurityActivity(10);
  return (
    <Section title="Recent security activity">
      {activity.isPending ? (
        <Spinner />
      ) : activity.error ? (
        <Alert>Couldn't load activity: {activity.error.message}</Alert>
      ) : activity.data.length === 0 ? (
        <p className="text-ink-2">Nothing yet.</p>
      ) : (
        <ul className="flex flex-col gap-2.5">
          {activity.data.map((e) => (
            <li key={e.log_id} className="flex flex-wrap items-baseline justify-between gap-x-4">
              <span className="flex items-center gap-2">
                {e.severity !== "INFO" && <TriangleAlert className="size-4 flex-none text-warn" aria-label="Warning" />}
                {eventLabel(e.event_type)}
              </span>
              <span className="text-xs text-ink-3">{[e.ip_address, relativeTime(e.created_at)].filter(Boolean).join(" · ")}</span>
            </li>
          ))}
        </ul>
      )}
    </Section>
  );
}

type DeleteProof = "google" | "password" | "code";

function DataSection() {
  const { user, logout } = useAuth();
  const { data: config } = usePublicConfig();
  const exportData = useExportData();
  const del = useDeleteAccount();
  const [deleting, setDeleting] = useState(false);
  const [email, setEmail] = useState("");
  const googleOn = !!config?.google_client_id;
  const passwordOn = config?.password_auth_enabled !== false;
  // Google sign-in accounts have no password they know: they confirm with Google or a 2FA code.
  const proofs: { value: DeleteProof; label: string }[] = [
    ...(googleOn ? [{ value: "google" as const, label: "Google" }] : []),
    ...(passwordOn ? [{ value: "password" as const, label: "Password" }] : []),
    { value: "code", label: "Authenticator code" },
  ];
  const [chosen, setChosen] = useState<DeleteProof | null>(null);
  const method = chosen && proofs.some((p) => p.value === chosen) ? chosen : proofs[0].value;
  const [secret, setSecret] = useState("");
  const [googleToken, setGoogleToken] = useState<string | null>(null);
  const emailMatches = email.trim().toLowerCase() === (user?.email ?? "").toLowerCase();
  const ready = emailMatches && (method === "google" ? !!googleToken : !!secret.trim());

  return (
    <>
      <Section title="Your data">
        <div className="flex flex-wrap items-center gap-3">
          <p className="flex-1 text-ink-2">Download everything we store about you as a JSON file.</p>
          <Button loading={exportData.isPending} onClick={() => exportData.mutate()}>
            <Download className="size-4" aria-hidden />
            Download my data
          </Button>
        </div>
        {exportData.error && (
          <div className="mt-3">
            <Alert>Couldn't export: {exportData.error.message}</Alert>
          </div>
        )}
      </Section>

      <Section title="Delete account" tone="danger">
        {!deleting ? (
          <div className="flex flex-wrap items-center gap-3">
            <p className="flex-1 text-ink-2">Permanently erase your profile, applications and history. This can't be undone.</p>
            <Button onClick={() => setDeleting(true)}>Delete account…</Button>
          </div>
        ) : (
          <form
            className="flex flex-col gap-4"
            onSubmit={(e) => {
              e.preventDefault();
              if (!ready) return;
              const proof =
                method === "google" ? { google_id_token: googleToken ?? "" } : method === "password" ? { password: secret } : { mfa_code: secret.replace(/\s/g, "") };
              del.mutate({ confirm_email: email.trim(), ...proof }, { onSuccess: () => void logout() });
            }}
          >
            <Alert>Everything is erased immediately, including any paid subscription. Download your data first if you want a copy.</Alert>
            <Field
              label={`Type your email (${user?.email}) to confirm`}
              name="confirm-email"
              type="email"
              autoComplete="off"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
            {proofs.length > 1 && (
              <ChoiceChips
                label="Confirm it's you with"
                value={method}
                options={proofs}
                onChange={(v) => {
                  setChosen(v);
                  setSecret("");
                  setGoogleToken(null);
                  del.reset();
                }}
              />
            )}
            {method === "google" && config?.google_client_id ? (
              googleToken ? (
                <p className="flex items-center gap-1.5 text-ok" role="status">
                  <Check className="size-4" aria-hidden />
                  Confirmed with Google
                </p>
              ) : (
                <div className="sm:w-80">
                  <GoogleButton clientId={config.google_client_id} text="signin_with" onCredential={setGoogleToken} />
                </div>
              )
            ) : method === "password" ? (
              <Field key="pw" label="Password" name="delete-password" type="password" autoComplete="current-password" value={secret} onChange={(e) => setSecret(e.target.value)} />
            ) : (
              <Field key="code" label="Authenticator code" name="delete-mfa-code" className="sm:w-40" inputMode="numeric" autoComplete="one-time-code" value={secret} onChange={(e) => setSecret(e.target.value)} />
            )}
            {del.error && <Alert>{del.error.message}</Alert>}
            <div className="flex gap-2">
              <Button type="submit" variant="danger" loading={del.isPending} disabled={!ready}>
                Delete my account
              </Button>
              <Button variant="ghost" onClick={() => setDeleting(false)} disabled={del.isPending}>
                Cancel
              </Button>
            </div>
          </form>
        )}
      </Section>
    </>
  );
}
