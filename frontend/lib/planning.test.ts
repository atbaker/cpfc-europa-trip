import { describe, expect, it } from "vitest";
import { stageFor, tickerLines } from "./planning";
import type { Snapshot } from "./api";

const snap = (over: Partial<Snapshot>): Snapshot =>
  ({ phase: "researching", progress_message: "Checking your travel preferences…", itinerary: null, ...over } as unknown as Snapshot);

describe("stageFor", () => {
  it("starts at preferences before any search", () => {
    expect(stageFor(snap({}))).toBe("preferences");
    expect(stageFor(null)).toBe("preferences");
  });
  it("moves to searching once the workflow is comparing", () => {
    expect(stageFor(snap({ progress_message: "Comparing transport and accommodation…" }))).toBe("searching");
    expect(stageFor(snap({ progress_message: "A journey was found. Checking stays…", preview_trip: {} as Snapshot["preview_trip"] }))).toBe("searching");
  });
  it("is done when an itinerary exists or the phase is draft_ready", () => {
    expect(stageFor(snap({ itinerary: {} as Snapshot["itinerary"] }))).toBe("done");
    expect(stageFor(snap({ phase: "draft_ready" }))).toBe("done");
  });
  it("is failed only when terminal without an itinerary", () => {
    expect(stageFor(snap({ phase: "failed" }))).toBe("failed");
    expect(stageFor(snap({ phase: "emailed", itinerary: {} as Snapshot["itinerary"] }))).toBe("done");
  });
  it("ignores a prior itinerary for in-flight revisions", () => {
    const revising = snap({ itinerary: {} as Snapshot["itinerary"], phase: "revising", progress_message: "Comparing transport and accommodation…" });
    expect(stageFor(revising)).toBe("done");
    expect(stageFor(revising, { ignoreItinerary: true })).toBe("searching");
  });
});

describe("tickerLines", () => {
  it("uses brief-specific lines before travel research starts", () => {
    expect(tickerLines("preferences")).toContain("Checking your travel preferences…");
    expect(tickerLines("preferences")).not.toContain("Comparing routes from London…");
  });
  it("injects the city when known", () => {
    expect(tickerLines("searching", "Lyon")).toContain("Comparing places to stay in Lyon…");
    expect(tickerLines("searching", "Lyon", "Manchester")).toContain("Comparing routes from Manchester…");
  });
  it("stays generic without a city", () => {
    expect(tickerLines("searching")).toContain("Comparing places to stay…");
  });
});
