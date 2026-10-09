import json
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest

from cpfc_trip.catalog import load_catalog
from cpfc_trip.config import Settings
from cpfc_trip.domain import Party, SearchSpec
from cpfc_trip.origins import routes_for_origin
from cpfc_trip.planner.links import flight_url, hotel_url, safe_url
from cpfc_trip.planner.prices import total
from cpfc_trip.planner.providers.searchapi import (
    ProviderError,
    SearchApi,
    connect_onward_rail,
    normalize_flights,
    normalize_stay,
    normalize_trains,
)
from cpfc_trip.planner.recorded import sample

CHECKED = datetime(2026, 9, 6, tzinfo=UTC)


def data(name):
    return json.loads((Path(__file__).parent / "data" / f"{name}.json").read_text())


def spec(session_input):
    return SearchSpec(
        fixture=session_input.fixtures[0],
        route=session_input.routes[0],
        party=Party(adults=2),
        outbound_date=date(2026, 10, 4),
        return_date=date(2026, 10, 6),
    )


def test_flight_round_trip_counted_once(session_input):
    s = spec(session_input)
    result = normalize_flights(data("flight-booking"), s, CHECKED)
    j = result.journeys[0]
    assert j.outbound[0].origin == "LGW" and j.inbound[0].destination == "LGW"
    assert j.outbound[0].service_number == "U2 8429"
    assert j.inbound[0].service_number == "U2 8430"
    price, _ = total([j.outbound[0].quote, j.inbound[0].quote], s.party)
    assert price.minor_units == 14800
    url = parse_qs(urlsplit(j.outbound[0].offer.booking_url).query)
    assert url["curr"] == ["GBP"] and url["gl"] == ["GB"] and url["tfs"]


def test_selected_city_airports_gate_returned_flights(session_input):
    route = routes_for_origin(session_input.routes, "Manchester")[0]
    selected = spec(session_input).model_copy(update={"route": route})
    raw = data("flight-booking")
    assert not normalize_flights(raw, selected, CHECKED).journeys
    raw["selected_flights"][0]["flights"][0]["departure_airport"]["id"] = "MAN"
    raw["selected_flights"][1]["flights"][0]["arrival_airport"]["id"] = "MAN"
    result = normalize_flights(raw, selected, CHECKED)
    assert result.journeys[0].outbound[0].origin == "MAN"
    assert result.journeys[0].inbound[0].destination == "MAN"


def connecting_booking():
    raw = data("flight-booking")
    outward, home = raw["selected_flights"]
    outward["flights"] = [
        {
            **outward["flights"][0],
            "departure_airport": {"id": "LGW", "date": "2026-10-04", "time": "08:00"},
            "arrival_airport": {"id": "AMS", "date": "2026-10-04", "time": "10:15"},
            "duration": 75,
            "airline": "KLM",
            "flight_number": "KL 1001",
        },
        {
            **outward["flights"][0],
            "departure_airport": {"id": "AMS", "date": "2026-10-04", "time": "11:45"},
            "arrival_airport": {"id": "LYS", "date": "2026-10-04", "time": "13:15"},
            "duration": 90,
            "airline": "KLM",
            "flight_number": "KL 1002",
        },
    ]
    home["flights"] = [
        {
            **home["flights"][0],
            "departure_airport": {"id": "LYS", "date": "2026-10-06", "time": "10:00"},
            "arrival_airport": {"id": "AMS", "date": "2026-10-06", "time": "11:30"},
            "duration": 90,
            "airline": "KLM",
            "flight_number": "KL 1003",
        },
        {
            **home["flights"][0],
            "departure_airport": {"id": "AMS", "date": "2026-10-06", "time": "13:00"},
            "arrival_airport": {"id": "LGW", "date": "2026-10-06", "time": "13:15"},
            "duration": 75,
            "airline": "KLM",
            "flight_number": "KL 1004",
        },
    ]
    outward["layovers"] = home["layovers"] = [{"id": "AMS", "duration": 90}]
    return raw


