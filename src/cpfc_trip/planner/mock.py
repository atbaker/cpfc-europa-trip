"""Deterministic, clearly-labelled planning data for local product development."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, time, timedelta
from typing import Literal
from zoneinfo import ZoneInfo

from cpfc_trip.domain import (
    BookingReference,
    BudgetTier,
    FixtureSnapshot,
    FixtureTrip,
    Itinerary,
    MatchEvent,
    Money,
    PlanActivityInput,
    Stay,
    TransportLeg,
    TripAlternative,
)
from cpfc_trip.planner.providers import AcquisitionMethod, LaunchMode, load_policy_registry


@dataclass(frozen=True)
class DestinationProfile:
    airport: str
    budget_mode: Literal["flight", "rail"]
    budget_operator: str
    value_operator: str
    basic_stay: str
    value_stay: str
    comfort_stay: str
    base_transport: int
    base_stay: int


PROFILES: dict[str, DestinationProfile] = {
    "uel-2026-lyon-away": DestinationProfile(
        "Lyon city centre",
        "rail",
        "Eurostar + TGV (illustrative)",
        "Direct-flight option (illustrative)",
        "A well-rated central hostel",
        "A central boutique hotel",
        "A five-star Presqu'ile hotel",
        12_000,
        7_000,
    ),
    "uel-2026-besiktas-away": DestinationProfile(
        "Istanbul Airport",
        "flight",
        "One-stop flight option (illustrative)",
        "Direct-flight option (illustrative)",
        "A simple Beşiktaş guesthouse",
        "A Bosphorus-side boutique hotel",
        "A five-star Bosphorus hotel",
        18_000,
        6_500,
    ),
    "uel-2026-jagiellonia-away": DestinationProfile(
        "Warsaw Chopin Airport, then Białystok",
        "flight",
        "Flight + intercity rail (illustrative)",
        "Convenient flight + rail (illustrative)",
        "A simple Białystok hostel",
        "A central Białystok hotel",
        "A top-rated central hotel",
        16_000,
        5_000,
    ),
    "uel-2026-salzburg-away": DestinationProfile(
        "Salzburg city centre",
        "flight",
        "Munich flight + rail (illustrative)",
        "Direct-flight option (illustrative)",
        "A simple Salzburg guesthouse",
        "A central boutique hotel",
        "A five-star Altstadt hotel",
        17_000,
        7_500,
    ),
}


def build_mock_itinerary(input: PlanActivityInput) -> Itinerary:
    """Create a useful UI fixture without claiming live availability or prices."""

    load_policy_registry().authorize(
        "generic-travel-search",
        AcquisitionMethod.GENERIC_LINK,
        LaunchMode.INTERNAL_R_AND_D,
    )
    effective_tier = _tier_for_message(input.request.budget_tier, input.user_message)
    trips = tuple(_build_trip(input, fixture, effective_tier) for fixture in input.fixtures)
    qualifier = {
        BudgetTier.BUDGET: "lower-cost, more flexible",
        BudgetTier.VALUE: "best-value",
        BudgetTier.COMFORT: "comfort-first",
    }[effective_tier]
    return Itinerary(
        id=f"itinerary-{input.public_id}",
        revision=input.revision,
        title="Your Crystal Palace away days",
        summary=(
            f"A {qualifier} plan for {len(trips)} away fixture"
            f"{'s' if len(trips) != 1 else ''}. This local build uses illustrative routes "
            "and estimated prices so the full product flow can be tested safely."
        ),
        trips=trips,
        assumptions=(
            "Match venues remain provisional until confirmed by the club or UEFA.",
            "Times, routes, and prices are demo estimates—not live inventory.",
            "Match tickets are not included.",
        ),
        generated_at=datetime.now(UTC),
    )


def _tier_for_message(current: BudgetTier, message: str | None) -> BudgetTier:
    text = (message or "").lower()
    if any(word in text for word in ("cheaper", "cheapest", "hostel", "budget")):
        return BudgetTier.BUDGET
    if any(word in text for word in ("comfort", "direct", "luxury", "five-star")):
        return BudgetTier.COMFORT
    return current


def _build_trip(
    input: PlanActivityInput, fixture: FixtureSnapshot, tier: BudgetTier
) -> FixtureTrip:
    profile = PROFILES[fixture.id]
    destination_tz = ZoneInfo(fixture.venue.city.timezone)
    origin_tz = ZoneInfo("Europe/London")
    kickoff_local = fixture.kickoff_at.astimezone(destination_tz)
    outbound_date = kickoff_local.date() - timedelta(days=1)
    return_date = kickoff_local.date() + timedelta(days=1)
    departure = datetime.combine(outbound_date, time(8, 15), origin_tz)
    arrival = datetime.combine(outbound_date, time(15, 0), destination_tz)
    return_departure = datetime.combine(return_date, time(11, 30), destination_tz)
    return_arrival = datetime.combine(return_date, time(17, 15), origin_tz)

    factor = {BudgetTier.BUDGET: 0.78, BudgetTier.VALUE: 1.0, BudgetTier.COMFORT: 1.65}[tier]
    party_size = input.request.travellers.size
    transport_total = round(profile.base_transport * factor) * party_size
    stay_total = round(profile.base_stay * factor) * input.request.travellers.rooms * 2
    total = transport_total + stay_total

    if tier == BudgetTier.BUDGET:
        operator = profile.budget_operator
        mode: Literal["flight", "rail"] = profile.budget_mode
        property_name = profile.basic_stay
        transport_tradeoff = "Wider gateway search and extra changes can reduce total cost."
    elif tier == BudgetTier.COMFORT:
        operator = profile.value_operator
        mode = "flight"
        property_name = profile.comfort_stay
        transport_tradeoff = "Convenient timings and fewer changes rank above headline price."
    else:
        operator = profile.value_operator
        mode = "flight"
        property_name = profile.value_stay
        transport_tradeoff = "Balances the estimated whole-trip cost with journey time."

    checked_at = datetime.now(UTC)
    flight_search = BookingReference(
        provider="Google Travel",
        url="https://www.google.com/travel/flights",
        label="Search current transport",
    )
    hotel_search = BookingReference(
        provider="Google Hotels",
        url="https://www.google.com/travel/hotels",
        label="Search current stays",
    )
    caveat = ("Illustrative option; check the current timetable, fare, baggage, and terms.",)
    items = (
        TransportLeg(
            id=f"{fixture.id}-outbound-r{input.revision}",
            mode=mode,
            origin_name=input.request.origin,
            destination_name=profile.airport,
            origin_timezone="Europe/London",
            destination_timezone=fixture.venue.city.timezone,
            departs_at=departure,
            arrives_at=arrival,
            operator=operator,
            price=Money(minor_units=transport_total // 2),
            price_confidence="estimated",
            checked_at=checked_at,
            booking=flight_search,
            self_transfer=tier == BudgetTier.BUDGET and fixture.id != "uel-2026-lyon-away",
            caveats=caveat,
        ),
        Stay(
            id=f"{fixture.id}-stay-r{input.revision}",
            property_name=property_name,
            place_name=fixture.venue.city.name,
            check_in=outbound_date,
            check_out=return_date,
            room_description=_room_description(tier),
            price=Money(minor_units=stay_total),
            price_confidence="estimated",
            checked_at=checked_at,
            booking=hotel_search,
            venue_transfer_note=(
                "Prioritise a stay with a verified post-match route from the confirmed venue."
            ),
            caveats=("Named property class is illustrative; no room is being held.",),
        ),
        MatchEvent(
            id=f"{fixture.id}-match",
            fixture=fixture,
            recommended_arrival_at=fixture.kickoff_at - timedelta(minutes=90),
        ),
        TransportLeg(
            id=f"{fixture.id}-return-r{input.revision}",
            mode=mode,
            origin_name=profile.airport,
            destination_name=input.request.origin,
            origin_timezone=fixture.venue.city.timezone,
            destination_timezone="Europe/London",
            departs_at=return_departure,
            arrives_at=return_arrival,
            operator=operator,
            price=Money(minor_units=transport_total - transport_total // 2),
            price_confidence="estimated",
            checked_at=checked_at,
            booking=flight_search,
            self_transfer=tier == BudgetTier.BUDGET and fixture.id != "uel-2026-lyon-away",
            caveats=caveat,
        ),
    )
    return FixtureTrip(
        id=f"trip-{fixture.id}",
        fixture_ids=(fixture.id,),
        title=f"{fixture.home_team_name} away",
        items=items,
        alternatives=(
            TripAlternative(
                id=f"{fixture.id}-alternative",
                label="Worth comparing",
                summary=(
                    "Try a nearby gateway and add rail for a possible saving."
                    if tier != BudgetTier.COMFORT
                    else "Compare a central hotel with an airport transfer package."
                ),
            ),
        ),
        estimated_total=Money(minor_units=total),
        per_person_total=Money(minor_units=total // party_size),
        tradeoffs=(transport_tradeoff, "All prices are estimates in this local demo."),
        booking_order=("Confirm the match venue", "Book flexible transport", "Book the stay"),
    )


def _room_description(tier: BudgetTier) -> str:
    return {
        BudgetTier.BUDGET: "Hostel or simple private room",
        BudgetTier.VALUE: "Well-rated mid-range or boutique room",
        BudgetTier.COMFORT: "Four/five-star room with convenient cancellation terms",
    }[tier]
