import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { PlannerForm } from "./planner-form";
import { request } from "../lib/api";

vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn() }) }));
vi.mock("../lib/api", async importOriginal => ({
  ...(await importOriginal<typeof import("../lib/api")>()),
  request: vi.fn(async () => ({ fixtures: [{ id: "lyon", opponent: "Lyon", city: "Lyon", kickoff_at: "2026-10-15T17:45:00Z" }], origin_cities: ["London", "Manchester", "Belfast"], rail_cities: ["London", "Manchester"], development_mode: false })),
}));

describe("trip brief steps", () => {
  afterEach(() => { cleanup(); vi.restoreAllMocks(); });

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

  it("defaults to London and offers trains from a selected UK city", async () => {
    render(<PlannerForm />);
    await screen.findByRole("checkbox", { name: /Lyon/ });
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
    await screen.findByRole("checkbox", { name: /Lyon/ });
    fireEvent.change(screen.getByRole("combobox", { name: "Starting from" }), { target: { value: "Manchester" } });
    fireEvent.click(screen.getByRole("button", { name: /Continue to travel preferences/ }));
    fireEvent.change(screen.getByRole("combobox", { name: "Travel by" }), { target: { value: "rail" } });
    fireEvent.click(screen.getByRole("button", { name: /Continue to your details/ }));
    fireEvent.change(screen.getByRole("textbox", { name: "Email address" }), { target: { value: "supporter@example.com" } });
    fireEvent.click(screen.getByRole("button", { name: /Plan my away days/ }));
    await waitFor(() => expect(vi.mocked(request).mock.calls.some(([path]) => path === "/api/sessions")).toBe(true));
    const submission = vi.mocked(request).mock.calls.find(([path]) => path === "/api/sessions");
    const body = JSON.parse(String(submission?.[1]?.body));
    expect(body.brief).toMatchObject({ origin_city: "Manchester", transport_mode: "rail" });
  });
});
