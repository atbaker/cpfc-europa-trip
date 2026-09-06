"""Transactional itinerary rendering and delivery."""

from __future__ import annotations

import asyncio
import html
from datetime import UTC, datetime

import resend

from cpfc_trip.config import get_settings
from cpfc_trip.domain import EmailActivityInput, EmailActivityResult, MatchEvent, Stay, TransportLeg
from cpfc_trip.persistence.repository import (
    create_delivery,
    find_delivery,
    get_contact_email,
)


async def deliver_itinerary(input: EmailActivityInput) -> EmailActivityResult:
    settings = get_settings()
    key = f"final-itinerary/{input.public_id}/{input.itinerary.revision}"
    existing = await find_delivery(key)
    if existing and existing.provider_message_id:
        return EmailActivityResult(provider_message_id=existing.provider_message_id)

    recipient = await get_contact_email(input.contact_id)
    subject = "Your Crystal Palace away-day itinerary"
    rendered = render_itinerary_email(input)
    if settings.email_mode == "preview":
        provider_id = f"preview-{input.public_id}-{input.itinerary.revision}"
    else:
        resend.api_key = settings.resend_api_key
        response = await asyncio.to_thread(
            resend.Emails.send,
            {
                "from": settings.resend_from_email,
                "to": [recipient],
                "subject": subject,
                "html": rendered,
            },
            {"idempotency_key": key},
        )
        provider_id = str(response["id"])

    await create_delivery(
        idempotency_key=key,
        public_id=input.public_id,
        contact_id=input.contact_id,
        itinerary_revision=input.itinerary.revision,
        subject=subject,
        preview_html=rendered,
        status="sent",
        provider_message_id=provider_id,
    )
    return EmailActivityResult(provider_message_id=provider_id)


def render_itinerary_email(input: EmailActivityInput) -> str:
    itinerary = input.itinerary
    trip_sections: list[str] = []
    for trip in itinerary.trips:
        items: list[str] = []
        for item in trip.items:
            if isinstance(item, TransportLeg):
                detail = (
                    f"{item.mode.title()}: {item.origin_name} → {item.destination_name}<br>"
                    f"{item.departs_at:%a %d %b, %H:%M %Z} - {item.arrives_at:%H:%M %Z}"
                )
            elif isinstance(item, Stay):
                detail = (
                    f"Stay: {item.property_name}<br>{item.check_in:%d %b} - {item.check_out:%d %b}"
                )
            elif isinstance(item, MatchEvent):
                kickoff = item.fixture.kickoff_at.astimezone(
                    __import__("zoneinfo", fromlist=["ZoneInfo"]).ZoneInfo(
                        item.fixture.venue.city.timezone
                    )
                )
                detail = (
                    f"Match: {item.fixture.home_team_name} v Crystal Palace<br>"
                    f"{kickoff:%a %d %b, %H:%M %Z} · Match ticket not included"
                )
            else:  # pragma: no cover - discriminated union exhaustiveness
                continue
            escaped_detail = html.escape(detail).replace("&lt;br&gt;", "<br>")
            items.append(f'<li style="margin:0 0 14px;color:#18233b">{escaped_detail}</li>')
        trip_sections.append(
            f'<section style="background:#fff;border-radius:16px;padding:20px;margin:0 0 18px">'
            f'<h2 style="margin:0 0 14px;color:#1b3f92">{html.escape(trip.title)}</h2>'
            f'<ul style="padding-left:20px;margin:0">{"".join(items)}</ul></section>'
        )
    sent_at = datetime.now(UTC).strftime("%d %b %Y at %H:%M UTC")
    return f"""<!doctype html>
<html><body style="margin:0;background:#f2f5fa;font-family:Arial,sans-serif">
<main style="max-width:640px;margin:auto;padding:28px 16px">
<p style="font-weight:700;color:#e21d3c">CRYSTAL PALACE AWAY DAYS</p>
<h1 style="color:#172642">{html.escape(itinerary.title)}</h1>
<p style="color:#52617a;line-height:1.5">{html.escape(itinerary.summary)}</p>
{"".join(trip_sections)}
<p style="color:#52617a;font-size:13px;line-height:1.5">Prices and availability can change.
Recheck every fare and booking condition before paying. This planner does not sell travel and
match tickets are not included.</p>
<p style="color:#52617a;font-size:13px">Sent {sent_at}. Sponsored by Temporal in partnership
with Crystal Palace Football Club.</p>
</main></body></html>"""
