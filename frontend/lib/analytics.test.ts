import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

describe("optional website analytics", () => {
  beforeEach(() => {
    const storage = new Map<string, string>();
    vi.stubGlobal("localStorage", {
      getItem: (key: string) => storage.get(key) ?? null,
      setItem: (key: string, value: string) => { storage.set(key, value); },
      clear: () => { storage.clear(); },
    });
  });

  afterEach(() => {
    vi.unstubAllEnvs();
    vi.resetModules();
    localStorage.clear();
    document.querySelector("script[data-eagles-away-analytics]")?.remove();
    document.cookie = "_ga=; Max-Age=0; Path=/";
    window.history.replaceState({}, "", "/");
    window.dataLayer = undefined;
    window.gtag = undefined;
    vi.unstubAllGlobals();
  });

  it("does not load Google before consent and never sends the session query", async () => {
    vi.stubEnv("NEXT_PUBLIC_GA_MEASUREMENT_ID", "G-TEST123");
    vi.resetModules();
    const analytics = await import("./analytics");
    window.history.replaceState({}, "", "/plan/?session=private-session-id");
    expect(analytics.analyticsConsent()).toBeNull();
    analytics.trackPage("/plan/");
    analytics.trackAnalytics("plan_ready");
    expect(document.querySelector("script[data-eagles-away-analytics]")).toBeNull();

    analytics.setAnalyticsConsent(true);
    analytics.trackPage("/plan/");
    analytics.trackAnalytics("plan_ready");
    expect(document.querySelector("script[data-eagles-away-analytics]")).toHaveAttribute("src", "https://www.googletagmanager.com/gtag/js?id=G-TEST123");
    expect(JSON.stringify(window.dataLayer)).toContain("plan_ready");
    expect(JSON.stringify(window.dataLayer)).not.toContain("private-session-id");
  });

  it("stops event tracking and clears analytics cookies when consent is withdrawn", async () => {
    vi.stubEnv("NEXT_PUBLIC_GA_MEASUREMENT_ID", "G-TEST123");
    vi.resetModules();
    const analytics = await import("./analytics");
    analytics.setAnalyticsConsent(true);
    document.cookie = "_ga=test; Path=/";
    const before = window.dataLayer?.length;

    analytics.setAnalyticsConsent(false);
    analytics.trackAnalytics("trip_started");
    expect(window.dataLayer?.length).toBe((before ?? 0) + 1);
    expect(document.cookie).not.toContain("_ga=");
    expect(analytics.analyticsConsent()).toBe("rejected");
  });
});
