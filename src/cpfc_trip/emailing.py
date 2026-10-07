"""Pure escaped email rendering of a frozen revision; no research dependencies."""

from datetime import UTC
from html import escape
from zoneinfo import ZoneInfo

from cpfc_trip.domain import Leg, Money, Quote, Snapshot, Stay, Trip
from cpfc_trip.planner.links import safe_url

INK = "#17253d"
MUTED = "#526176"
PAPER = "#f7f5f0"
RED = "#bf1934"
BLUE = "#20509a"
LINE = "#d9dfe7"
SOFT_BLUE = "#edf3fa"


def _money(amount: Money) -> str:
    return f"{amount.currency} {amount.minor_units / 100:,.2f}"


def _paragraph(value: str, *, muted: bool = False) -> str:
    color = MUTED if muted else INK
    return (
        f'<p style="margin:0 0 12px;color:{color};font-size:14px;line-height:1.55">'
        f"{escape(value)}</p>"
    )


def _label(value: str) -> str:
    return (
        f'<p style="margin:0 0 10px;color:{BLUE};font-size:12px;font-weight:700;'
        f'letter-spacing:1.4px;text-transform:uppercase">{escape(value)}</p>'
    )


def _card(content: str, *, match: bool = False) -> str:
    background = BLUE if match else "#ffffff"
    border = f"border-left:5px solid {RED};" if match else f"border:1px solid {LINE};"
    return (
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
        'style="margin:0 0 16px;border-collapse:separate"><tr><td '
        f'style="padding:20px;{border}border-radius:7px;background:{background}">'
        f"{content}</td></tr></table>"
    )


def _link(value: str | None, label: str) -> str:
    url = safe_url(value) if value else None
    if not url:
        return ""
    return (
        f'<a href="{escape(url, quote=True)}" style="color:{BLUE};font-size:14px;'
        'font-weight:700;text-decoration:underline">'
        f"{escape(label)} &#8599;</a>"
    )


def _price(item: Leg | Stay) -> str:
    quote: Quote | None = item.quote
    if quote is None:
        price = _paragraph("Price unavailable — check current fare.", muted=True)
    else:
        scope = {
            "round_trip": "return journey",
            "leg": "journey leg",
            "stay": "stay",
            "night": "night",
            "unknown": "quoted item",
        }[quote.scope]
        taxes = {
            "included": "Taxes included",
            "excluded": "Taxes not included",
            "unknown": "Taxes not confirmed",
        }[quote.taxes]
        extra = (
            f" · {_money(quote.additional_taxes)} additional tax indicated"
            if quote.additional_taxes
            else ""
        )
        price = (
            f'<p style="margin:0 0 4px;color:{INK};font-size:21px;font-weight:700">'
            f"{escape(_money(quote.amount))}</p>"
            + _paragraph(f"{scope} for your {quote.unit}", muted=True)
            + _paragraph(
                f"Checked {quote.observed_at.astimezone(UTC).strftime('%d %b %Y, %H:%M')} "
                f"UTC · {taxes}{extra}",
                muted=True,
            )
            + "".join(_paragraph(caveat, muted=True) for caveat in quote.caveats)
        )
    source = item.offer.evidence
    link_label = (
        "View on Google Flights"
        if isinstance(item, Leg) and item.mode == "flight"
        else "View on travel provider"
    )
    return (
        f'<div style="margin-top:16px;padding-top:15px;border-top:1px solid {LINE}">'
        + price
        + _paragraph(f"Price source: {source.underlying_source} via {source.provider}", muted=True)
        + _link(item.offer.booking_url, link_label)
        + (
            _paragraph("You may need to select this option again. Prices can change.", muted=True)
            if item.offer.link_kind == "contextual_search" and item.offer.booking_url
            else ""
        )
        + "</div>"
    )