def test_one_stop_round_trip_keeps_connection_and_one_price(session_input):
    chosen = spec(session_input)
    result = normalize_flights(connecting_booking(), chosen, CHECKED)
    journey = result.journeys[0]
    assert len(journey.outbound) == len(journey.inbound) == 1
    assert journey.outbound[0].origin == "LGW"
    assert journey.outbound[0].destination == "LYS"
    assert "AMS" in journey.outbound[0].caveats[0]
    assert "KL 1001" in journey.outbound[0].service_number
    assert "KL 1002" in journey.outbound[0].service_number
    assert (
        total([journey.outbound[0].quote, journey.inbound[0].quote], chosen.party)[0].minor_units
        == 14800
    )


@pytest.mark.parametrize("change", ["wrong_airport", "short_layover", "wrong_duration"])
def test_one_stop_requires_supported_connection_evidence(session_input, change):
    raw = connecting_booking()
    if change == "wrong_airport":
        raw["selected_flights"][0]["flights"][1]["departure_airport"]["id"] = "FRA"
    elif change == "short_layover":
        raw["selected_flights"][0]["flights"][1]["duration"] = 130
    else:
        raw["selected_flights"][0]["layovers"][0]["duration"] = 200
    assert not normalize_flights(raw, spec(session_input), CHECKED).journeys


def test_hotel_price_tax_and_exact_room_identity(session_input):
    search = data("hotels")
    s = spec(session_input)
    stay = normalize_stay(search["properties"][0], data("hotel-detail"), search, s, CHECKED)
    assert stay.room_description == "Twin Room"  # Never accidentally pick the first/triple room.
    assert stay.quote.amount.minor_units == 5900
    price, _ = total([stay.quote], s.party)
    assert price.minor_units == 6800  # £59 + £9; supplier checkout may differ by rounding.
    params = parse_qs(urlsplit(stay.offer.booking_url).query)
    assert params["group_adults"] == ["2"] and params["checkin"] == ["2026-10-04"]
    assert normalize_stay(search["properties"][1], data("hotel-detail"), search, s, CHECKED) is None


def test_hotel_rejects_changed_dates_and_keeps_dorm_party_scope(session_input):
    search, details, s = data("hotels"), data("hotel-detail"), spec(session_input)
    details["search_parameters"]["check_out_date"] = "2026-10-07"
    assert normalize_stay(search["properties"][0], details, search, s, CHECKED) is None
    details = data("hotel-detail")
    details["search_parameters"]["adults"] = 1
    assert normalize_stay(search["properties"][0], details, search, s, CHECKED) is None
    details = data("hotel-detail")
    name = "Bed in Mixed Dormitory Room"
    search["properties"][0]["room_type"] = name
    details["rooms"][1].update(name=name, max_guests=1)
    stay = normalize_stay(search["properties"][0], details, search, s, CHECKED)
    assert stay.room_type == "dorm" and stay.max_guests is None
    assert stay.quote.priced_party == s.party


def test_rail_date_party_currency_are_not_guessed():
    raw = data("trains")
    legs = normalize_trains(raw, "London", "Paris", "2026-10-04", CHECKED)
    assert len(legs) == 1 and legs[0].quote.amount.minor_units == 5800
    assert legs[0].departs_at.utcoffset().total_seconds() == 3600
    assert legs[0].arrives_at.utcoffset().total_seconds() == 7200
    assert total([legs[0].quote], Party(adults=2))[0] is None
    assert not normalize_trains(raw, "London", "Paris", "2026-10-05", CHECKED)
    assert not normalize_trains(raw, "Paris", "London", "2026-10-04", CHECKED)


