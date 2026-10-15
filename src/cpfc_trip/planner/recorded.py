"""Synthetic development examples. Never enabled in production or presented as live quotes."""

from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from cpfc_trip.domain import (
    Evidence,
    Journey,
    Leg,
    Money,
    Offer,
    Quote,
    SearchBatch,
    SearchSpec,
    Stay,
)
from cpfc_trip.origins import UK_RAIL


def sample(spec: SearchSpec, kind: str) -> SearchBatch:
    checked = datetime(2026, 9, 6, tzinfo=ZoneInfo("UTC"))
    base = spec.fixture.id + str(spec.outbound_date)
    ref = Offer(
        id=base + kind,
        search_fingerprint="synthetic-development-data",
        evidence=Evidence(
            provider="Development fixture",
            underlying_source="Synthetic sample",
            retrieved_at=checked,
        ),
        booking_url=None,
        link_kind="generic_search",
    )
    q = Quote(
        id=ref.id,
        amount=Money(minor_units=18000 * spec.party.size, currency="GBP"),
        scope="stay" if kind == "stay" else "round_trip",
        unit="party",
        priced_party=spec.party,
        taxes="included",
        observed_at=checked,
        caveats=("Synthetic test price — not a live offer.",),
    )
    if kind == "stay":
        return SearchBatch(
            stays=(
                Stay(
                    id=ref.id,
                    property_name="Sample city guesthouse",
                    check_in=spec.outbound_date,
                    check_out=spec.return_date,
                    room_description="Private twin room",
                    bathroom="private",
                    room_type="private",
                    max_guests=spec.party.size,
                    review_score=8.2,
                    offer=ref,
                    quote=q,
                ),
            )
        )
    london, destination = ZoneInfo("Europe/London"), ZoneInfo(spec.route.destination_timezone)
    rail = kind == "rail"
    airport = (
        UK_RAIL[spec.route.origin][1]
        if rail and spec.route.origin in UK_RAIL
        else "St Pancras International"
        if rail
        else spec.route.origin.split(",")[0]
    )
    gateway = "Lyon Part Dieu" if rail else spec.route.destination
    dep = datetime.combine(spec.outbound_date, time(9), london)
    back = datetime.combine(spec.return_date, time(14), destination)
    out = Leg(
        id=base + "out",
        mode="rail" if rail else "flight",
        origin=airport,
        destination=gateway,
        departs_at=dep,
        arrives_at=(dep + timedelta(hours=8 if rail else 2)).astimezone(destination),
        operator="Sample rail journey" if rail else "Sample airline",
        offer=ref,
        quote=q,
    )
    inbound = Leg(
        id=base + "in",
        mode="rail" if rail else "flight",
        origin=gateway,
        destination=airport,
        departs_at=back,
        arrives_at=(back + timedelta(hours=8 if rail else 2)).astimezone(london),
        operator="Sample rail journey" if rail else "Sample airline",
        offer=ref,
        quote=q,
    )
    return SearchBatch(
        journeys=(Journey(id=base, route_id=spec.route.id, outbound=(out,), inbound=(inbound,)),)
    )
