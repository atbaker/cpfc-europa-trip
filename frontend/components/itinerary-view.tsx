import type {
  FixtureTrip,
  Itinerary,
  ItineraryItem,
  MatchItem,
  Money,
  StayItem,
  TransportItem,
} from "@/lib/types";

export function ItineraryView({ itinerary }: { itinerary: Itinerary }) {
  return (
    <section className="itinerary" aria-labelledby="itinerary-title">
      <div className="itinerary-heading">
        <div>
          <p className="eyebrow">Draft itinerary · revision {itinerary.revision}</p>
          <h1 id="itinerary-title">{itinerary.title}</h1>
          <p>{itinerary.summary}</p>
        </div>
        <span className="draft-badge">Draft</span>
      </div>
      {itinerary.trips.map((trip) => (
        <TripView trip={trip} key={trip.id} />
      ))}
      <aside className="assumptions">
        <strong>Before you book</strong>
        <ul>
          {itinerary.assumptions.map((assumption) => (
            <li key={assumption}>{assumption}</li>
          ))}
        </ul>
      </aside>
    </section>
  );
}

function TripView({ trip }: { trip: FixtureTrip }) {
  return (
    <article className="trip-block">
      <header className="trip-header">
        <div>
          <span className="trip-kicker">Independent round trip</span>
          <h2>{trip.title}</h2>
        </div>
        {trip.estimated_total && (
          <div className="trip-total">
            <strong>{formatMoney(trip.estimated_total)}</strong>
            <span>estimated total</span>
          </div>
        )}
      </header>
      <div className="timeline">
        {trip.items.map((item) => (
          <ItemView item={item} key={item.id} />
        ))}
      </div>
      <div className="trip-notes">
        <div>
          <strong>Why this route</strong>
          {trip.tradeoffs.map((tradeoff) => (
            <p key={tradeoff}>{tradeoff}</p>
          ))}
        </div>
        {trip.alternatives.map((alternative) => (
          <div key={alternative.id}>
            <strong>{alternative.label}</strong>
            <p>{alternative.summary}</p>
          </div>
        ))}
      </div>
      {trip.booking_order.length > 0 && (
        <div className="booking-order">
          <strong>Suggested booking order</strong>
          <ol>
            {trip.booking_order.map((step) => (
              <li key={step}>{step}</li>
            ))}
          </ol>
        </div>
      )}
    </article>
  );
}

function ItemView({ item }: { item: ItineraryItem }) {
  if (item.kind === "transport") return <TransportCard item={item} />;
  if (item.kind === "stay") return <StayCard item={item} />;
  return <MatchCard item={item} />;
}

function TransportCard({ item }: { item: TransportItem }) {
  return (
    <div className="timeline-row">
      <div className={`timeline-icon ${item.mode}`} aria-hidden="true">
        {transportIcon(item.mode)}
      </div>
      <section className="detail-card">
        <div className="card-topline">
          <span>{item.mode.replace("_", " ")}</span>
          <Price money={item.price} confidence={item.price_confidence} />
        </div>
        <h3>
          {item.origin_name} <span aria-hidden="true">→</span> {item.destination_name}
        </h3>
        <div className="journey-times">
          <p>
            <strong>{formatTime(item.departs_at, item.origin_timezone)}</strong>
            <span>{formatDate(item.departs_at, item.origin_timezone)}</span>
          </p>
          <span className="journey-line" aria-hidden="true" />
          <p>
            <strong>{formatTime(item.arrives_at, item.destination_timezone)}</strong>
            <span>{formatDate(item.arrives_at, item.destination_timezone)}</span>
          </p>
        </div>
        {item.operator && <p className="muted">{item.operator}</p>}
        {item.self_transfer && <span className="risk-badge">Self-transfer: allow extra time</span>}
        {item.caveats.map((caveat) => (
          <p className="caveat" key={caveat}>
            {caveat}
          </p>
        ))}
        <CardFooter booking={item.booking} checkedAt={item.checked_at} confidence={item.price_confidence} />
      </section>
    </div>
  );
}

