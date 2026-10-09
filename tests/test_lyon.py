import asyncio
import json
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

from cpfc_trip.domain import SearchSpec
from cpfc_trip.origins import routes_for_origin
from cpfc_trip.planner.agent import Intent
from cpfc_trip.planner.planning import enumerate_specs, feasible, rank
from cpfc_trip.planner.providers.searchapi import (
    connect_rail,
    london_connection,
    normalize_trains,
    search_trains,
)
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


async def test_manchester_rail_connects_to_reviewed_lyon_route(session_input):
    raw = await asyncio.to_thread(lambda: json.loads(Path("tests/data/lyon-rail.json").read_text()))

    def domestic(origin, destination, day, departure, arrival, from_station, to_station):
        return {
            "train_results": {
                "origin": origin,
                "destination": destination,
                "date": day,
                "trains": [
                    {
                        "transfers": 0,
                        "time_window": {"depart_at_iso": departure, "arrive_at_iso": arrival},
                        "instructions": [
                            {
                                "depart_from": {"place": from_station, "at_iso": departure},
                                "arrive_at": {"place": to_station, "at_iso": arrival},
                                "service_provider": {"name": "Example rail"},
                            }
                        ],
                        "buy_ticket": {
                            "offers": [
                                {
                                    "source": "Omio",
                                    "link": "https://www.omio.com/test",
                                    "extracted_price": 45,
                                    "currency": "GBP",
                                }
                            ]
                        },
                    }
                ],
            }
        }

    raw["Manchester-London"] = domestic(
        "Manchester",
        "London",
        "2026-10-14",
        "2026-10-14T05:00:00+01:00",
        "2026-10-14T07:20:00+01:00",
        "Manchester Piccadilly",
        "Euston",
    )
    raw["London-Manchester"] = domestic(
        "London",
        "Manchester",
        "2026-10-16",
        "2026-10-16T17:00:00+01:00",
        "2026-10-16T19:20:00+01:00",
        "Euston",
        "Manchester Piccadilly",
    )

    class FakeApi:
        calls = 0

        async def get(self, params):
            self.calls += 1
            query = params["q"]
            return next(
                result
                for key, result in raw.items()
                if query.startswith(f"trains from {key.replace('-', ' to ')} on")
            )

    route = next(
        r for r in routes_for_origin(session_input.routes, "Manchester") if r.mode == "rail"
    )
    spec = SearchSpec(
        fixture=session_input.fixtures[0],
        route=route,
        party=session_input.brief.travellers,
        outbound_date=date(2026, 10, 14),
        return_date=date(2026, 10, 16),
    )
    result = await search_trains(FakeApi(), spec)
    assert result.calls == 6
    assert result.journeys
    journey = result.journeys[0]
    assert len(journey.outbound) == len(journey.inbound) == 3
    assert journey.outbound[0].origin == "Manchester Piccadilly"
    assert journey.inbound[-1].destination == "Manchester Piccadilly"
    assert journey.outbound[0].quote.amount.minor_units == 4500
    tight = journey.outbound[0].model_copy(
        update={"arrives_at": journey.outbound[1].departs_at - timedelta(minutes=90)}
    )
    assert not london_connection(tight, journey.outbound[1], 180)
    raw["Manchester-London"]["train_results"]["trains"][0]["instructions"][0]["arrive_at"][
        "place"
    ] = "Waterloo"
    assert not normalize_trains(
        raw["Manchester-London"], "Manchester", "London", "2026-10-14", datetime.now(UTC)
    )


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
