"use client";

import { useEffect, useRef, useState } from "react";
import { usePathname } from "next/navigation";
import Link from "next/link";
import { analyticsConfigured, analyticsConsent, setAnalyticsConsent, trackPage } from "../lib/analytics";

export function AnalyticsConsent() {
  const pathname = usePathname();
  const [choice, setChoice] = useState<"accepted" | "rejected" | null | "loading">("loading");
  const [editing, setEditing] = useState(false);
  const lastTrackedPath = useRef<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    queueMicrotask(() => {
      if (cancelled) return;
      const saved = analyticsConsent();
      setChoice(saved);
      if (saved === "accepted") setAnalyticsConsent(true);
    });
    return () => { cancelled = true; };
  }, []);

  useEffect(() => {
    if (choice === "accepted" && lastTrackedPath.current !== pathname) {
      trackPage(pathname);
      lastTrackedPath.current = pathname;
    }
  }, [pathname, choice]);

  if (!analyticsConfigured()) return null;

  function choose(accepted: boolean) {
    setAnalyticsConsent(accepted);
    if (!accepted) lastTrackedPath.current = null;
    setChoice(accepted ? "accepted" : "rejected");
    setEditing(false);
  }

  return <>
    <button type="button" className="analytics-settings text-button" onClick={() => setEditing(true)}>Analytics choices</button>
    {(choice === null || editing) && <aside className="analytics-consent" aria-label="Analytics choice">
      <p><strong>Help us improve Eagles Away?</strong> With your permission, we’ll measure visits and whether trip planning works. We won’t send your email, trip details, or session link to Google. <Link href="/privacy/">How we use analytics</Link>.</p>
      <div className="analytics-actions"><button type="button" className="text-button" onClick={() => choose(false)}>No thanks</button><button type="button" className="text-button" onClick={() => choose(true)}>Allow analytics</button></div>
    </aside>}
  </>;
}
