import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import type { Snapshot } from "../lib/api";
import { PlanExperience } from "./plan-experience";

const { state } = vi.hoisted(() => ({ state: { snapshot: null as Snapshot | null } }));

vi.mock("next/navigation", () => ({ useSearchParams: () => new URLSearchParams("session=example") }));
vi.mock("../lib/api", async importOriginal => ({
  ...(await importOriginal<typeof import("../lib/api")>()),
  request: vi.fn(async () => state.snapshot),
}));

const snapshot: Snapshot = {
  development_mode: false,
  public_session_id: "example",
  origin_city: "London",
  state_revision: 1,
  phase: "draft_ready",
  progress_message: "Your draft is ready.",
  itinerary: { revision: 1, generated_at: "2026-10-05T12:00:00Z", trips: [], caveats: [], ranking_policy_version: "1" },
  transcript_tail: [{ id: "reply", turn_id: "turn", role: "assistant", content: "Your plan is ready.", created_at: "2026-10-05T12:00:00Z" }],
  email_deadline: "2026-10-05T13:00:00Z",
  interaction_deadline: "2026-10-05T13:00:00Z",
  follow_ups_remaining: 10,
  email_status: "not_requested",
};

describe("trip conversation", () => {
  afterEach(() => { cleanup(); state.snapshot = null; });

  it("keeps the message box available while the session is open", async () => {
    state.snapshot = snapshot;
    render(<PlanExperience />);
    expect(await screen.findByRole("heading", { name: "Fine-tune your away day" })).toBeVisible();
    expect(screen.getByRole("textbox", { name: "Ask a question or change your trip" })).toBeVisible();
  });

  it("explains why the message box is gone after the session ends", async () => {
    state.snapshot = { ...snapshot, phase: "emailed", progress_message: "Your email has been prepared." };
    render(<PlanExperience />);
    expect(await screen.findByRole("heading", { name: "Your trip conversation" })).toBeVisible();
    expect(screen.queryByRole("textbox", { name: "Ask a question or change your trip" })).not.toBeInTheDocument();
    expect(screen.getByText(/Messages are closed/)).toBeVisible();
    expect(screen.getByRole("link", { name: /Start a new trip brief/ })).toHaveAttribute("href", "/");
  });

  it("shows a checked journey as an incomplete preview while hotels are pending", async () => {
    vi.stubGlobal("matchMedia", () => ({ matches: false, addEventListener: () => {}, removeEventListener: () => {} }));
    const outbound = { id: "outbound", kind: "transport", mode: "flight", origin: "Manchester", destination: "Lyon", departs_at: "2026-10-14T08:00:00Z", arrives_at: "2026-10-14T10:00:00Z", operator: "Example Air", service_number: "EA1", quote: null, offer: { evidence: { underlying_source: "Google Flights", provider: "SearchApi" } }, caveats: [] };
    const inbound = { ...outbound, id: "inbound", origin: "Lyon", destination: "Manchester", departs_at: "2026-10-16T08:00:00Z", arrives_at: "2026-10-16T10:00:00Z" };
    state.snapshot = { ...snapshot, phase: "researching", itinerary: null, preview_trip: { fixture: { city: "Lyon", opponent: "Olympique Lyonnais", kickoff_at: "2026-10-15T19:00:00Z", timezone: "Europe/Paris", venue: "Parc Olympique Lyonnais", venue_status: "confirmed" }, journey: { outbound: [outbound], inbound: [inbound] }, stay: null } as unknown as NonNullable<Snapshot["preview_trip"]> };
    render(<PlanExperience />);
    expect(await screen.findByRole("article", { name: "Journey found while planning continues" })).toBeVisible();
    expect(screen.getByText(/This is not a complete trip yet/)).toBeVisible();
    expect(screen.getByRole("heading", { name: "Palace at Olympique Lyonnais" })).toBeVisible();
    const match = screen.getByRole("heading", { name: "Olympique Lyonnais v Crystal Palace" });
    const checking = screen.getByRole("heading", { name: "Finding your stay and comparing options" });
    const returning = screen.getByRole("heading", { name: /Lyon.*Manchester/ });
    expect(match).toBeVisible();
    expect(checking).toBeVisible();
    expect(returning).toBeVisible();
    expect(match.compareDocumentPosition(checking) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(checking.compareDocumentPosition(returning) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(screen.queryByText(/Comparing routes from/)).not.toBeInTheDocument();
    expect(screen.queryByText("Take the plan with you.")).not.toBeInTheDocument();
    vi.unstubAllGlobals();
  });
});