def _transport(leg: Leg, direction: str) -> str:
    route = f"{leg.origin} → {leg.destination}"
    times = (
        f"{leg.departs_at.strftime('%d %b %Y, %H:%M')} local → "
        f"{leg.arrives_at.strftime('%d %b %Y, %H:%M')} local"
    )
    content = (
        _label(f"{direction} · {leg.mode} · {leg.operator} {leg.service_number}")
        + f'<h3 style="margin:0 0 9px;color:{INK};font-size:21px;line-height:1.2">'
        f"{escape(route)}</h3>"
        + _paragraph(times)
        + _price(leg)
        + "".join(_paragraph(caveat, muted=True) for caveat in leg.caveats)
    )
    return _card(content)


def _stay(stay: Stay) -> str:
    details = f"{stay.bathroom.capitalize()} bathroom · " + (
        f"{stay.review_score}/10 review score"
        if stay.review_score is not None
        else "Review score unavailable"
    )
    content = (
        _label(f"STAY · {stay.check_in} — {stay.check_out}")
        + f'<h3 style="margin:0 0 9px;color:{INK};font-size:21px;line-height:1.2">'
        f"{escape(stay.property_name)}</h3>"
        + _paragraph(stay.room_description)
        + _paragraph(details, muted=True)
        + _price(stay)
        + "".join(_paragraph(caveat, muted=True) for caveat in stay.caveats)
    )
    return _card(content)


def _match(trip: Trip) -> str:
    fixture = trip.fixture
    kickoff = fixture.kickoff_at.astimezone(ZoneInfo(fixture.timezone))
    return _card(
        '<p style="margin:0 0 10px;color:#e4edfb;font-size:12px;font-weight:700;'
        'letter-spacing:1.4px">MATCHDAY</p>'
        '<h3 style="margin:0 0 9px;color:#ffffff;font-size:21px;line-height:1.2">'
        f"{escape(fixture.opponent)} v Crystal Palace</h3>"
        f'<p style="margin:0 0 10px;color:#ffffff;font-size:14px">'
        f"{escape(kickoff.strftime('%A %d %B %Y, %H:%M'))} local</p>"
        f'<p style="margin:0;color:#e4edfb;font-size:13px;line-height:1.5">'
        f"{escape(fixture.venue)} · {escape(fixture.venue_status)} venue · "
        "Match ticket not included</p>",
        match=True,
    )


def _trip(trip: Trip) -> str:
    badge = "Ready to review" if trip.feasibility == "verified" else "Checks outstanding"
    header = (
        _label(trip.fixture.city)
        + f'<p style="margin:0 0 12px;color:{BLUE};font-size:13px;font-weight:700">'
        f"{escape(badge)}</p>"
        + f'<h2 style="margin:0 0 12px;color:{INK};font-size:27px;line-height:1.2">'
        f"Palace at {escape(trip.fixture.opponent)}</h2>" + _paragraph(trip.summary)
    )
    journey = trip.journey
    cards = ""
    if journey:
        cards += "".join(_transport(leg, "OUTBOUND") for leg in journey.outbound)
    if trip.stay:
        cards += _stay(trip.stay)
    cards += _match(trip)
    if journey:
        cards += "".join(_transport(leg, "RETURN") for leg in journey.inbound)
    if trip.transfers or trip.maps_transfers:
        cards += f'<h3 style="margin:8px 0 16px;color:{INK};font-size:20px">Getting between the stops</h3>'
        for transfer in trip.transfers:
            cards += _card(
                f'<h4 style="margin:0 0 9px;color:{INK};font-size:17px">'
                f"{escape(transfer.title)}</h4>"
                + _paragraph(transfer.description)
                + _link(transfer.source_url, "Official travel guidance")
                + _paragraph(
                    f"Reviewed {transfer.reviewed_at.strftime('%d %b %Y')} · "
                    "Transfer fares excluded",
                    muted=True,
                )
            )
        for maps_transfer in trip.maps_transfers:
            cards += _card(
                f'<h4 style="margin:0 0 9px;color:{INK};font-size:17px">'
                f"{escape(maps_transfer.title)}</h4>"
                + _paragraph(maps_transfer.description)
                + _link(maps_transfer.url, "Open in Google Maps")
            )
    total = _money(trip.known_total) if trip.known_total else "Total price unavailable"
    cards += (
        f'<div style="padding:18px 0;border-top:1px solid {LINE}">'
        f'<p style="margin:0 0 8px;color:{INK};font-size:23px;font-weight:700">'
        f"Known subtotal: {escape(total)}</p>"
        + _paragraph(
            f"Prices are available for {round(trip.price_coverage * 100)}% of the planned "
            "cost items. Check what's missing before comparing trips.",
            muted=True,
        )
        + "</div>"
    )
    if trip.gaps:
        cards += (
            f'<div style="margin:0 0 16px;padding:16px;border-left:4px solid {BLUE};'
            f'background:{SOFT_BLUE}"><strong style="color:{INK}">Before you book</strong>'
            '<ul style="margin:10px 0 0;padding-left:20px;color:#17253d;font-size:14px;'
            'line-height:1.5">'
            + "".join(f"<li>{escape(gap)}</li>" for gap in trip.gaps)
            + "</ul></div>"
        )
    return _card(header + cards)


