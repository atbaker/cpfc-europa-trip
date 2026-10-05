import pytest
from pydantic import ValidationError

from cpfc_trip.domain import Brief, Party
from cpfc_trip.origins import airports_for, routes_for_origin
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
        == 2
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


def test_uk_departure_city_resolves_without_guessing(session_input):
    assert airports_for(" manchester ") == ("MAN",)
    assert airports_for("London") == ("LHR", "LGW", "STN", "LTN")
    with pytest.raises(ValueError, match="supported UK departure city"):
        airports_for("Paris")
    routes = routes_for_origin(session_input.routes, "Manchester")
    assert len(routes) == 2
    assert routes[0].origin == "MAN" and routes[0].mode == "flight"
    assert routes[0].id != session_input.routes[0].id
    assert routes[1].origin == "Manchester" and routes[1].mode == "rail"
    assert all(
        route.mode == "flight" for route in routes_for_origin(session_input.routes, "Belfast")
    )
    assert any(route.mode == "rail" for route in routes_for_origin(session_input.routes, "London"))
    edinburgh_rail = next(
        route
        for route in routes_for_origin(session_input.routes, "Edinburgh")
        if route.mode == "rail"
    )
    assert edinburgh_rail.gateway_arrival_hours == (6, 24)
    assert "hotel check-in" in edinburgh_rail.transfer_note


def test_recorded_city_offers_a_rail_example(session_input):
    brief = session_input.brief.model_copy(
        update={"origin_city": "Manchester", "transport_mode": "rail"}
    )
    specs = enumerate_specs(
        brief, session_input.fixtures, routes_for_origin(session_input.routes, "Manchester"), True
    )
    assert {spec.route.mode for spec in specs} == {"flight", "rail"}
    rail = next(spec for spec in specs if spec.route.mode == "rail")
    journey = sample(rail, "rail").journeys[0]
    stay = sample(rail, "stay").stays[0]
    assert journey.outbound[0].mode == "rail"
    assert journey.outbound[0].origin == "Manchester Piccadilly"
    assert feasible(
        journey,
        stay,
        rail.fixture,
        brief,
        Intent(action="revise", answer="", transport_mode="rail"),
        rail.route,
    )


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


def test_model_rejects_invalid_airport_code():
    with pytest.raises(ValidationError):
        Intent(action="revise", answer="", preferred_airports=("MAN<script>",))
