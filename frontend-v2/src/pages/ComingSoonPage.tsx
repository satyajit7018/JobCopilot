import { Construction, ExternalLink } from "lucide-react";
import { PageHeader } from "../components/AppShell";
import { Card, EmptyState, buttonClass } from "../components/ui";

// Where the legacy UI lives until every screen is rebuilt. In dev FastAPI serves it on :8000.
const CLASSIC_URL: string = import.meta.env.VITE_CLASSIC_URL ?? (import.meta.env.DEV ? "http://localhost:8000/" : "/");

export function ComingSoonPage({ title, description }: { title: string; description: string }) {
  return (
    <>
      <PageHeader title={title} />
      <div className="mx-auto max-w-2xl px-4 py-8 md:px-7">
        <Card>
          <EmptyState
            icon={<Construction className="size-5" />}
            title={`${title} is being redesigned`}
            action={
              <a href={CLASSIC_URL} className={buttonClass("secondary")}>
                Open in classic view
                <ExternalLink className="size-3.5" aria-hidden />
              </a>
            }
          >
            {description}
          </EmptyState>
        </Card>
      </div>
    </>
  );
}
