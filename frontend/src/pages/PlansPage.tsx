import { useState } from "react";
import { Link } from "react-router";
import { Check, Minus, Sparkles } from "lucide-react";
import { PageHeader } from "../components/AppShell";
import { Alert, Badge, Button, Card, Spinner, cx } from "../components/ui";
import { CheckoutDismissed, PLAN_FEATURES, detectRegion, formatPrice, useBillingPlan, useIsPremium, useUpgrade, type Region } from "../lib/billing";

export function PlansPage() {
  const plan = useBillingPlan();
  const premium = useIsPremium();
  const upgrade = useUpgrade();
  const [region, setRegion] = useState<Region>(() => detectRegion());
  const p = plan.data;
  const price = p?.prices[region];
  const error = upgrade.error && !(upgrade.error instanceof CheckoutDismissed) ? upgrade.error : null;

  return (
    <>
      <PageHeader title="Plans" />
      <div className="mx-auto max-w-4xl px-4 py-5 md:px-7 md:py-8">
        <div className="mb-6 max-w-xl">
          <h1 className="text-xl font-semibold">Find jobs for free. Let JobCopilot do the work with Premium.</h1>
          <p className="mt-1 text-ink-2">Premium writes your applications, applies with your approval, watches your inbox and gets you ready for interviews.</p>
        </div>

        {plan.isPending ? (
          <Spinner />
        ) : !p || !price ? (
          <Alert>Couldn't load plans: {plan.error?.message ?? "no data"}</Alert>
        ) : (
          <div className="grid gap-4 md:grid-cols-2">
            <Card className="flex flex-col gap-4 p-6">
              <div>
                <h2 className="text-base font-semibold">Free</h2>
                <p className="mt-1 text-2xl font-semibold">{formatPrice({ ...price, amount: 0 })}</p>
                <p className="text-ink-3">forever</p>
              </div>
              <FeatureList premium={false} />
              {!premium && <p className="mt-auto font-medium text-ink-2">Your current plan</p>}
            </Card>

            <Card className="flex flex-col gap-4 border-accent p-6 ring-1 ring-accent">
              <div>
                <h2 className="flex items-center gap-2 text-base font-semibold">
                  <Sparkles className="size-4 text-accent" aria-hidden />
                  Premium
                </h2>
                <p className="mt-1 text-2xl font-semibold">
                  {formatPrice(price)}
                  <span className="text-base font-normal text-ink-2"> / month</span>
                </p>
                <button
                  type="button"
                  className="text-xs text-ink-3 hover:text-accent hover:underline"
                  onClick={() => setRegion(region === "IN" ? "INTL" : "IN")}
                >
                  {region === "IN" ? `Outside India? ${formatPrice(p.prices.INTL)} / month` : `In India? ${formatPrice(p.prices.IN)} / month`}
                </button>
              </div>
              <FeatureList premium />
              <div className="mt-auto flex flex-col gap-2">
                {premium ? (
                  <>
                    <Badge tone="ok">You're on Premium</Badge>
                    <Link to="/settings" className="text-sm font-medium text-accent hover:underline">
                      Manage your plan in Settings
                    </Link>
                  </>
                ) : !p.payments_enabled ? (
                  <Alert tone="warn">Premium is coming soon. Payments aren't open yet.</Alert>
                ) : (
                  <>
                    {error && <Alert>{error.message}</Alert>}
                    <Button variant="primary" loading={upgrade.isPending} onClick={() => upgrade.mutate(region)}>
                      Upgrade to Premium
                    </Button>
                    <p className="text-xs text-ink-3">
                      Secure payment by Razorpay. Renews monthly; cancel any time in Settings. See the{" "}
                      <Link to="/terms" className="underline hover:text-ink">
                        Terms
                      </Link>{" "}
                      for refunds.
                    </p>
                  </>
                )}
              </div>
            </Card>
          </div>
        )}

        <p className="mt-6 text-ink-3">
          Questions? <Link to="/settings" className="text-accent hover:underline">Your plan and billing live in Settings.</Link>
        </p>
      </div>
    </>
  );
}

function FeatureList({ premium }: { premium: boolean }) {
  return (
    <ul className="flex flex-col gap-2">
      {PLAN_FEATURES.map((f) => {
        const included = premium || f.free;
        return (
          <li key={f.label} className={cx("flex items-start gap-2", !included && "text-ink-3")}>
            {included ? (
              <Check className="mt-0.5 size-4 flex-none text-ok" aria-hidden />
            ) : (
              <Minus className="mt-0.5 size-4 flex-none" aria-hidden />
            )}
            <span>
              {f.label}
              {!included && <span className="sr-only"> (not included)</span>}
            </span>
          </li>
        );
      })}
    </ul>
  );
}
