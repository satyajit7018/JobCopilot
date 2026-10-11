// Privacy Policy and Terms. Public pages (no sign-in), written to match what the app does.
// Operator name and support email come from the server (OPERATOR_NAME, SUPPORT_EMAIL).
import { usePageTitle } from "../lib/pageTitle";
import type { ReactNode } from "react";
import { Link } from "react-router";
import { ArrowLeft } from "lucide-react";
import { usePublicConfig } from "../lib/auth";

const EFFECTIVE = "9 October 2026";

function useOperator() {
  const { data } = usePublicConfig();
  return {
    name: data?.operator_name || "the operator of JobCopilot",
    email: data?.support_email || "",
  };
}

function Mail({ email }: { email: string }) {
  return email ? (
    <a href={`mailto:${email}`} className="font-medium text-accent hover:underline">
      {email}
    </a>
  ) : (
    <>the contact address on our Help page</>
  );
}

function LegalLayout({ title, children, effective = true }: { title: string; children: ReactNode; effective?: boolean }) {
  usePageTitle(title);
  return (
    <div className="min-h-dvh bg-canvas">
      <header className="flex h-14 items-center gap-2 border-b border-line bg-surface px-4 md:px-7">
        <Link to="/" className="flex items-center gap-2 font-bold">
          <img src="/favicon.svg" alt="" className="size-7" />
          JobCopilot
        </Link>
      </header>
      <main className="mx-auto max-w-3xl px-4 py-8 md:px-7">
        <Link to="/" className="mb-6 inline-flex items-center gap-1 text-sm font-medium text-ink-2 hover:text-ink">
          <ArrowLeft className="size-4" aria-hidden />
          Back to JobCopilot
        </Link>
        <h1 className="text-2xl font-semibold">{title}</h1>
        {effective && <p className="mt-1 text-ink-3">Effective {EFFECTIVE}</p>}
        <div className="legal mt-6 flex flex-col gap-6 leading-relaxed text-ink-2 [&_h2]:mb-2 [&_h2]:text-base [&_h2]:font-semibold [&_h2]:text-ink [&_li]:ml-5 [&_li]:list-disc [&_ul]:flex [&_ul]:flex-col [&_ul]:gap-1">
          {children}
        </div>
        <p className="mt-10 text-sm text-ink-3">
          <Link to="/privacy" className="hover:text-ink hover:underline">
            Privacy Policy
          </Link>
          {" · "}
          <Link to="/terms" className="hover:text-ink hover:underline">
            Terms of Service
          </Link>
          {" · "}
          <Link to="/help" className="hover:text-ink hover:underline">
            Help
          </Link>
        </p>
      </main>
    </div>
  );
}

