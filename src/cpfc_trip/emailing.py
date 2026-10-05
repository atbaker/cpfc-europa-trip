"""Pure escaped email rendering of a frozen revision; no research dependencies."""

from html import escape

from cpfc_trip.domain import Leg, Snapshot, Stay
from cpfc_trip.planner.links import safe_url


def render(snapshot: Snapshot) -> dict[str, str]:
    title = (
        "Eagles Away · Your Palace itinerary"
        if snapshot.itinerary
        else "Eagles Away · An update on your Palace trip"
    )
    text = [title, "Supported by Temporal", ""]
    if not snapshot.itinerary:
        text.append(
            "We couldn't verify a useful itinerary within this session. No travel has been booked."
        )
    else:
        text.extend(snapshot.itinerary.caveats)
        for trip in snapshot.itinerary.trips:
            text += [
                "",
                f"Palace away at {trip.fixture.opponent}",
                f"Kickoff: {trip.fixture.kickoff_at.isoformat()} (UTC)",
                trip.summary,
            ]
            items = list(trip.journey.outbound + trip.journey.inbound) if trip.journey else []
            for leg in items:
                text.append(
                    f"{leg.origin} → {leg.destination}: {leg.departs_at.isoformat()} – "
                    f"{leg.arrives_at.isoformat()} · {leg.operator} {leg.service_number}"
                )
            priced: list[Leg | Stay] = [*items, *([trip.stay] if trip.stay else [])]
            if trip.stay:
                s = trip.stay
                text.append(
                    f"{s.property_name} · {s.room_description} · {s.check_in} to {s.check_out}"
                )
            for item in priced:
                q = item.quote
                if q:
                    text.append(
                        f"Observed {q.amount.currency} {q.amount.minor_units / 100:.2f} "
                        f"per {q.unit}, {q.scope}; checked {q.observed_at.isoformat()}. "
                        f"Taxes {q.taxes}. {' '.join(q.caveats)}"
                    )
                    if q.additional_taxes:
                        text.append(
                            f"Additional taxes: {q.additional_taxes.currency} "
                            f"{q.additional_taxes.minor_units / 100:.2f}"
                        )
                else:
                    text.append("Price unavailable — check current fare.")
                if item.offer.booking_url and safe_url(item.offer.booking_url):
                    text.append(item.offer.booking_url)
            for transfer in trip.transfers:
                text += [
                    transfer.title,
                    transfer.description,
                    transfer.source_url,
                    f"Transfer guidance reviewed {transfer.reviewed_at.isoformat()}; fares excluded.",
                ]
            text.extend(trip.gaps)
            if trip.known_total:
                text.append(
                    f"Known subtotal: {trip.known_total.currency} "
                    f"{trip.known_total.minor_units / 100:.2f}; incomplete price coverage."
                )
    text += [
        "",
        "Prices may have changed. Confirm every detail on the travel provider's site.",
        f"No match tickets, bookings, or travel to/from the {snapshot.origin_city} departure hub are included.",
    ]
    lines = []
    for line in text:
        if safe_url(line):
            lines.append(f'<p><a href="{escape(line, quote=True)}">View on travel provider</a></p>')
        else:
            lines.append(f"<p>{escape(line)}</p>")
    return dict(
        subject=title,
        text="\n".join(text),
        html=(
            '<!doctype html><html lang="en"><body style="font:16px/1.5 Arial,sans-serif;'
            'color:#152039;max-width:640px;margin:auto;padding:24px">'
            + "".join(lines)
            + "</body></html>"
        ),
    )
