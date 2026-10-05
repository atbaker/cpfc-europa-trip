import type { components } from "./api-schema";
export type Snapshot = components["schemas"]["Snapshot"];
export type Fixture = components["schemas"]["Fixture"];
export type Brief = components["schemas"]["Brief"];
export type Itinerary = NonNullable<Snapshot["itinerary"]>;
export type Trip = Itinerary["trips"][number];
export type Leg = NonNullable<Trip["journey"]>["outbound"][number];
export type Stay = NonNullable<Trip["stay"]>;
const API = process.env.NEXT_PUBLIC_API_ORIGIN ?? "";

export function londonDayBoundary(day: string, end = false): string {
  const offset = new Intl.DateTimeFormat("en-GB", { timeZone: "Europe/London", timeZoneName: "shortOffset" })
    .formatToParts(new Date(`${day}T${end ? "23:59:00" : "00:00:00"}Z`)).find(p => p.type === "timeZoneName")?.value;
  return `${day}T${end ? "23:59:00" : "00:00:00"}${offset === "GMT+1" ? "+01:00" : "+00:00"}`;
}

export class ApiError extends Error { constructor(public status: number, message: string) { super(message); } }
export async function request<T>(path: string, init: RequestInit = {}): Promise<T | null> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 10000);
  try {
    const response = await fetch(`${API}${path}`, { ...init, credentials: "include", signal: controller.signal,
      headers: { "Content-Type": "application/json", ...init.headers } });
    if (!response.ok) {
      let message = "Connection interrupted. Please retry.";
      try { const body = await response.json(); if (typeof body.detail === "string") message = body.detail; } catch { /* Keep safe fallback. */ }
      throw new ApiError(response.status, message);
    }
    return response.status === 204 ? null : await response.json() as T;
  } finally { clearTimeout(timeout); }
}
export function newer(current: Snapshot | null, incoming: Snapshot | null): Snapshot | null {
  return incoming && (!current || incoming.state_revision > current.state_revision) ? incoming : current;
}
export function terminal(snapshot: Snapshot | null): boolean {
  return !!snapshot && ["emailed", "failed", "email_failed"].includes(snapshot.phase);
}
export function formatMoney(money: { minor_units: number; currency: string }): string {
  return new Intl.NumberFormat("en-GB", { style: "currency", currency: money.currency,
    maximumFractionDigits: money.minor_units % 100 ? 2 : 0, minimumFractionDigits: 0 }).format(money.minor_units / 100);
}
