import { useEffect, useRef, useState } from "react";
import { Alert } from "./ui";

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

/** Google's own "Continue with Google" button; calls onCredential with a fresh ID token. */
export function GoogleButton({
  clientId,
  onCredential,
  text = "continue_with",
  unavailable = "Google sign-in is unavailable right now. Try again in a moment.",
}: {
  clientId: string;
  onCredential: (idToken: string) => void;
  text?: "continue_with" | "signin_with";
  unavailable?: string;
}) {
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
        gid.renderButton(ref.current, { theme: "outline", size: "large", text, width: ref.current.offsetWidth || 320 });
      })
      .catch(() => !cancelled && setFailed(true));
    return () => {
      cancelled = true;
    };
  }, [clientId, text]);

  if (failed) return <Alert tone="warn">{unavailable}</Alert>;
  return <div ref={ref} className="flex min-h-11 justify-center" />;
}
