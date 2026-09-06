export type BudgetTier = "budget" | "value" | "comfort";
export type SessionPhase =
  | "created"
  | "researching"
  | "draft_ready"
  | "revising"
  | "finalizing"
  | "emailed"
  | "failed"
  | "email_failed";

export type Money = { minor_units: number; currency: "GBP" };
export type BookingReference = { provider: string; url: string; label: string };

export type Fixture = {
  id: string;
  home_team_name: string;
  away_team_name: string;
  kickoff_at: string;
  venue: {
    name: string;
    status: "provisional" | "confirmed";
    city: { name: string; timezone: string };
  };
};

export type TransportItem = {
  kind: "transport";
  id: string;
  mode: string;
  origin_name: string;
  destination_name: string;
  origin_timezone: string;
  destination_timezone: string;
  departs_at: string;
  arrives_at: string;
  operator: string | null;
  price: Money | null;
  price_confidence: string;
  checked_at: string | null;
  booking: BookingReference | null;
  self_transfer: boolean;
  caveats: string[];
};

export type StayItem = {
  kind: "stay";
  id: string;
  property_name: string;
  place_name: string;
  check_in: string;
  check_out: string;
  room_description: string | null;
  price: Money | null;
  price_confidence: string;
  checked_at: string | null;
  booking: BookingReference | null;
  venue_transfer_note: string;
  caveats: string[];
};

export type MatchItem = {
  kind: "match";
  id: string;
  fixture: Fixture;
  recommended_arrival_at: string;
  ticket_included: false;
};

export type ItineraryItem = TransportItem | StayItem | MatchItem;
export type FixtureTrip = {
  id: string;
  title: string;
  fixture_ids: string[];
  items: ItineraryItem[];
  alternatives: { id: string; label: string; summary: string }[];
  estimated_total: Money | null;
  per_person_total: Money | null;
  tradeoffs: string[];
  booking_order: string[];
};
export type Itinerary = {
  id: string;
  revision: number;
  title: string;
  summary: string;
  trips: FixtureTrip[];
  assumptions: string[];
  generated_at: string;
};
export type TranscriptMessage = {
  id: string;
  role: "user" | "assistant";
  body: string;
  created_at: string;
};
export type SessionSnapshot = {
  public_id: string;
  phase: SessionPhase;
  progress: string;
  state_revision: number;
  itinerary: Itinerary | null;
  messages: TranscriptMessage[];
  email_status: "not_sent" | "sending" | "sent" | "failed";
  finalization_reason: "manual" | "inactivity" | null;
};
export type StreamEvent = {
  type: "status" | "text_delta" | "turn_committed" | "retry" | "session_closed";
  message?: string | null;
  state_revision?: number | null;
  turn_id?: string | null;
  attempt?: number | null;
  text?: string | null;
  itinerary_revision?: number | null;
};
