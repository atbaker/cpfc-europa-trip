import pytest
from pydantic import ValidationError

from cpfc_trip.domain import Brief, Party
from cpfc_trip.planner.agent import Intent
from cpfc_trip.planner.planning import enumerate_specs, feasible
from cpfc_trip.planner.recorded import sample


def test_catalog_fails_closed(session_input):
    assert not enumerate_specs(
        session_input.brief,
        session_input.fixtures,
        tuple(r.model_copy(update={"enabled": False}) for r in session_input.routes),
    )
    assert (
        len(
            enumerate_specs(session_input.brief, session_input.fixtures, session_input.routes, True)
        )
        == 1
    )


def test_constraints_and_kickoff_gate(session_input):
    s = enumerate_specs(session_input.brief, session_input.fixtures, session_input.routes, True)[0]
    journey = sample(s, "flight").journeys[0]
    stay = sample(s, "stay").stays[0]
    intent = Intent(action="revise", answer="")
    assert feasible(journey, stay, s.fixture, session_input.brief, intent)
    late = journey.model_copy(
        update={
            "outbound": (
                journey.outbound[0].model_copy(update={"arrives_at": s.fixture.kickoff_at}),
            )
        }
    )
    assert not feasible(late, stay, s.fixture, session_input.brief, intent)
    assert not feasible(
        journey,
        stay,
        s.fixture,
        session_input.brief,
        intent.model_copy(update={"unsupported_requirements": ("step-free route",)}),
    )
    dorm = stay.model_copy(update={"room_type": "dorm", "bathroom": "shared"})
    assert feasible(journey, dorm, s.fixture, session_input.brief, intent)
    assert not feasible(
        journey,
        dorm,
        s.fixture,
        session_input.brief,
        intent.model_copy(update={"private_room": True}),
    )


@pytest.mark.parametrize("adults", [0, 9, -1])
def test_party_bound(adults):
    with pytest.raises(ValidationError):
        Party(adults=adults)


def test_duplicate_fixture_rejected():
    with pytest.raises(ValidationError):
        Brief(fixture_ids=("same", "same"))


def test_search_respects_custom_window_and_prioritizes_each_fixture(session_input):
    from datetime import timedelta

    from cpfc_trip.domain import Window

    fixture = session_input.fixtures[0]
    start = fixture.kickoff_at - timedelta(days=2)
    end = fixture.kickoff_at + timedelta(days=2)
    brief = session_input.brief.model_copy(
        update={
            "windows": (Window(fixture_id=fixture.id, earliest_departure=start, latest_return=end),)
        }
    )
    routes = tuple(r.model_copy(update={"enabled": True}) for r in session_input.routes)
    specs = enumerate_specs(brief, session_input.fixtures, routes)
    assert 1 < len({(s.outbound_date, s.return_date) for s in specs}) <= 3
    assert all(start.date() <= s.outbound_date < s.return_date <= end.date() for s in specs)
    assert any(s.outbound_date == start.date() for s in specs)


def test_model_rejects_outside_catalog_airport():
    with pytest.raises(ValidationError):
        Intent(action="revise", answer="", preferred_airports=("MAN",))
