"""Pure enumeration, feasibility and ranking. No I/O and no invented commercial facts."""

from datetime import timedelta
from itertools import pairwise
from zoneinfo import ZoneInfo

from cpfc_trip.domain import (
    Alternative,
    Brief,
    Fixture,
    Journey,
    Party,
    Route,
    SearchBatch,
    SearchSpec,
    Stay,
    Trip,
)
from cpfc_trip.planner.agent import Intent
from cpfc_trip.planner.maps_links import transfer_links
from cpfc_trip.planner.prices import total


def enumerate_specs(
    brief: Brief, fixtures: tuple[Fixture, ...], routes: tuple[Route, ...], recorded: bool = False
) -> list[SearchSpec]:
    grouped: list[list[SearchSpec]] = []
    for f in fixtures:
        window = next(w for w in brief.windows if w.fixture_id == f.id)
        day = f.kickoff_at.astimezone(ZoneInfo(f.timezone)).date()
        dates = [
            window.earliest_departure.date() + timedelta(days=i)
            for i in range(
                (window.latest_return.date() - window.earliest_departure.date()).days + 1
            )
        ]
        pairs = [
            (start, end) for start in dates for end in dates if start <= day <= end and start < end
        ]
        preferred = (day - timedelta(days=1), day + timedelta(days=1))
        pairs.sort(
            key=lambda pair: (
                (pair[1] - pair[0]).days if brief.flexibility == "tight" else pair != preferred,
                abs((pair[0] - preferred[0]).days) + abs((pair[1] - preferred[1]).days),
                pair,
            )
        )
        pairs = pairs[:3]
        allowed = [r for r in routes if r.fixture_id == f.id and (r.enabled or recorded)]
        options = [
            SearchSpec(
                fixture=f,
                route=r,
                party=brief.travellers,
                outbound_date=start,
                return_date=end,
                budget_tier=brief.budget_tier,
            )
            for start, end in pairs
            for r in allowed
        ]
        grouped.append(options[: len(allowed)] if recorded else options)
    # Give every selected fixture an initial route/date candidate before spending on alternatives.
    return [
        options[index]
        for index in range(max(map(len, grouped), default=0))
        for options in grouped
        if index < len(options)
    ]


def feasible(
    journey: Journey,
    stay: Stay,
    fixture: Fixture,
    brief: Brief,
    intent: Intent,
    route: Route | None = None,
) -> bool:
    if not feasible_journey(journey, fixture, brief, intent, route):
        return False
    outbound, inbound = journey.outbound, journey.inbound
    if (
        stay.check_in != outbound[-1].arrives_at.astimezone(ZoneInfo(fixture.timezone)).date()
        or stay.check_out != inbound[0].departs_at.astimezone(ZoneInfo(fixture.timezone)).date()
    ):
        return False
    if intent.private_room and stay.room_type != "private":
        return False
    if intent.private_bathroom and stay.bathroom != "private":
        return False
    if (
        stay.max_guests is not None
        and stay.max_guests * brief.travellers.rooms < brief.travellers.size
    ):
        return False
    return True


def feasible_journey(
    journey: Journey,
    fixture: Fixture,
    brief: Brief,
    intent: Intent,
    route: Route | None = None,
) -> bool:
    """Check that a dated return journey fits the brief before showing it."""
    window = next(w for w in brief.windows if w.fixture_id == fixture.id)
    if intent.unsupported_requirements:
        return False
    outbound, inbound = journey.outbound, journey.inbound
    if intent.transport_mode and outbound[0].mode != intent.transport_mode:
        return False
    if route:
        local = ZoneInfo(fixture.timezone)
        arrival = outbound[-1].arrives_at.astimezone(local)
        departure = inbound[0].departs_at.astimezone(local)
        if not (
            route.gateway_arrival_hours[0] <= arrival.hour < route.gateway_arrival_hours[1]
            and route.gateway_departure_hours[0]
            <= departure.hour
            < route.gateway_departure_hours[1]
        ):
            return False
        if (route.mode == "rail" or route.onward_stations) and any(
            b.departs_at - a.arrives_at < timedelta(minutes=route.minimum_transfer_minutes)
            for direction in (outbound, inbound)
            for a, b in pairwise(direction)
        ):
            return False
    if (
        outbound[0].departs_at < window.earliest_departure
        or inbound[-1].arrives_at > window.latest_return
    ):
        return False
    if outbound[-1].arrives_at > fixture.kickoff_at - timedelta(hours=5):
        return False
    if inbound[0].departs_at < fixture.kickoff_at + timedelta(hours=5):
        return False
    for direction in (outbound, inbound):
        if any(b.departs_at < a.arrives_at for a, b in pairwise(direction)):
            return False
    if intent.preferred_airports and (
        outbound[0].origin not in intent.preferred_airports
        or inbound[-1].destination not in intent.preferred_airports
    ):
        return False
    return True