export function PrivacyPage() {
  const op = useOperator();
  return (
    <LegalLayout title="Privacy Policy">
      <section>
        <p>
          JobCopilot is run by {op.name} ("we"). This policy explains what we collect when you use JobCopilot, why, and the choices you have.
          Questions or requests: <Mail email={op.email} />.
        </p>
      </section>

      <section>
        <h2>What we collect</h2>
        <ul>
          <li>
            <strong>Account:</strong> your name and email address from Google sign-in.
          </li>
          <li>
            <strong>Your resume and profile:</strong> the resume you upload and what we read from it (contact details, skills, work history, education,
            projects), plus the preferences you give us (such as expected salary, notice period and the kind of work you want). Phone number,
            location, salary and similar details are stored encrypted.
          </li>
          <li>
            <strong>Your job search:</strong> job matches, applications you track, their status and dates, interview dates and notes.
          </li>
          <li>
            <strong>Premium features:</strong> if you use inbox tracking, the emails you send to your JobCopilot tracking address; if you use automatic
            applying, the applications we prepare and submit for you and their results.
          </li>
          <li>
            <strong>Payments:</strong> Premium payments are handled by Razorpay. We never see or store your card or bank details; we keep your
            subscription's ID, status and renewal date.
          </li>
          <li>
            <strong>Security:</strong> sign-in sessions (device type, IP address, time) and a log of security events such as sign-ins and password or
            two-step changes.
          </li>
          <li>
            <strong>Feedback</strong> you send us, and technical error reports when something breaks (these may include the page you were on and your
            account ID, but not your resume).
          </li>
        </ul>
      </section>

      <section>
        <h2>How we use it</h2>
        <ul>
          <li>To find jobs that match you, explain the match, and track your applications.</li>
          <li>With Premium: to write tailored resumes, cover letters and emails, to apply for you once you approve each application, and to update your
            applications from recruiter replies.</li>
          <li>To run your account: sign-in, security, billing and support.</li>
          <li>To find and fix problems with the service.</li>
        </ul>
        <p className="mt-2">We do not sell your data, and we do not use it for advertising.</p>
      </section>

      <section>
        <h2>Who we share it with</h2>
        <ul>
          <li>
            <strong>Employers you apply to:</strong> when you apply (yourself, or with Premium automatic applying after you approve it), the employer
            receives what the application needs: your resume, contact details and answers.
          </li>
          <li>
            <strong>Service providers</strong> that run JobCopilot for us: our cloud hosting provider, Google (sign-in), Razorpay (payments), an AI
            provider when JobCopilot writes text for you, and our error-monitoring service. They may only use your data to provide their service to
            us.
          </li>
          <li>When the law requires it.</li>
        </ul>
      </section>

      <section>
        <h2>Storage and retention</h2>
        <p>
          Your data is kept while your account is open. Database backups are kept for up to 14 days, so deleted data disappears from backups within
          14 days. Security logs and records of the consents you gave are kept after deletion where the law requires us to be able to show them.
        </p>
      </section>

      <section>
        <h2>Your choices and rights</h2>
        <ul>
          <li>
            <strong>See and correct</strong> your details any time on the Profile page.
          </li>
          <li>
            <strong>Download</strong> everything we store about you: Settings → Your data → Download my data.
          </li>
          <li>
            <strong>Delete</strong> your account and data: Settings → Delete account. It takes effect immediately and cancels any subscription.
          </li>
          <li>
            <strong>Withdraw consent</strong> for automatic applying in Settings at any time.
          </li>
          <li>
            For anything else, including complaints, email <Mail email={op.email} />. We reply within 30 days.
          </li>
        </ul>
      </section>

      <section>
        <h2>Cookies and browser storage</h2>
        <p>
          We don't use advertising or tracking cookies. JobCopilot keeps your sign-in and a few display preferences in your browser's local storage.
          Google's sign-in button and, when you pay, Razorpay's checkout load their own scripts under their own privacy policies.
        </p>
      </section>

      <section>
        <h2>Children</h2>
        <p>JobCopilot is for people aged 18 and over.</p>
      </section>

      <section>
        <h2>Changes</h2>
        <p>If we change this policy in a way that matters, we'll tell you in the app before it takes effect.</p>
      </section>
    </LegalLayout>
  );
}

export function TermsPage() {
  const op = useOperator();
  return (
    <LegalLayout title="Terms of Service">
      <section>
        <p>
          These terms are an agreement between you and {op.name}, who runs JobCopilot. By using JobCopilot you agree to them. Questions:{" "}
          <Mail email={op.email} />.
        </p>
      </section>

      <section>
        <h2>The service</h2>
        <p>
          JobCopilot finds job postings that match your profile and helps you apply and keep track. The Free plan includes matches and tracking.
          Premium adds tailored applications, automatic applying with your approval, inbox tracking and interview prep. We may change features over
          time.
        </p>
      </section>

      <section>
        <h2>Your account</h2>
        <ul>
          <li>You must be 18 or older.</li>
          <li>Keep your sign-in secure; you're responsible for what happens in your account.</li>
          <li>The information you give us must be true. Don't create accounts for other people.</li>
        </ul>
      </section>

      <section>
        <h2>Applications and AI-written text</h2>
        <ul>
          <li>
            JobCopilot can draft resumes, cover letters and emails. Read them before they're used; you are responsible for what is sent in your
            name.
          </li>
          <li>
            Automatic applying only submits an application after you approve it. Some job sites don't allow automated applications; you decide
            whether to use it, and you're responsible for following the rules of the sites you apply through.
          </li>
          <li>
            Match scores are estimates. We don't guarantee interviews, offers, or that a posting is accurate or still open. Postings come from
            employers and job boards, not from us.
          </li>
        </ul>
      </section>

      <section>
        <h2>Acceptable use</h2>
        <p>
          Don't misuse JobCopilot: no attempts to break or overload it, access other people's data, scrape it, resell it, or use it to send spam or
          misleading applications. We may suspend accounts that do.
        </p>
      </section>

      <section>
        <h2>Premium, payments and refunds</h2>
        <ul>
          <li>
            Premium is a monthly subscription, charged in advance through Razorpay: ₹199 per month in India or US$5 per month elsewhere (plus any
            applicable taxes), at the price shown when you subscribe.
          </li>
          <li>It renews every month until you cancel. Cancel any time in Settings; you keep Premium until the end of the month you've paid for.</li>
          <li>
            Payments are not refunded for partial months, except where the law requires a refund or we charged you by mistake. If you think you were
            charged wrongly, email <Mail email={op.email} /> within 30 days and we'll make it right.
          </li>
          <li>If a renewal payment fails, Razorpay retries it; if it keeps failing, your account moves to the Free plan.</li>
          <li>We'll tell you at least 30 days before any price change affects your subscription.</li>
        </ul>
      </section>

      <section>
        <h2>Ending your account</h2>
        <p>
          You can delete your account at any time in Settings. We may suspend or close accounts that break these terms; where it's reasonable, we'll
          tell you first.
        </p>
      </section>

      <section>
        <h2>Liability</h2>
        <p>
          JobCopilot is provided "as is". To the extent the law allows, we aren't liable for indirect losses, lost opportunities or decisions made by
          employers, and our total liability to you is limited to the amount you paid us in the 12 months before the claim. Nothing in these terms
          limits rights you have under consumer law.
        </p>
      </section>

      <section>
        <h2>Changes and law</h2>
        <p>
          If we change these terms in a way that matters, we'll tell you in the app before it takes effect. These terms are governed by the laws of
          India.
        </p>
      </section>
    </LegalLayout>
  );
}

