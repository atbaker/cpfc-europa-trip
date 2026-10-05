import { afterEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { PlannerForm } from "./planner-form";

vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn() }) }));
vi.mock("../lib/api", async importOriginal => ({
  ...(await importOriginal<typeof import("../lib/api")>()),
  request: vi.fn(async () => ({ fixtures: [{ id: "lyon", opponent: "Lyon", city: "Lyon", kickoff_at: "2026-10-15T17:45:00Z" }], development_mode: false })),
}));

describe("trip brief steps", () => {
  afterEach(() => { vi.restoreAllMocks(); });

  it("keeps existing trip choices when moving forward and back", async () => {
    render(<PlannerForm />);
    await screen.findByRole("checkbox", { name: /Lyon/ });
    fireEvent.click(screen.getByRole("button", { name: /Continue to travel preferences/ }));
    expect(screen.getByRole("heading", { name: "How do you like to travel?" })).toBeVisible();
    fireEvent.change(screen.getByRole("spinbutton", { name: "Adults" }), { target: { value: "2" } });
    fireEvent.click(screen.getByRole("button", { name: /Continue to your details/ }));
    expect(screen.getByRole("heading", { name: "Where should we send your plan?" })).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: /Back/ }));
    await waitFor(() => expect(screen.getByRole("spinbutton", { name: "Adults" })).toHaveValue(2));
  });
});