def _render_html(snapshot: Snapshot, title: str) -> str:
    intro = (
        "Your saved away-day plan is below. Check each outstanding detail before booking."
        if snapshot.itinerary
        else "We couldn't verify a useful itinerary within this session. No travel has been booked."
    )
    trip_cards = (
        "".join(_trip(trip) for trip in snapshot.itinerary.trips)
        if snapshot.itinerary
        else _card(_paragraph(intro))
    )
    caveats = (
        "".join(_paragraph(caveat, muted=True) for caveat in snapshot.itinerary.caveats)
        if snapshot.itinerary
        else ""
    )
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        f"<title>{escape(title)}</title></head>"
        f'<body style="margin:0;padding:0;background:{PAPER};color:{INK};'
        'font-family:Arial,Helvetica,sans-serif">'
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
        f'style="background:{PAPER}"><tr><td align="center" style="padding:0 12px 32px">'
        '<table role="presentation" width="640" cellpadding="0" cellspacing="0" '
        'style="width:100%;max-width:640px;border-collapse:separate">'
        f'<tr><td style="height:5px;background:{RED};font-size:1px;line-height:5px">&nbsp;</td>'
        '<td style="width:5%;background:#ffffff;font-size:1px">&nbsp;</td>'
        f'<td style="width:48%;background:{BLUE};font-size:1px">&nbsp;</td></tr>'
        f'<tr><td colspan="3" style="padding:22px 18px;background:#ffffff;'
        f'border-bottom:1px solid {LINE}">'
        f'<strong style="color:{INK};font-size:16px;letter-spacing:1.2px">EAGLES '
        f'<span style="color:{BLUE}">AWAY</span></strong>'
        f'<span style="float:right;color:{MUTED};font-size:13px">Powered by Temporal</span>'
        '</td></tr><tr><td colspan="3" style="padding:32px 6px 0">'
        + _label("YOUR AWAY DAYS")
        + f'<h1 style="margin:0 0 20px;color:{INK};font-size:34px;line-height:1.12">'
        "A plan worth travelling for.</h1>"
        + _paragraph(intro)
        + trip_cards
        + caveats
        + _paragraph(
            "Prices may have changed. Confirm every detail on the travel provider's site.",
            muted=True,
        )
        + _paragraph(
            f"No match tickets, bookings, or travel to/from the {snapshot.origin_city} "
            "departure hub are included.",
            muted=True,
        )
        + "</td></tr></table></td></tr></table></body></html>"
    )


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
            for maps_transfer in trip.maps_transfers:
                text += [maps_transfer.title, maps_transfer.description, maps_transfer.url]
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
    return dict(
        subject=title,
        text="\n".join(text),
        html=_render_html(snapshot, title),
    )
