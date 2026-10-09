// Plans: Free and Premium (Razorpay subscriptions, Rs 199/month in India, $5/month elsewhere).
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "./api";
import { useAuth } from "./auth";

/** Roles that have Premium. ELITE is a legacy paid tier; admins always have it. */
const PREMIUM_ROLES = new Set(["PRO", "ELITE", "ADMIN"]);

export function useIsPremium(): boolean {
  const { user } = useAuth();
  return !!user && PREMIUM_ROLES.has(user.role);
}

export type Region = "IN" | "INTL";

/** India pays in rupees, everyone else in dollars. The time zone is a good enough signal for pricing. */
export function detectRegion(timeZone = Intl.DateTimeFormat().resolvedOptions().timeZone): Region {
  return timeZone === "Asia/Kolkata" || timeZone === "Asia/Calcutta" ? "IN" : "INTL";
}

export interface Price {
  currency: "INR" | "USD";
  amount: number;
}

export function formatPrice(p: Price): string {
  return p.currency === "INR" ? `₹${p.amount}` : `$${p.amount}`;
}

export interface Subscription {
  subscription_id: string;
  /** created, authenticated, active, pending, cancelling, halted, cancelled, completed, expired */
  status: string;
  current_end: string | null;
}

export interface BillingPlan {
  premium: boolean;
  subscription: Subscription | null;
  payments_enabled: boolean;
  prices: Record<Region, Price>;
}

export function useBillingPlan() {
  return useQuery({ queryKey: ["billing-plan"], queryFn: () => api<BillingPlan>("/billing/plan") });
}

/** Statuses that keep Premium on (mirrors the backend). */
export function subscriptionIsLive(s: Subscription | null | undefined): boolean {
  return !!s && ["authenticated", "active", "pending", "cancelling"].includes(s.status);
}

// --- Razorpay Checkout -------------------------------------------------------------

interface RazorpayResponse {
  razorpay_payment_id: string;
  razorpay_subscription_id: string;
  razorpay_signature: string;
}

interface RazorpayCheckout {
  open(): void;
  on(event: "payment.failed", cb: (r: { error?: { description?: string } }) => void): void;
}

declare global {
  interface Window {
    Razorpay?: new (options: Record<string, unknown>) => RazorpayCheckout;
  }
}

let checkoutLoader: Promise<void> | null = null;
function loadCheckout(): Promise<void> {
  checkoutLoader ??= new Promise((resolve, reject) => {
    const s = document.createElement("script");
    s.src = "https://checkout.razorpay.com/v1/checkout.js";
    s.async = true;
    s.onload = () => resolve();
    s.onerror = () => {
      checkoutLoader = null;
      reject(new Error("The payment window couldn't load. Check your connection and try again."));
    };
    document.head.appendChild(s);
  });
  return checkoutLoader;
}

interface SubscribeResponse {
  subscription_id: string;
  key_id: string;
  currency: string;
  amount: number;
  email: string;
  name: string;
}

/** Thrown when the person closes the payment window; not shown as an error. */
export class CheckoutDismissed extends Error {}

/**
 * Starts Premium: creates the subscription, opens Razorpay Checkout, then confirms the
 * payment with the server. Resolves once Premium is on.
 */
export function useUpgrade() {
  const qc = useQueryClient();
  const { refreshUser } = useAuth();
  return useMutation({
    mutationFn: async (region: Region) => {
      const sub = await api<SubscribeResponse>("/billing/razorpay/subscribe", { method: "POST", body: { region } });
      await loadCheckout();
      if (!window.Razorpay) throw new Error("The payment window couldn't load. Try again.");
      const paid = await new Promise<RazorpayResponse>((resolve, reject) => {
        const checkout = new window.Razorpay!({
          key: sub.key_id,
          subscription_id: sub.subscription_id,
          name: "JobCopilot",
          description: "Premium, monthly",
          prefill: { email: sub.email, name: sub.name },
          theme: { color: "#4F46E5" },
          handler: resolve,
          modal: { ondismiss: () => reject(new CheckoutDismissed("closed")) },
        });
        checkout.on("payment.failed", (r) => reject(new Error(r.error?.description ?? "The payment didn't go through.")));
        checkout.open();
      });
      await api("/billing/razorpay/verify", { method: "POST", body: paid });
    },
    onSettled: async () => {
      await refreshUser();
      await qc.invalidateQueries({ queryKey: ["billing-plan"] });
      await qc.invalidateQueries({ queryKey: ["plan"] });
    },
  });
}

export function useCancelPremium() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => api<{ premium_until: string | null }>("/billing/razorpay/cancel", { method: "POST" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["billing-plan"] }),
  });
}

/** What Free and Premium include, shown on the plans page and in locks. */
export const PLAN_FEATURES: { label: string; free: boolean }[] = [
  { label: "Job matches from top tech companies and startup job boards", free: true },
  { label: "Match scores with the reasons behind them", free: true },
  { label: "Track your applications on a board", free: true },
  { label: "Offer checks against salary ranges", free: true },
  { label: "Resume and cover letter tailored to each job", free: false },
  { label: "Automatic applying, with your approval for each one", free: false },
  { label: "Inbox tracking: recruiter replies update your board", free: false },
  { label: "Follow-up emails drafted for you", free: false },
  { label: "Interview prep: likely questions, practice and feedback", free: false },
];