def test_warsaw_onward_rail_needs_reviewed_stations_and_airport_transfer(session_input):
    fixtures, routes = load_catalog()
    route = next(route for route in routes if route.id == "london-waw")
    fixture = next(fixture for fixture in fixtures if fixture.id == route.fixture_id)
    chosen = spec(session_input).model_copy(
        update={
            "fixture": fixture,
            "route": route,
            "outbound_date": date(2026, 12, 9),
            "return_date": date(2026, 12, 11),
        }
    )
    flight = sample(chosen, "flight").journeys[0]

    def train(origin, destination, day, departure, arrival, start_station, end_station):
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
                                "depart_from": {"place": start_station, "at_iso": departure},
                                "arrive_at": {"place": end_station, "at_iso": arrival},
                                "service_provider": {
                                    "name": "PKP Intercity",
                                    "website": "https://www.intercity.pl/pl/",
                                },
                            }
                        ],
                    }
                ],
            }
        }

    outward = normalize_trains(
        train(
            "Warsaw",
            "Białystok",
            "2026-12-09",
            "2026-12-09T15:00:00+01:00",
            "2026-12-09T17:30:00+01:00",
            "Warsaw Central",
            "Zielone Wzgórza",
        ),
        "Warsaw",
        "Białystok",
        "2026-12-09",
        CHECKED,
    )
    inbound = normalize_trains(
        train(
            "Białystok",
            "Warsaw",
            "2026-12-11",
            "2026-12-11T07:00:00+01:00",
            "2026-12-11T10:00:00+01:00",
            "Zielone Wzgórza",
            "Warsaw Central",
        ),
        "Białystok",
        "Warsaw",
        "2026-12-11",
        CHECKED,
    )
    assert outward and inbound
    assert outward[0].quote is None and inbound[0].quote is None
    assert "fare unavailable" in outward[0].caveats[0]
    joined = connect_onward_rail(flight, outward, inbound, chosen.route.minimum_transfer_minutes)
    assert joined and joined[0].outbound[-1].destination == "Zielone Wzgórza"
    assert len(joined[0].outbound) == len(joined[0].inbound) == 2
    too_close = outward[0].model_copy(
        update={"departs_at": flight.outbound[-1].arrives_at + timedelta(hours=1)}
    )
    assert not connect_onward_rail(
        flight, (too_close,), inbound, chosen.route.minimum_transfer_minutes
    )


@pytest.mark.parametrize(
    "url",
    [
        "javascript:alert(1)",
        "https://www.google.com.evil.test/travel/flights",
        "https://www.booking.com@evil.test/",
        "http://www.booking.com/",
        "https://127.0.0.1",
        "https://www.google.com/travel/clk/f",
        "https://www.booking.com:444/",
    ],
)
def test_unsafe_links_rejected(url):
    assert safe_url(url) is None


def test_locale_preserves_opaque_tokens_and_child_occupancy():
    result = flight_url(
        "https://www.google.com/travel/flights/search?tfs=a%2Bb%3D&tfu=x&gl=US&curr=USD"
    )
    params = parse_qs(urlsplit(result).query)
    assert params["tfs"] == ["a+b="] and params["tfu"] == ["x"] and params["curr"] == ["GBP"]
    link = hotel_url(
        "https://www.booking.com/hotel/fr/test.html?age=99&checkin=old",
        "2026-10-04",
        "2026-10-06",
        Party(adults=2, child_ages=(4, 8), rooms=2),
    )
    params = parse_qs(urlsplit(link).query)
    assert params["age"] == ["4", "8"] and params["no_rooms"] == ["2"]


async def test_provider_error_never_exposes_key(settings):
    settings.searchapi_api_key = (
        "test-secret"  # pydantic assignment not validated; construct correctly below
    )
    settings = settings.model_copy(
        update={"searchapi_api_key": __import__("pydantic").SecretStr("test-secret")}
    )
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(401, json={"error": "test-secret"})
        )
    ) as client:
        api = SearchApi(client, settings)
        with pytest.raises(ProviderError) as exc:
            await api.get({"engine": "google"})
        assert "test-secret" not in str(exc.value)
        assert api.calls == 1


async def test_no_nonstop_flights_has_specific_gap(session_input, settings):
    from pydantic import SecretStr

    from cpfc_trip.planner.providers.searchapi import search_flights

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                200, json={"error": "Google Flights didn't return any results."}
            )
        )
    ) as client:
        api = SearchApi(
            client,
            settings.model_copy(update={"searchapi_api_key": SecretStr("test-secret")}),
        )
        result = await search_flights(api, spec(session_input))
    assert result.calls == 2
    assert not result.journeys
    assert result.gaps == (
        "No nonstop or suitable one-stop flights were found for this route and date pair.",
    )


