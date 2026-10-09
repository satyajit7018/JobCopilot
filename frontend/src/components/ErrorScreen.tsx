import { useEffect } from "react";
import { isRouteErrorResponse, Link, useRouteError } from "react-router";
import { RefreshCw, TriangleAlert } from "lucide-react";
import { reportError } from "../lib/errorReporting";
import { Button, buttonClass } from "./ui";

/** Replaces the router's raw error screen; the error is reported automatically. */
export function ErrorScreen() {
  const error = useRouteError();
  const notFound = isRouteErrorResponse(error) && error.status === 404;
  useEffect(() => {
    if (!notFound) reportError(error);
  }, [error, notFound]);

  return (
    <div className="flex min-h-dvh items-center justify-center bg-canvas px-4">
      <div className="max-w-md text-center">
        <span className="mx-auto mb-4 grid size-12 place-items-center rounded-full bg-warn-soft text-warn">
          <TriangleAlert className="size-6" aria-hidden />
        </span>
        <h1 className="text-xl font-semibold">{notFound ? "This page doesn't exist" : "Something went wrong"}</h1>
        <p className="mt-2 text-ink-2">
          {notFound
            ? "The link may be old or mistyped."
            : "We've been told about it. Reloading usually fixes it; your data is safe."}
        </p>
        <div className="mt-6 flex justify-center gap-2">
          {!notFound && (
            <Button variant="primary" onClick={() => window.location.reload()}>
              <RefreshCw className="size-4" aria-hidden />
              Reload
            </Button>
          )}
          <Link to="/" className={buttonClass(notFound ? "primary" : "secondary")} reloadDocument>
            Go to Home
          </Link>
        </div>
      </div>
    </div>
  );
}
