import { afterEach, describe, expect, it, vi } from "vitest";
import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { PlannerForm } from "./planner-form";
import { request } from "../lib/api";
import formCatalog from "../lib/form-catalog.json";

vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn() }) }));
vi.mock("../lib/api", async importOriginal => ({
  ...(await importOriginal<typeof import("../lib/api")>()),
  request: vi.fn(async () => ({ ...(await import("../lib/form-catalog.json")).default, development_mode: false })),
}));

describe("trip brief steps", () => {
  afterEach(() => { cleanup(); vi.clearAllMocks(); vi.restoreAllMocks(); });

  it("shows all city and match choices before the catalog request completes", async () => {
    vi.mocked(request).mockImplementationOnce(() => new Promise<never>(() => {}));
    render(<PlannerForm />);
    expect(screen.getByRole("combobox", { name: /Starting from/ })).toHaveValue("London");
    expect(screen.getByRole("option", { name: "Manchester" })).toBeInTheDocument();
    expect(screen.getByRole("radio", { name: /Olympique Lyonnais/ })).toBeChecked();
    expect(screen.getByRole("radio", { name: /FC Red Bull Salzburg/ })).toBeInTheDocument();
    await act(async () => { await Promise.resolve(); });
  });

  it("keeps a match chosen while the catalog request is pending", async () => {
    let finishRequest!: () => void;
    vi.mocked(request).mockImplementationOnce(async () => {
      await new Promise<void>(resolve => { finishRequest = resolve; });
      return { ...formCatalog, development_mode: false } as never;
    });
    render(<PlannerForm />);
    fireEvent.click(screen.getByRole("radio", { name: /Beşiktaş J.K./ }));
    await act(async () => { finishRequest(); });
    expect(screen.getByRole("radio", { name: /Beşiktaş J.K./ })).toBeChecked();
  });

  it("keeps the same major-airport city list for every match", async () => {
    render(<PlannerForm />);
    const origin = screen.getByRole("combobox", { name: /Starting from/ });
    expect(screen.queryByRole("option", { name: "Bournemouth" })).not.toBeInTheDocument();
    expect(screen.getByRole("option", { name: "Bristol" })).toBeInTheDocument();
    fireEvent.change(origin, { target: { value: "Manchester" } });
    fireEvent.click(screen.getByRole("radio", { name: /Beşiktaş J.K./ }));
    expect(origin).toHaveValue("Manchester");
    expect(screen.getByRole("option", { name: "Bristol" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("radio", { name: /Jagiellonia Białystok/ }));
    expect(origin).toHaveValue("Manchester");
    await act(async () => { await Promise.resolve(); });
  });

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
    expect(JSON.parse(String(submission?.[1]?.body)).brief.fixture_ids).toEqual(["uel-2026-besiktas-away"]);
  });
});
