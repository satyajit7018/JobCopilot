import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { createBrowserRouter, Navigate, Outlet, RouterProvider, useLocation } from "react-router";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ApiError } from "./lib/api";
import { loadPage, setReloadTarget } from "./lib/chunks";
import { installGlobalErrorReporting } from "./lib/errorReporting";
import { ErrorScreen } from "./components/ErrorScreen";
import { AuthProvider, useAuth } from "./lib/auth";
import { AppShell } from "./components/AppShell";
import { Alert, Button, Card, Spinner } from "./components/ui";
import { LoginPage } from "./pages/LoginPage";
import { HomePage } from "./pages/HomePage";
import { JobsPage } from "./pages/JobsPage";
import { JobReviewPage } from "./pages/JobReviewPage";
import { ApplicationDetailPage } from "./pages/ApplicationDetailPage";
import { ApplicationsPage } from "./pages/ApplicationsPage";
import { ProfilePage } from "./pages/ProfilePage";
import { SetupPage } from "./pages/SetupPage";
import "./index.css";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      // Never retry auth/permission/not-found failures; retry transient ones once.
      retry: (count, err) => !(err instanceof ApiError && err.status < 500) && count < 1,
    },
  },
});

function RequireAuth() {
  const { status, retry, logout } = useAuth();
  const location = useLocation();
  if (status === "loading") return <Spinner />;
  if (status === "unreachable")
    return (
      <div className="grid min-h-dvh place-items-center bg-canvas px-4">
        <Card className="w-full max-w-sm p-6 text-center">
          <h1 className="text-lg font-semibold">Can't reach JobCopilot</h1>
          <p className="mt-1 mb-4 text-ink-2">Check your connection. You're still signed in.</p>
          <Alert tone="warn">The server didn't respond.</Alert>
          <div className="mt-5 flex justify-center gap-2">
            <Button variant="ghost" onClick={() => void logout()}>
              Sign out
            </Button>
            <Button variant="primary" onClick={retry}>
              Try again
            </Button>
          </div>
        </Card>
      </div>
    );
  if (status === "anonymous") return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  return <Outlet />;
}

function Root() {
  return (
    <AuthProvider>
      <Outlet />
    </AuthProvider>
  );
}

const router = createBrowserRouter([
  {
    element: <Root />,
    errorElement: <ErrorScreen />,
    children: [
      { path: "/login", element: <LoginPage /> },
      // Public: readable without signing in (Google and Razorpay link to them).
      { path: "/privacy", lazy: async () => ({ Component: (await loadPage(() => import("./pages/LegalPages"))).PrivacyPage }) },
      { path: "/terms", lazy: async () => ({ Component: (await loadPage(() => import("./pages/LegalPages"))).TermsPage }) },
      { path: "/help", lazy: async () => ({ Component: (await loadPage(() => import("./pages/LegalPages"))).HelpPage }) },
      {
        element: <RequireAuth />,
        children: [
          { path: "setup", element: <SetupPage /> },
          {
            element: <AppShell />,
            children: [
              { index: true, element: <HomePage /> },
              { path: "jobs", element: <JobsPage /> },
              { path: "jobs/:jobId", element: <JobReviewPage /> },
              { path: "applications", element: <ApplicationsPage /> },
              { path: "applications/:jobId", element: <ApplicationDetailPage /> },
              // Less-visited pages load on demand to keep the first download small.
              { path: "prep", lazy: async () => ({ Component: (await loadPage(() => import("./pages/PrepPage"))).PrepPage }) },
              { path: "profile", element: <ProfilePage /> },
              { path: "plans", lazy: async () => ({ Component: (await loadPage(() => import("./pages/PlansPage"))).PlansPage }) },
              { path: "settings", lazy: async () => ({ Component: (await loadPage(() => import("./pages/SettingsPage"))).SettingsPage }) },
              { path: "admin", lazy: async () => ({ Component: (await loadPage(() => import("./pages/AdminPage"))).AdminPage }) },
              { path: "*", element: <Navigate to="/" replace /> },
            ],
          },
        ],
      },
    ],
  },
]);

// The legacy UI registered a caching service worker; this app doesn't use one.
// public/sw.js also retires it, but unregistering here takes effect immediately.
if ("serviceWorker" in navigator) {
  void navigator.serviceWorker.getRegistrations().then((regs) => regs.forEach((r) => void r.unregister()));
}

installGlobalErrorReporting();

setReloadTarget(() => {
  const next = router.state.navigation.location;
  return next ? `${next.pathname}${next.search}${next.hash}` : null;
});

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>
  </StrictMode>,
);
