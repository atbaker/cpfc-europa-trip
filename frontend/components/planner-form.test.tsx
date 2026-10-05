import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { PlannerForm } from "./planner-form";
import { request } from "../lib/api";

vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn() }) }));
vi.mock("../lib/api", async importOriginal => ({
  ...(await importOriginal<typeof import("../lib/api")>()),
  request: vi.fn(async () => ({ fixtures: [
    { id: "lyon", opponent: "Olympique Lyonnais", city: "Lyon", venue: "Parc Olympique Lyonnais", kickoff_at: "2026-10-15T16:45:00Z" },
    { id: "besiktas", opponent: "Beşiktaş J.K.", city: "Istanbul", venue: "Tüpraş Stadium", kickoff_at: "2026-10-22T19:00:00Z" },
    { id: "jagiellonia", opponent: "Jagiellonia Białystok", city: "Białystok", venue: "Białystok City Stadium", kickoff_at: "2026-12-10T17:45:00Z" },
    { id: "salzburg", opponent: "FC Red Bull Salzburg", city: "Salzburg", venue: "Red Bull Arena", kickoff_at: "2027-01-28T20:00:00Z" },
  ], origin_cities: ["London", "Manchester", "Belfast"], rail_cities: ["London", "Manchester"], development_mode: false })),
}));

describe("trip brief steps", () => {
  afterEach(() => { cleanup(); vi.clearAllMocks(); vi.restoreAllMocks(); });

  it("keeps existing trip choices when moving forward and back", async () => {
    render(<PlannerForm />);
    await screen.findByRole("radio", { name: /Olympique Lyonnais/ });
    fireEvent.click(screen.getByRole("button", { name: /Continue to travel preferences/ }));
    expect(screen.getByRole("heading", { name: "How do you like to travel?" })).toBeVisible();
    fireEvent.change(screen.getByRole("spinbutton", { name: "Adults" }), { target: { value: "2" } });
    fireEvent.click(screen.getByRole("button", { name: /Continue to your details/ }));
    expect(screen.getByRole("heading", { name: "Where should we send your plan?" })).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: /Back/ }));
    await waitFor(() => expect(screen.getByRole("spinbutton", { name: "Adults" })).toHaveValue(2));
  });

  it("defaults to London and offers trains from a selected UK city", async () => {
    render(<PlannerForm />);
    await screen.findByRole("radio", { name: /Olympique Lyonnais/ });
    const origin = screen.getByRole("combobox", { name: /Starting from/ });
    expect(origin).toHaveValue("London");
    fireEvent.change(origin, { target: { value: "Manchester" } });
    fireEvent.click(screen.getByRole("button", { name: /Continue to travel preferences/ }));
    expect(screen.getByRole("heading", { name: "How do you like to travel?" })).toBeVisible();
    expect(screen.getByRole("combobox", { name: "Travel by" })).toHaveValue("");
    expect(screen.getByRole("combobox", { name: "Travel by" })).toHaveTextContent("Trains");
  });

  it("submits the selected city and rail mode in the brief", async () => {
    render(<PlannerForm />);
    await screen.findByRole("radio", { name: /Olympique Lyonnais/ });
    fireEvent.change(screen.getByRole("combobox", { name: "Starting from" }), { target: { value: "Manchester" } });
    fireEvent.click(screen.getByRole("button", { name: /Continue to travel preferences/ }));
    fireEvent.change(screen.getByRole("combobox", { name: "Travel by" }), { target: { value: "rail" } });
    fireEvent.click(screen.getByRole("button", { name: /Continue to your details/ }));
    fireEvent.change(screen.getByRole("textbox", { name: "Email address" }), { target: { value: "supporter@example.com" } });
    fireEvent.click(screen.getByRole("button", { name: /Plan my away day/ }));
    await waitFor(() => expect(vi.mocked(request).mock.calls.some(([path]) => path === "/api/sessions")).toBe(true));
    const submission = vi.mocked(request).mock.calls.find(([path]) => path === "/api/sessions");
    const body = JSON.parse(String(submission?.[1]?.body));
    expect(body.brief).toMatchObject({ origin_city: "Manchester", transport_mode: "rail" });
  });

  it("offers one match at a time and submits only the current choice", async () => {
    render(<PlannerForm />);
    const lyon = await screen.findByRole("radio", { name: /Olympique Lyonnais/ });
    const besiktas = screen.getByRole("radio", { name: /Beşiktaş J.K./ });
    expect(lyon).toBeChecked();
    fireEvent.click(besiktas);
    expect(besiktas).toBeChecked();
    expect(lyon).not.toBeChecked();
    expect(screen.getAllByRole("radio", { name: /Olympique Lyonnais|Beşiktaş J.K.|Jagiellonia Białystok|FC Red Bull Salzburg/ })).toHaveLength(4);
    fireEvent.click(screen.getByRole("button", { name: /Continue to travel preferences/ }));
    expect(screen.getByRole("combobox", { name: "Travel by" })).not.toHaveTextContent("Trains");
    fireEvent.click(screen.getByRole("button", { name: /Continue to your details/ }));
    fireEvent.change(screen.getByRole("textbox", { name: "Email address" }), { target: { value: "supporter@example.com" } });
    fireEvent.click(screen.getByRole("button", { name: /Plan my away day/ }));
    await waitFor(() => expect(vi.mocked(request).mock.calls.some(([path]) => path === "/api/sessions")).toBe(true));
    const submission = vi.mocked(request).mock.calls.find(([path]) => path === "/api/sessions");
    expect(JSON.parse(String(submission?.[1]?.body)).brief.fixture_ids).toEqual(["besiktas"]);
  });
});
