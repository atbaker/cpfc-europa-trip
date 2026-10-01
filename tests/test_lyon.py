import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from cpfc_trip.planner.agent import Intent
from cpfc_trip.planner.planning import enumerate_specs, feasible, rank
from cpfc_trip.planner.providers.searchapi import connect_rail, normalize_trains
from cpfc_trip.planner.recorded import sample


def test_live_station_contract_and_cross_paris_buffer():
    raw = json.loads(Path("tests/data/lyon-rail.json").read_text())
    groups = []
    for key, data in raw.items():
        origin, destination = key.split("-")
        groups.append(
            normalize_trains(
                data, origin, destination, data["train_results"]["date"], datetime.now(UTC)
            )
        )
    for first, second in (groups[:2], groups[2:]):
        pairs = connect_rail(first, second, 180)
        assert pairs and pairs[0][1].departs_at - pairs[0][0].arrives_at >= timedelta(hours=3)
        close = second[0].model_copy(
            update={"departs_at": first[0].arrives_at + timedelta(minutes=35)}
        )
        assert not connect_rail(first, (close,), 180)
        wrong = second[0].model_copy(update={"origin": "Lille Europe"})
        assert not connect_rail(first, (wrong,), 180)
    block = raw["London-Paris"]
    block["train_results"]["trains"][0]["instructions"][0]["arrive_at"]["place"] = "Lille Europe"
    assert not normalize_trains(block, "London", "Paris", "2026-10-14", datetime.now(UTC))


def test_lyon_supported_hours_and_hard_mode(session_input):
    spec = enumerate_specs(session_input.brief, session_input.fixtures, session_input.routes, True)[
        0
    ]
    journey = sample(spec, "flight").journeys[0]
    stay = sample(spec, "stay").stays[0]
    intent = Intent(action="revise", answer="")
    assert feasible(journey, stay, spec.fixture, session_input.brief, intent, spec.route)
    assert not feasible(
        journey,
        stay,
        spec.fixture,
        session_input.brief,
        intent.model_copy(update={"transport_mode": "rail"}),
        spec.route,
    )
    early = journey.inbound[0].model_copy(
        update={"departs_at": journey.inbound[0].departs_at.replace(hour=5)}
    )
    assert not feasible(
        journey.model_copy(update={"inbound": (early,)}),
        stay,
        spec.fixture,
        session_input.brief,
        intent,
        spec.route,
    )


def test_budget_prefers_cost_but_comfort_penalizes_dorms(session_input):
    spec = enumerate_specs(session_input.brief, session_input.fixtures, session_input.routes, True)[
        0
    ]
    journey = sample(spec, "flight").journeys[0]
    room = sample(spec, "stay").stays[0]
    cheap = room.model_copy(
        update={
            "room_type": "dorm",
            "review_score": 5,
            "quote": room.quote.model_copy(
                update={"amount": room.quote.amount.model_copy(update={"minor_units": 1000})}
            ),
        }
    )
    assert rank(journey, cheap, spec.party, "budget") < rank(journey, room, spec.party, "budget")
    assert rank(journey, room, spec.party, "comfort") < rank(journey, cheap, spec.party, "comfort")


def test_private_bathroom_requires_explicit_room_evidence():
    from datetime import date

    from cpfc_trip.catalog import load_catalog
    from cpfc_trip.domain import Party, SearchSpec
    from cpfc_trip.planner.providers.searchapi import normalize_stay

    fixtures, routes = load_catalog()
    spec = SearchSpec(
        fixture=fixtures[0],
        route=routes[0],
        party=Party(),
        outbound_date=date(2026, 10, 14),
        return_date=date(2026, 10, 16),
        private_room=True,
        private_bathroom=True,
    )
    raw = json.loads(Path("tests/data/lyon-private-room.json").read_text())
    prop, details = raw["search"]["properties"][0], raw["details"]
    stay = normalize_stay(prop, details, raw["search"], spec, datetime.now(UTC))
    assert stay and stay.bathroom == "private" and stay.room_type == "private"
    # A bathroom count or property-level filter alone does not establish room privacy.
    prop["room_type"] = "Double Room"
    details["rooms"][0]["name"] = "Double Room"
    assert normalize_stay(prop, details, raw["search"], spec, datetime.now(UTC)) is None
