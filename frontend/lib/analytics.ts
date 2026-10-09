const measurementId = process.env.NEXT_PUBLIC_GA_MEASUREMENT_ID;
const consentKey = "eagles-away-analytics-consent";

type AnalyticsEvent = "form_match_complete" | "form_preferences_complete" | "trip_started" | "plan_ready" | "plan_failed" | "plan_sent";
type Gtag = (...args: unknown[]) => void;

declare global {
  interface Window {
    dataLayer?: unknown[];
    gtag?: Gtag;
  }
}

let enabled = false;

export function analyticsConfigured(): boolean {
  return Boolean(measurementId);
}

export function analyticsConsent(): "accepted" | "rejected" | null {
  try {
    const choice = localStorage.getItem(consentKey);
    return choice === "accepted" || choice === "rejected" ? choice : null;
  } catch {
    return null;
  }
}

export function setAnalyticsConsent(accepted: boolean): void {
  try { localStorage.setItem(consentKey, accepted ? "accepted" : "rejected"); } catch { /* storage may be unavailable */ }
  if (!accepted) {
    enabled = false;
    if (measurementId) {
      (window as unknown as Record<string, unknown>)[`ga-disable-${measurementId}`] = true;
      window.gtag?.("consent", "update", { analytics_storage: "denied" });
    }
    for (const cookie of document.cookie.split(";")) {
      const name = cookie.trim().split("=")[0];
      if (name === "_ga" || name?.startsWith("_ga_")) {
        document.cookie = `${name}=; Max-Age=0; Path=/; SameSite=Lax`;
      }
    }
    return;
  }
  if (!measurementId || enabled) return;
  enabled = true;
  (window as unknown as Record<string, unknown>)[`ga-disable-${measurementId}`] = false;
  window.dataLayer ??= [];
  window.gtag = (...args: unknown[]) => { window.dataLayer?.push(args); };
  window.gtag("consent", "default", {
    analytics_storage: "granted", ad_storage: "denied", ad_user_data: "denied", ad_personalization: "denied",
  });
  window.gtag("js", new Date());
  window.gtag("config", measurementId, { send_page_view: false, page_location: `${window.location.origin}${window.location.pathname}`, page_referrer: window.location.origin, allow_google_signals: false, allow_ad_personalization_signals: false, cookie_domain: "none" });
  if (!document.querySelector("script[data-eagles-away-analytics]")) {
    const script = document.createElement("script");
    script.async = true;
    script.dataset.eaglesAwayAnalytics = "";
    script.src = `https://www.googletagmanager.com/gtag/js?id=${encodeURIComponent(measurementId)}`;
    document.head.append(script);
  }
}

export function trackPage(pathname: string): void {
  if (!enabled) return;
  window.gtag?.("set", { page_location: `${window.location.origin}${pathname}`, page_path: pathname, page_referrer: window.location.origin });
  window.gtag?.("event", "page_view", {
    page_location: `${window.location.origin}${pathname}`,
    page_path: pathname,
    page_title: document.title,
  });
}

export function trackAnalytics(event: AnalyticsEvent): void {
  if (enabled) window.gtag?.("event", event);
}
