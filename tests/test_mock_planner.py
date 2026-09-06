from uuid import uuid4

import pytest

from cpfc_trip.domain import (
    BudgetTier,
    MatchEvent,
    PlanActivityInput,
    PlanningRequest,
    TransportLeg,
    TravellerParty,
)
from cpfc_trip.fixtures import fixtures_by_id
from cpfc_trip.planner.mock import build_mock_itinerary


def planner_input(tier: BudgetTier, message: str | None = None) -> PlanActivityInput:
    fixture_ids = ("uel-2026-lyon-away",)
    public_id = uuid4()
    return PlanActivityInput(
        public_id=public_id,
        request=PlanningRequest(
            fixture_ids=fixture_ids,
            origin="London",
            travellers=TravellerParty(adults=2),
            flexibility_days=1,
            budget_tier=tier,
            contact_id=uuid4(),
            request_id=uuid4(),
        ),
        fixtures=fixtures_by_id(fixture_ids),
        revision=1,
        turn_id="initial",
        user_message=message,
    )


@pytest.mark.parametrize("tier", list(BudgetTier))
def test_mock_plans_are_chronologically_feasible(tier: BudgetTier) -> None:
    itinerary = build_mock_itinerary(planner_input(tier))
    trip = itinerary.trips[0]
    outbound = trip.items[0]
    match = trip.items[2]
    returning = trip.items[3]
    assert isinstance(outbound, TransportLeg)
    assert isinstance(match, MatchEvent)
    assert isinstance(returning, TransportLeg)
    assert outbound.arrives_at < match.recommended_arrival_at < match.fixture.kickoff_at
    assert returning.departs_at > match.fixture.kickoff_at
    assert match.ticket_included is False


def test_budget_tiers_materially_change_estimated_total() -> None:
    totals = [
        build_mock_itinerary(planner_input(tier)).trips[0].estimated_total for tier in BudgetTier
    ]
    assert all(total is not None for total in totals)
    values = [total.minor_units for total in totals if total]
    assert values[0] < values[1] < values[2]


def test_follow_up_can_request_a_cheaper_revision() -> None:
    itinerary = build_mock_itinerary(planner_input(BudgetTier.COMFORT, "Make it cheaper"))
    first_leg = itinerary.trips[0].items[0]
    assert isinstance(first_leg, TransportLeg)
    assert first_leg.mode == "rail"
    assert "lower-cost" in itinerary.summary


def test_planner_payload_contains_contact_reference_not_email() -> None:
    serialized = planner_input(BudgetTier.VALUE).model_dump_json()
    assert "@" not in serialized
    assert "contact_id" in serialized