def rank(journey: Journey, stay: Stay, party: Party, tier: str) -> float:
    legs = journey.outbound + journey.inbound
    cost, coverage = total([*(x.quote for x in legs), stay.quote], party)
    # Unknown scope/currency never wins by pretending to be free.
    pounds = cost.minor_units / 100 if cost and cost.currency == "GBP" else 10000
    hours = sum(
        (x[-1].arrives_at - x[0].departs_at).total_seconds() / 3600
        for x in (journey.outbound, journey.inbound)
    )
    comfort_penalty = (30 if stay.room_type == "dorm" else 0) + (10 - (stay.review_score or 5)) * 5
    return (
        pounds
        + (0 if tier == "budget" else 25 if tier == "value" else 60) * hours
        + (1 - coverage) * 1500
        + (comfort_penalty * (0 if tier == "budget" else 2 if tier == "value" else 5))
    )


def choose(
    fixture: Fixture,
    batches: list[SearchBatch],
    brief: Brief,
    routes: tuple[Route, ...],
    intent: Intent,
) -> Trip:
    journeys = [j for b in batches for j in b.journeys]
    stays = [s for b in batches for s in b.stays]
    by_route = {r.id: r for r in routes}
    candidates = [
        (j, s)
        for j in journeys
        for s in stays
        if j.route_id in by_route and feasible(j, s, fixture, brief, intent, by_route[j.route_id])
    ]
    if not candidates:
        return Trip(
            fixture=fixture,
            summary="We could not verify a complete trip for this fixture.",
            gaps=tuple(
                dict.fromkeys(
                    [
                        "Travel and accommodation evidence is incomplete.",
                        *intent.unsupported_requirements,
                        *(g for b in batches for g in b.gaps),
                    ]
                )
            )[:8],
        )
    candidates.sort(key=lambda x: rank(x[0], x[1], brief.travellers, brief.budget_tier))
    journey, stay = candidates[0]
    route = next(r for r in routes if r.id == journey.route_id)
    amount, coverage = total(
        [*(x.quote for x in journey.outbound + journey.inbound), stay.quote, None, None, None],
        brief.travellers,
    )
    gaps = [
        route.transfer_note,
        "Confirm late check-in and post-match access to the accommodation.",
    ]
    if (
        route.onward_stations
        and route.mode != "rail"
        and all(leg.mode != "rail" for leg in journey.outbound)
    ):
        # Never label an airport-only journey as a complete trip to an onward destination.
        gaps.append("Onward rail has not been verified; this is an incomplete travel option.")
    if fixture.venue_status != "confirmed":
        gaps.append("The match venue and away-supporter access instructions remain provisional.")
    alternatives = []
    seen = {(journey.outbound[0].mode, stay.property_name)}
    for other, room in candidates[1:]:
        key = (other.outbound[0].mode, room.property_name)
        if key in seen:
            continue
        seen.add(key)
        value, fraction = total(
            [*(x.quote for x in other.outbound + other.inbound), room.quote, None, None, None],
            brief.travellers,
        )
        alternatives.append(
            Alternative(
                journey=other,
                stay=room,
                known_total=value,
                price_coverage=fraction,
                summary=f"{other.outbound[0].mode.title()} with {room.property_name}; compare missing costs separately.",
            )
        )
        if len(alternatives) == 2:
            break
    return Trip(
        fixture=fixture,
        journey=journey,
        stay=stay,
        known_total=amount,
        price_coverage=coverage,
        gaps=tuple(gaps),
        feasibility="needs_checks",
        transfers=route.guidance,
        maps_transfers=transfer_links(brief.origin_city, journey, stay, fixture),
        alternatives=tuple(alternatives),
        summary=f"{'Prioritises lower known costs among the checked options' if brief.budget_tier == 'budget' else 'Balanced price and journey time' if brief.budget_tier == 'value' else 'Prioritises shorter journeys and more comfortable stays'}. Transfer fares and outstanding checks are excluded.",
    )
