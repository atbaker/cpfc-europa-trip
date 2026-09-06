import { render, screen } from "@testing-library/react";

import { ItineraryView } from "./itinerary-view";
import type { Itinerary } from "@/lib/types";

const itinerary: Itinerary = {
  id: "itinerary-test",
  revision: 1,
  title: "Your Crystal Palace away days",
  summary: "A best-value illustrative plan.",
  generated_at: "2026-09-04T00:00:00Z",
  assumptions: ["Match tickets are not included."],
  trips: [
    {
      id: "trip-test",
      title: "Lyon away",
      fixture_ids: ["uel-2026-lyon-away"],
      estimated_total: { minor_units: 45000, currency: "GBP" },
      per_person_total: { minor_units: 45000, currency: "GBP" },
      tradeoffs: ["Balances cost and journey time."],
      booking_order: ["Confirm the venue", "Book transport"],
      alternatives: [
        { id: "alt-test", label: "Worth comparing", summary: "Try rail via Paris." },
      ],
      items: [
        {
          kind: "transport",
          id: "leg-test",
          mode: "rail",
          origin_name: "London",
          destination_name: "Lyon",
          origin_timezone: "Europe/London",
          destination_timezone: "Europe/Paris",
          departs_at: "2026-10-14T08:15:00+01:00",
          arrives_at: "2026-10-14T15:00:00+02:00",
          operator: "Eurostar + TGV (illustrative)",
          price: { minor_units: 24000, currency: "GBP" },
          price_confidence: "estimated",
          checked_at: "2026-09-04T00:00:00Z",
          booking: { provider: "demo", url: "https://example.com", label: "Search fares" },
          self_transfer: false,
          caveats: ["Illustrative route."],
        },
        {
          kind: "match",
          id: "match-test",
          fixture: {
            id: "uel-2026-lyon-away",
            home_team_name: "Lyon",
            away_team_name: "Crystal Palace",
            kickoff_at: "2026-10-15T16:45:00Z",
            venue: {
              name: "Lyon venue (to be confirmed)",
              status: "provisional",
              city: { name: "Lyon", timezone: "Europe/Paris" },
            },
          },
          recommended_arrival_at: "2026-10-15T15:15:00Z",
          ticket_included: false,
        },
      ],
    },
  ],
};

describe("ItineraryView", () => {
  it("renders complete structured cards and caveats", () => {
    render(<ItineraryView itinerary={itinerary} />);
    expect(screen.getByRole("heading", { name: "Lyon away" })).toBeInTheDocument();
    expect(screen.getByText("Eurostar + TGV (illustrative)")).toBeInTheDocument();
    expect(screen.getByText(/Match ticket not included/)).toBeInTheDocument();
    expect(screen.getByText("~£240")).toBeInTheDocument();
  });
});

