import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { createBrowserRouter, Navigate, Outlet, RouterProvider, useLocation } from "react-router";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ApiError } from "./lib/api";
import { AuthProvider, useAuth } from "./lib/auth";
import { AppShell } from "./components/AppShell";
import { Spinner } from "./components/ui";
import { LoginPage } from "./pages/LoginPage";
import { HomePage } from "./pages/HomePage";
import { JobsPage } from "./pages/JobsPage";
import { ApplicationsPage } from "./pages/ApplicationsPage";
import { ComingSoonPage } from "./pages/ComingSoonPage";
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
  const { status } = useAuth();
  const location = useLocation();
  if (status === "loading") return <Spinner />;
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
    children: [
      { path: "/login", element: <LoginPage /> },
      {
        element: <RequireAuth />,
        children: [
          {
            element: <AppShell />,
            children: [
              { index: true, element: <HomePage /> },
              { path: "jobs", element: <JobsPage /> },
              { path: "applications", element: <ApplicationsPage /> },
              {
                path: "prep",
                element: <ComingSoonPage title="Prep" description="Mock interviews, your story bank and questions to ask, all in one place." />,
              },
              {
                path: "profile",
                element: <ComingSoonPage title="Profile" description="Your resume, preferences and connected job sites." />,
              },
              {
                path: "settings",
                element: <ComingSoonPage title="Settings" description="Automation, security, sessions and billing." />,
              },
              {
                path: "admin",
                element: <ComingSoonPage title="Admin" description="Organization and user management." />,
              },
              { path: "*", element: <Navigate to="/" replace /> },
            ],
          },
        ],
      },
    ],
  },
]);

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>
  </StrictMode>,
);