const FAQ: { q: string; a: ReactNode }[] = [
  {
    q: "How does JobCopilot find jobs for me?",
    a: (
      <>
        Every hour we check the career pages of tech companies, startup job boards and Instahyre for new postings, and score each one against your resume
        and preferences. Only good matches show up in Jobs. You can also press <strong>Find new jobs</strong> to check right away.
      </>
    ),
  },
  {
    q: "What does the match score mean?",
    a: (
      <>
        It combines how many of the skills a posting asks for are on your resume, whether the role is the kind you do, your experience level, and
        location. A job only scores high when several skills match. Open a job to see the reasons and the skills you're missing.
      </>
    ),
  },
  {
    q: "Some details from my resume are wrong.",
    a: (
      <>
        Go to <Link to="/profile" className="text-accent hover:underline">Profile</Link> and press <strong>Edit</strong> next to your resume to fix
        skills, work history and education. Your matches use these details, so it's worth getting them right.
      </>
    ),
  },
  {
    q: "I don't want to see a job again.",
    a: <>Press the hide button on the job in Jobs. It won't come back in future searches. Use Save to keep a job for later.</>,
  },
  {
    q: "What do I get with Premium?",
    a: (
      <>
        A resume and cover letter tailored to each job, automatic applying (you approve each application first), recruiter replies tracked from
        your inbox, follow-up emails drafted for you, and interview prep. See <Link to="/plans" className="text-accent hover:underline">Plans</Link>.
      </>
    ),
  },
  {
    q: "How do I cancel Premium?",
    a: <>Settings → Plan → Cancel Premium. You keep Premium until the end of the month you've paid for, and you won't be charged again.</>,
  },
  {
    q: "How do I download or delete my data?",
    a: (
      <>
        Settings → Your data → <strong>Download my data</strong> gives you everything we store. Settings → <strong>Delete account</strong> erases
        your account and data immediately. Details are in the <Link to="/privacy" className="text-accent hover:underline">Privacy Policy</Link>.
      </>
    ),
  },
];

export function HelpPage() {
  const op = useOperator();
  return (
    <LegalLayout title="Help" effective={false}>
      <section className="flex flex-col gap-2">
        {FAQ.map(({ q, a }) => (
          <details key={q} className="group rounded-lg border border-line bg-surface px-4 py-3 open:pb-4">
            <summary className="cursor-pointer list-none font-medium text-ink marker:hidden">
              <span className="mr-2 inline-block text-ink-3 transition-transform group-open:rotate-90" aria-hidden>
                ›
              </span>
              {q}
            </summary>
            <div className="mt-2 pl-5">{a}</div>
          </details>
        ))}
      </section>

      <section>
        <h2>Still stuck?</h2>
        <p>
          Use <strong>Send feedback</strong> in the menu under your name, or email <Mail email={op.email} />. We usually reply within two working
          days.
        </p>
      </section>
    </LegalLayout>
  );
}
