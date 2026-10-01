import { describe, expect, it } from "vitest";
import { newer, terminal, formatMoney, type Snapshot } from "./api";
const current = { state_revision: 3, phase: "draft_ready", active_turn_id: "pending-turn" } as Snapshot;
describe("poll reconciliation", () => {
  it("keeps pending state on unchanged, older, and duplicate snapshots", () => {
    expect(newer(current, null)).toBe(current);
    expect(newer(current, { ...current, state_revision: 2 })).toBe(current);
    expect(newer(current, { ...current })).toBe(current);
    expect(newer(current, { ...current, state_revision: 4 })?.state_revision).toBe(4);
  });
  it("stops only at terminal states", () => {
    expect(terminal(current)).toBe(false);
    expect(terminal({ ...current, phase: "finalizing" })).toBe(false);
    expect(terminal({ ...current, phase: "emailed" })).toBe(true);
  });
  it("does not invent fractional precision for rounded prices", () => {
    expect(formatMoney({ minor_units: 5800, currency: "GBP" })).toBe("£58");
    expect(formatMoney({ minor_units: 6859, currency: "GBP" })).toBe("£68.59");
  });
});
