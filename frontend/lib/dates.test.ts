import { expect, test } from "vitest";
import { londonDayBoundary } from "./api";

test("date windows retain London time across DST changes", () => {
  expect(londonDayBoundary("2026-10-14")).toBe("2026-10-14T00:00:00+01:00");
  expect(londonDayBoundary("2026-10-25")).toBe("2026-10-25T00:00:00+01:00");
  expect(londonDayBoundary("2026-10-25", true)).toBe("2026-10-25T23:59:00+00:00");
});
