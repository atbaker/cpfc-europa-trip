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
});