function StayCard({ item }: { item: StayItem }) {
  return (
    <div className="timeline-row">
      <div className="timeline-icon stay" aria-hidden="true">
        ▰
      </div>
      <section className="detail-card">
        <div className="card-topline">
          <span>Stay · {nightsBetween(item.check_in, item.check_out)} nights</span>
          <Price money={item.price} confidence={item.price_confidence} />
        </div>
        <h3>{item.property_name}</h3>
        <p className="muted">
          {formatDateOnly(item.check_in)} → {formatDateOnly(item.check_out)} · {item.place_name}
        </p>
        {item.room_description && <p>{item.room_description}</p>}
        <p className="transfer-note">{item.venue_transfer_note}</p>
        {item.caveats.map((caveat) => (
          <p className="caveat" key={caveat}>
            {caveat}
          </p>
        ))}
        <CardFooter booking={item.booking} checkedAt={item.checked_at} confidence={item.price_confidence} />
      </section>
    </div>
  );
}

function MatchCard({ item }: { item: MatchItem }) {
  const fixture = item.fixture;
  return (
    <div className="timeline-row match-row">
      <div className="timeline-icon match" aria-hidden="true">
        ⚽
      </div>
      <section className="detail-card match-card">
        <div className="card-topline">
          <span>Europa League</span>
          <span className="venue-status">{fixture.venue.status} venue</span>
        </div>
        <h3>{fixture.home_team_name} v Crystal Palace</h3>
        <p className="kickoff">
          {formatDate(fixture.kickoff_at, fixture.venue.city.timezone)} ·{" "}
          {formatTime(fixture.kickoff_at, fixture.venue.city.timezone)} kickoff
        </p>
        <p>{fixture.venue.name}</p>
        <p className="muted">
          Aim to arrive by {formatTime(item.recommended_arrival_at, fixture.venue.city.timezone)}.
          Match ticket not included.
        </p>
      </section>
    </div>
  );
}

function CardFooter({
  booking,
  checkedAt,
  confidence,
}: {
  booking: { url: string; label: string } | null;
  checkedAt: string | null;
  confidence: string;
}) {
  return (
    <footer className="card-footer">
      <span>
        {confidence === "estimated"
          ? "Demo estimate"
          : checkedAt
            ? `Checked ${formatCheckedAt(checkedAt)}`
            : "Price unavailable"}
      </span>
      {booking && (
        <a href={booking.url} target="_blank" rel="noreferrer">
          {booking.label} <span aria-hidden="true">↗</span>
        </a>
      )}
    </footer>
  );
}

function Price({ money, confidence }: { money: Money | null; confidence: string }) {
  if (!money) return <strong className="price unavailable">Check fare</strong>;
  return (
    <strong className="price">
      {confidence === "estimated" && "~"}
      {formatMoney(money)}
    </strong>
  );
}

function formatMoney(money: Money) {
  return new Intl.NumberFormat("en-GB", {
    style: "currency",
    currency: money.currency,
    maximumFractionDigits: 0,
  }).format(money.minor_units / 100);
}

function formatDate(value: string, timeZone: string) {
  return new Intl.DateTimeFormat("en-GB", {
    weekday: "short",
    day: "numeric",
    month: "short",
    timeZone,
  }).format(new Date(value));
}

function formatTime(value: string, timeZone: string) {
  return new Intl.DateTimeFormat("en-GB", {
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
    timeZone,
    timeZoneName: "short",
  }).format(new Date(value));
}

function formatCheckedAt(value: string) {
  return new Intl.DateTimeFormat("en-GB", {
    day: "numeric",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(value));
}

function formatDateOnly(value: string) {
  const [year, month, day] = value.split("-").map(Number);
  return new Intl.DateTimeFormat("en-GB", { day: "numeric", month: "short" }).format(
    new Date(Date.UTC(year, month - 1, day)),
  );
}

function nightsBetween(checkIn: string, checkOut: string) {
  return Math.round((Date.parse(checkOut) - Date.parse(checkIn)) / 86_400_000);
}

function transportIcon(mode: string) {
  if (mode === "flight") return "✈";
  if (mode === "rail") return "▤";
  if (mode === "coach") return "▣";
  return "→";
}

