import json
from datetime import UTC, date, datetime
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest

from cpfc_trip.config import Settings
from cpfc_trip.domain import Party, SearchSpec
from cpfc_trip.origins import routes_for_origin
from cpfc_trip.planner.links import flight_url, hotel_url, safe_url
from cpfc_trip.planner.prices import total
from cpfc_trip.planner.providers.searchapi import (
    ProviderError,
    SearchApi,
    normalize_flights,
    normalize_stay,
    normalize_trains,
)

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
    assert result.calls == 1
    assert not result.journeys
    assert result.gaps == ("No nonstop flights were found for this route and date pair.",)


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