async def test_one_stop_search_only_after_nonstop_is_empty(session_input, settings):
    from pydantic import SecretStr

    from cpfc_trip.planner.providers.searchapi import search_flights

    calls: list[httpx.QueryParams] = []

    def respond(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.params)
        if len(calls) == 1:
            return httpx.Response(200, json={"error": "Google Flights didn't return any results."})
        if len(calls) == 2:
            return httpx.Response(200, json={"best_flights": [{"departure_token": "out"}]})
        if len(calls) == 3:
            return httpx.Response(200, json={"best_flights": [{"booking_token": "return"}]})
        return httpx.Response(200, json=connecting_booking())

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        api = SearchApi(
            client,
            settings.model_copy(update={"searchapi_api_key": SecretStr("test-secret")}),
        )
        result = await search_flights(api, spec(session_input))
    assert result.calls == 4
    assert len(result.journeys) == 1
    assert calls[0]["stops"] == "nonstop"
    assert all(call["stops"] == "one_stop_or_fewer" for call in calls[1:])


async def test_complete_nonstop_trip_does_not_request_connection_search(session_input, settings):
    from pydantic import SecretStr

    from cpfc_trip.planner.providers.searchapi import search_flights

    calls: list[httpx.QueryParams] = []

    def respond(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.params)
        if len(calls) == 1:
            return httpx.Response(200, json={"best_flights": [{"departure_token": "out"}]})
        if len(calls) == 2:
            return httpx.Response(200, json={"best_flights": [{"booking_token": "return"}]})
        return httpx.Response(200, json=data("flight-booking"))

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        api = SearchApi(
            client,
            settings.model_copy(update={"searchapi_api_key": SecretStr("test-secret")}),
        )
        result = await search_flights(api, spec(session_input))
    assert len(result.journeys) == 1
    assert result.calls == 3
    assert all(call["stops"] == "nonstop" for call in calls)


async def test_transient_retry_repeats_only_failed_request(settings: Settings) -> None:
    from pydantic import SecretStr

    from cpfc_trip.planner.providers.searchapi import SearchApi

    requests: list[httpx.QueryParams] = []

    def respond(request: httpx.Request) -> httpx.Response:
        requests.append(request.url.params)
        return httpx.Response(503 if len(requests) == 2 else 200, json={"results": []})

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        api = SearchApi(
            client,
            settings.model_copy(update={"searchapi_api_key": SecretStr("test-secret")}),
            limit=3,
        )
        assert await api.get({"engine": "google", "q": "discovery"}) == {"results": []}
        assert await api.get({"engine": "google", "q": "detail"}) == {"results": []}
        assert api.calls == 3
        assert requests[0] != requests[1] == requests[2]


async def test_permanent_failure_and_exhausted_budget_do_not_retry(settings: Settings) -> None:
    from pydantic import SecretStr

    from cpfc_trip.planner.providers.searchapi import ProviderError, SearchApi

    calls: list[httpx.Request] = []

    def reject(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(400)

    async with httpx.AsyncClient(transport=httpx.MockTransport(reject)) as client:
        api = SearchApi(
            client,
            settings.model_copy(update={"searchapi_api_key": SecretStr("test-secret")}),
            limit=2,
        )
        with pytest.raises(ProviderError):
            await api.get({"engine": "google"})
        assert api.calls == 1
        assert len(calls) == 1

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda request: httpx.Response(503))
    ) as client:
        api = SearchApi(
            client,
            settings.model_copy(update={"searchapi_api_key": SecretStr("test-secret")}),
            limit=1,
        )
        with pytest.raises(ProviderError):
            await api.get({"engine": "google"})
        assert api.calls == 1


async def test_later_property_failure_preserves_checked_rooms(session_input, settings):
    from cpfc_trip.planner.providers.searchapi import search_stays

    search = data("hotels")
    prop = search["properties"][0]
    search["properties"] = [prop, {**prop, "property_id": "another-property"}]
    responses = [
        httpx.Response(200, json=search),
        httpx.Response(200, json=data("hotel-detail")),
        httpx.Response(503),
        httpx.Response(503),
    ]
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda _: responses.pop(0))
    ) as client:
        from pydantic import SecretStr

        api = SearchApi(
            client, settings.model_copy(update={"searchapi_api_key": SecretStr("test-secret")})
        )
        batch = await search_stays(api, spec(session_input))
        assert len(batch.stays) == 1
        assert batch.stays[0].room_description == "Twin Room"
        assert batch.calls == 4
