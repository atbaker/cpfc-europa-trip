"""Bounded SearchApi acquisition; raw JSON is discarded inside each Activity."""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
from datetime import UTC, date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import httpx
from pydantic import ValidationError

from cpfc_trip.config import Settings
from cpfc_trip.domain import (
    Evidence,
    Journey,
    Leg,
    Offer,
    Quote,
    SearchBatch,
    SearchSpec,
    Stay,
)
from cpfc_trip.origins import UK_RAIL
from cpfc_trip.planner.links import flight_url, hotel_url, safe_url
from cpfc_trip.planner.prices import money

ENDPOINT = "https://www.searchapi.io/api/v1/search"
REQUEST_CAPS = {"flight": 6, "rail": 8, "stay": 8}


class ProviderError(Exception):
    """A sanitized, user-safe provider failure (never includes credentials or raw URLs)."""


class NoResultsError(ProviderError):
    """The provider explicitly found no results for this search."""


def fingerprint(params: object) -> str:
    return hashlib.sha256(json.dumps(params, sort_keys=True, default=str).encode()).hexdigest()[:24]


class SearchApi:
    def __init__(self, client: httpx.AsyncClient, settings: Settings, limit: int = 8):
        self.client, self.settings, self.limit = client, settings, limit
        self.calls = 0
        self.deadline = asyncio.get_running_loop().time() + 80

    async def get(self, params: dict[str, Any]) -> dict[str, Any]:
        if (
            not self.settings.searchapi_enabled
            or not self.settings.searchapi_api_key.get_secret_value()
        ):
            raise ProviderError("Travel search is currently unavailable")
        for attempt in range(2):
            remaining = self.deadline - asyncio.get_running_loop().time()
            if self.calls >= self.limit or remaining <= 0:
                raise ProviderError("Search request limit or deadline reached")
            self.calls += 1
            try:
                response = await self.client.get(
                    ENDPOINT,
                    params=params,
                    headers={
                        "Authorization": f"Bearer {self.settings.searchapi_api_key.get_secret_value()}"
                    },
                    timeout=min(20, remaining),
                )
                response.raise_for_status()
                if len(response.content) > 4_000_000:
                    raise ProviderError("Travel search response exceeded its size limit")
                data = response.json()
                if (
                    isinstance(data, dict)
                    and data.get("error") == "Google Flights didn't return any results."
                ):
                    raise NoResultsError("No flights found")
                if not isinstance(data, dict) or data.get("error") or data.get("errors"):
                    raise ProviderError("Travel search returned an error")
                return data
            except (httpx.HTTPError, ValueError) as exc:
                # Engine/status only: never log request URLs, headers, bodies or secrets.
                logging.getLogger("cpfc_trip.provider").warning(
                    "SearchApi request failed: engine=%s error=%s status=%s",
                    params.get("engine"),
                    type(exc).__name__,
                    exc.response.status_code if isinstance(exc, httpx.HTTPStatusError) else None,
                )
                retryable = isinstance(exc, httpx.TransportError) or (
                    isinstance(exc, httpx.HTTPStatusError)
                    and (exc.response.status_code == 429 or exc.response.status_code >= 500)
                )
                if not retryable or attempt or self.calls >= self.limit:
                    raise ProviderError("Travel search did not return usable results") from None
                await asyncio.sleep(
                    min(0.25, max(0, self.deadline - asyncio.get_running_loop().time()))
                )
        raise ProviderError("Travel search did not return usable results")


def evidence(data: dict[str, Any], source: str, checked: datetime) -> Evidence:
    metadata = data.get("search_metadata", {})
    value = metadata.get("request_url", "")
    return Evidence(
        underlying_source=source,
        retrieved_at=checked,
        source_url=safe_url(value) if value else None,
    )


def offer(
    data: dict[str, Any],
    source: str,
    params: object,
    checked: datetime,
    url: str | None,
    seller: str | None = None,
    key: str = "",
) -> Offer:
    fid = fingerprint(params)
    return Offer(
        id=f"{fid}-{key}",
        booking_url=url,
        seller=seller,
        evidence=evidence(data, source, checked),
        search_fingerprint=fid,
    )


def local_time(point: dict[str, Any], timezone: str) -> datetime:
    return datetime.fromisoformat(f"{point['date']}T{point['time']}").replace(
        tzinfo=ZoneInfo(timezone)
    )


def normalize_flights(data: dict[str, Any], spec: SearchSpec, checked: datetime) -> SearchBatch:
    selected = data.get("selected_flights", [])
    if len(selected) != 2:
        return SearchBatch(gaps=("Complete outbound and return flights were not available.",))
    params = data.get("search_parameters", {})
    if params.get("outbound_date") != str(spec.outbound_date) or params.get("return_date") != str(
        spec.return_date
    ):
        return SearchBatch(gaps=("Returned flight dates did not match the requested dates.",))
    url = flight_url(data.get("search_metadata", {}).get("request_url", ""))
    ref = offer(data, "Google Flights", params, checked, url, "Google Flights")
    options = data.get("booking_options", [])
    value = options[0] if options else {}
    amount = money(value.get("price"), params.get("currency", ""))
    matched = (
        str(params.get("adults")) == str(spec.party.adults)
        and int(params.get("children", 0)) == len(spec.party.child_ages)
        and not any(a < 2 for a in spec.party.child_ages)
    )
    quote = (
        Quote(
            id=ref.id,
            amount=amount,
            scope="round_trip",
            unit="party",
            priced_party=spec.party if matched else None,
            observed_at=checked,
            caveats=("Rounded planning price; baggage and optional charges may be extra.",),
        )
        if amount
        else None
    )
    legs: list[tuple[Leg, ...]] = []
    for index, direction in enumerate(selected):
        flights = direction.get("flights", [])
        # Intermediate airport timezones need an airport catalog. Until reviewed, refuse connections.
        if len(flights) != 1:
            return SearchBatch(
                gaps=("Connecting-flight airport timezones require further evidence.",)
            )
        flight = flights[0]
        dep, arr = flight["departure_airport"], flight["arrival_airport"]
        london = spec.route.origin.split(",")
        if index == 0:
            valid = dep["id"] in london and arr["id"] == spec.route.destination
            dep_tz, arr_tz = "Europe/London", spec.route.destination_timezone
        else:
            valid = dep["id"] == spec.route.destination and arr["id"] in london
            dep_tz, arr_tz = spec.route.destination_timezone, "Europe/London"
        if not valid or dep.get("date") != str(
            spec.outbound_date if index == 0 else spec.return_date
        ):
            return SearchBatch(gaps=("Returned airports did not match the catalog route.",))
        legs.append(
            (
                Leg(
                    id=f"{ref.id}-{index}",
                    mode="flight",
                    origin=dep["id"],
                    destination=arr["id"],
                    departs_at=local_time(dep, dep_tz),
                    arrives_at=local_time(arr, arr_tz),
                    operator=flight["airline"],
                    service_number=flight.get("flight_number", ""),
                    offer=ref,
                    quote=quote,
                    caveats=("Select and confirm this itinerary on Google Flights.",),
                ),
            )
        )
    return SearchBatch(
        journeys=(Journey(id=ref.id, route_id=spec.route.id, outbound=legs[0], inbound=legs[1]),)
    )


async def search_flights(api: SearchApi, spec: SearchSpec) -> SearchBatch:
    if any(a < 2 for a in spec.party.child_ages):
        return SearchBatch(gaps=("Infant flight pricing is not yet supported.",))
    p = dict(
        engine="google_flights",
        departure_id=spec.route.origin,
        arrival_id=spec.route.destination,
        outbound_date=str(spec.outbound_date),
        return_date=str(spec.return_date),
        flight_type="round_trip",
        stops="nonstop",
        adults=spec.party.adults,
        children=len(spec.party.child_ages),
        currency="GBP",
        gl="GB",
        hl="en",
    )
    try:
        initial = await api.get(p)
    except NoResultsError:
        return SearchBatch(
            calls=api.calls,
            gaps=("No nonstop flights were found for this route and date pair.",),
        )
    choices = initial.get("best_flights", []) + initial.get("other_flights", [])
    journeys: list[Journey] = []
    for item in choices[:1]:
        if not item.get("departure_token"):
            continue
        try:
            returns = await api.get({**p, "departure_token": item["departure_token"]})
            back = returns.get("best_flights", []) + returns.get("other_flights", [])
            if not back:
                back = returns.get("flights", [])
            token = next((x.get("booking_token") for x in back if x.get("booking_token")), None)
            if not token:
                continue
            selected = await api.get({**p, "booking_token": token})
            result = normalize_flights(selected, spec, datetime.now(UTC))
            journeys.extend(result.journeys)
        except (ProviderError, KeyError, ValueError):
            # Preserve earlier complete flight offers when another choice fails.
            continue
    return SearchBatch(
        journeys=tuple(journeys),
        calls=api.calls,
        gaps=() if journeys else ("No complete flight result was verified.",),
    )


def normalize_stay(
    prop: dict[str, Any],
    details: dict[str, Any],
    search: dict[str, Any],
    spec: SearchSpec,
    checked: datetime,
) -> Stay | None:
    for response in (search, details):
        parameters = response.get("search_parameters", {})
        if parameters.get("check_in_date") != str(spec.outbound_date) or parameters.get(
            "check_out_date"
        ) != str(spec.return_date):
            return None
        if (
            parameters.get("adults") != spec.party.adults
            or parameters.get("rooms") != spec.party.rooms
        ):
            return None
    if prop.get("city", "").casefold() != spec.fixture.city.casefold():
        return None
    name = prop.get("room_type", "")
    room = next((x for x in details.get("rooms", []) if x.get("name") == name), None)
    if room is None:
        return None
    url = hotel_url(
        prop.get("link", ""), str(spec.outbound_date), str(spec.return_date), spec.party
    )
    if not url:
        return None
    ref = offer(
        search,
        "Booking.com",
        spec.model_dump(mode="json"),
        checked,
        url,
        "Booking.com",
        str(prop.get("property_id", "")),
    )
    summary = prop.get("stay_summary", "")
    nights = (spec.return_date - spec.outbound_date).days
    # Only the tested adult/one-room shape establishes group scope. Others remain observations.
    verified = (
        not spec.party.child_ages
        and spec.party.rooms == 1
        and summary
        == f"{nights} {'night' if nights == 1 else 'nights'}, {spec.party.adults} {'adult' if spec.party.adults == 1 else 'adults'}"
    )
    amount = money(prop.get("extracted_price"), prop.get("currency", ""))
    taxes = money(prop.get("extracted_taxes_and_charges"), prop.get("currency", ""))
    quote = (
        Quote(
            id=ref.id,
            amount=amount,
            scope="stay",
            unit="party" if verified else "unknown",
            priced_party=spec.party if verified else None,
            observed_at=checked,
            taxes="excluded" if taxes else "unknown",
            additional_taxes=taxes,
            caveats=("Search price is rounded. Confirm exact total and cancellation terms.",),
        )
        if amount
        else None
    )
    is_dorm = "dorm" in name.lower() or "bed in" in name.lower()
    room_facts = json.dumps(room.get("amenities", []), ensure_ascii=False).lower()
    bathroom = (
        "private"
        if "private bathroom" in name.lower() or "private bathroom" in room_facts
        else "shared"
        if "shared bathroom" in name.lower() or "shared bathroom" in room_facts
        else "unknown"
    )
    if spec.private_room and is_dorm or spec.private_bathroom and bathroom != "private":
        return None
    return Stay(
        id=ref.id,
        property_name=prop["title"],
        check_in=spec.outbound_date,
        check_out=spec.return_date,
        room_description=name,
        offer=ref,
        quote=quote,
        bathroom=bathroom,
        room_type="dorm" if is_dorm else "private",
        # Dorm metadata describes one bed's capacity, not the requested party's allocation.
        # The dated search summary establishes party price; bed allocation needs reconfirmation.
        max_guests=None if is_dorm else room.get("max_guests"),
        review_score=prop.get("rating"),
        caveats=(
            "Property and room must be reselected on Booking.com.",
            "Venue access, late check-in and post-match transfers need confirmation.",
        )
        + (("Confirm the number and allocation of dorm beds for your party.",) if is_dorm else ()),
    )


async def search_stays(api: SearchApi, spec: SearchSpec) -> SearchBatch:
    p: dict[str, Any] = dict(
        engine="booking",
        q=spec.fixture.city,
        check_in_date=str(spec.outbound_date),
        check_out_date=str(spec.return_date),
        adults=spec.party.adults,
        rooms=spec.party.rooms,
        currency="GBP",
        language="en-gb",
        sort_by="price_low_to_high",
    )
    if spec.party.child_ages:
        # Engine-specific child parameter contract must be proven before quoting children.
        return SearchBatch(
            gaps=("Accommodation prices for children need a direct occupancy check.",)
        )
    search = await api.get(p)
    if spec.private_bathroom:
        token = next(
            (
                o.get("value")
                for group in search.get("filters", [])
                for o in group.get("options", [])
                if o.get("name", "").casefold() == "private bathroom"
            ),
            None,
        )
        if token:
            p["filters"] = token
            search = await api.get(p)
    stays = []
    properties = [
        prop
        for prop in search.get("properties", [])[:40]
        if prop.get("city", "").casefold() == spec.fixture.city.casefold()
        and not (
            spec.private_room
            and any(x in prop.get("room_type", "").lower() for x in ("dorm", "bed in"))
        )
    ]

    def property_rank(prop: dict[str, Any]) -> float:
        price = prop.get("extracted_price")
        cost = float(price) if isinstance(price, (float, int)) else 10000
        dorm = any(x in prop.get("room_type", "").lower() for x in ("dorm", "bed in"))
        rating = prop.get("rating") or 5
        penalty = (150 if dorm else 0) + (10 - float(rating)) * 25
        return cost + penalty * (
            0 if spec.budget_tier == "budget" else 1 if spec.budget_tier == "value" else 4
        )

    properties.sort(key=property_rank)
    for prop in properties[:2]:
        url = hotel_url(
            prop.get("link", ""), str(spec.outbound_date), str(spec.return_date), spec.party
        )
        if not url:
            continue
        try:
            details = await api.get(
                {
                    k: v
                    for k, v in {**p, "engine": "booking_property", "url": url}.items()
                    if k not in {"q", "sort_by"}
                }
            )
            item = normalize_stay(prop, details, search, spec, datetime.now(UTC))
            if item:
                stays.append(item)
        except (ProviderError, KeyError, ValueError):
            # One unavailable property must not erase already checked rooms.
            continue
    return SearchBatch(
        stays=tuple(stays),
        calls=api.calls,
        gaps=() if stays else ("No dated room with verified identity was found.",),
    )


def normalize_trains(
    data: dict[str, Any], origin: str, destination: str, day: str, checked: datetime
) -> tuple[Leg, ...]:
    block = data.get("train_results") or {}
    if (
        block.get("date") != day
        or block.get("origin") != origin
        or block.get("destination") != destination
    ):
        return ()
    legs = []
    for train in block.get("trains", [])[:48]:
        window = train.get("time_window", {})
        instructions = train.get("instructions", [])
        if train.get("transfers") != 0 or len(instructions) != 1:
            continue
        instruction = instructions[0]
        stations = {
            ("London", "Paris"): ("St Pancras International", "Gare du Nord"),
            ("Paris", "London"): ("Gare du Nord", "St Pancras International"),
            ("Paris", "Lyon"): ("Gare de Lyon", "Lyon Part Dieu"),
            ("Lyon", "Paris"): ("Lyon Part Dieu", "Gare de Lyon"),
        }.get((origin, destination))
        for provider_city, departure_station, london_station in UK_RAIL.values():
            if (origin, destination) == (provider_city, "London"):
                stations = (departure_station, london_station)
            elif (origin, destination) == ("London", provider_city):
                stations = (london_station, departure_station)
        if (
            not stations
            or (
                instruction.get("depart_from", {}).get("place"),
                instruction.get("arrive_at", {}).get("place"),
            )
            != stations
        ):
            continue
        offers = train.get("buy_ticket", {}).get("offers", [])
        selected = next((x for x in offers if safe_url(x.get("link", ""))), None)
        if not selected:
            continue
        try:
            dep = datetime.fromisoformat(window["depart_at_iso"])
            arr = datetime.fromisoformat(window["arrive_at_iso"])
            if dep.date().isoformat() != day or dep.tzinfo is None or arr.tzinfo is None:
                continue
            if (
                datetime.fromisoformat(instruction["depart_from"]["at_iso"]) != dep
                or datetime.fromisoformat(instruction["arrive_at"]["at_iso"]) != arr
            ):
                continue
            ref = offer(
                data,
                "Google train results",
                (origin, destination, day, str(dep)),
                checked,
                safe_url(selected["link"]),
                selected.get("source"),
            )
            amount = money(selected.get("extracted_price"), selected.get("currency", ""))
            quote = (
                Quote(
                    id=ref.id,
                    amount=amount,
                    scope="leg",
                    unit="person",
                    priced_party=None,
                    observed_at=checked,
                    caveats=(
                        "Single-person indicative fare; party, railcards and payable currency unverified.",
                    ),
                )
                if amount
                else None
            )
            legs.append(
                Leg(
                    id=ref.id,
                    mode="rail",
                    origin=stations[0],
                    destination=stations[1],
                    departs_at=dep,
                    arrives_at=arr,
                    operator=instruction.get("service_provider", {}).get("name", "Rail"),
                    service_number=instruction.get("line_number", ""),
                    offer=ref,
                    quote=quote,
                    caveats=(
                        "Direct service with station and time evidence. Confirm the selected fare and passengers.",
                    ),
                )
            )
        except (KeyError, ValueError, ValidationError):
            continue
    return tuple(legs)


def connect_rail(
    first: tuple[Leg, ...], second: tuple[Leg, ...], minutes: int
) -> list[tuple[Leg, Leg]]:
    pairs = [
        (a, b)
        for a in first
        for b in second
        if (a.destination, b.origin)
        in {("Gare du Nord", "Gare de Lyon"), ("Gare de Lyon", "Gare du Nord")}
        and a.arrives_at.date() == b.departs_at.date()
        and timedelta(minutes=minutes) <= b.departs_at - a.arrives_at <= timedelta(hours=5)
        and 7 <= a.arrives_at.astimezone(ZoneInfo("Europe/Paris")).hour < 21
        and b.departs_at.astimezone(ZoneInfo("Europe/Paris")).hour <= 21
    ]
    pairs.sort(key=lambda pair: (pair[-1].arrives_at - pair[0].departs_at, pair[0].departs_at))
    return pairs[:8]


def london_connection(first: Leg, second: Leg, minutes: int) -> bool:
    """Require a same-day, buffered transfer between a UK terminal and Eurostar."""
    terminals = {station for _, _, station in UK_RAIL.values()}
    return (
        (
            (first.destination in terminals and second.origin == "St Pancras International")
            or (first.destination == "St Pancras International" and second.origin in terminals)
        )
        and first.arrives_at.date() == second.departs_at.date()
        and timedelta(minutes=minutes) <= second.departs_at - first.arrives_at <= timedelta(hours=8)
    )


async def search_trains(api: SearchApi, spec: SearchSpec) -> SearchBatch:
    if spec.route.id != "london-paris-lyon" and spec.route.origin not in UK_RAIL:
        return SearchBatch(gaps=("This rail pattern has not passed station-transfer review.",))
    segments = [
        ("London", "Paris", spec.outbound_date),
        ("Paris", "Lyon", spec.outbound_date),
        ("Lyon", "Paris", spec.return_date),
        ("Paris", "London", spec.return_date),
    ]
    if spec.route.origin in UK_RAIL:
        provider_city = UK_RAIL[spec.route.origin][0]
        segments = [
            (provider_city, "London", spec.outbound_date),
            *segments,
            ("London", provider_city, spec.return_date),
        ]
    semaphore = asyncio.Semaphore(3)

    async def fetch(origin: str, destination: str, day: datetime | date) -> tuple[Leg, ...]:
        async with semaphore:
            data = await api.get(
                dict(
                    engine="google",
                    q=f"trains from {origin} to {destination} on {day:%d %B %Y}",
                    gl="uk",
                    hl="en",
                )
            )
        return normalize_trains(data, origin, destination, str(day), datetime.now(UTC))

    legs = await asyncio.gather(*(fetch(*segment) for segment in segments))
    if len(legs) == 4:
        outbound: list[tuple[Leg, ...]] = [
            tuple(pair)
            for pair in connect_rail(legs[0], legs[1], spec.route.minimum_transfer_minutes)
        ]
        inbound: list[tuple[Leg, ...]] = [
            tuple(pair)
            for pair in connect_rail(legs[2], legs[3], spec.route.minimum_transfer_minutes)
        ]
    else:
        paris_out = connect_rail(legs[1], legs[2], spec.route.minimum_transfer_minutes)
        paris_in = connect_rail(legs[3], legs[4], spec.route.minimum_transfer_minutes)
        outbound = list[tuple[Leg, ...]](
            (domestic, *pair)
            for domestic in legs[0]
            for pair in paris_out
            if london_connection(domestic, pair[0], spec.route.minimum_transfer_minutes)
        )[:8]
        inbound = list[tuple[Leg, ...]](
            (*pair, domestic)
            for pair in paris_in
            for domestic in legs[5]
            if london_connection(pair[-1], domestic, spec.route.minimum_transfer_minutes)
        )[:8]
    combinations = [(a, b) for a in outbound for b in inbound]
    combinations.sort(
        key=lambda pair: sum((x[-1].arrives_at - x[0].departs_at).total_seconds() for x in pair)
    )
    journeys = tuple(
        Journey(
            id=fingerprint(tuple(x.id for x in (*a, *b))),
            route_id=spec.route.id,
            outbound=a,
            inbound=b,
        )
        for a, b in combinations[:12]
    )
    return SearchBatch(
        journeys=journeys,
        calls=api.calls,
        gaps=()
        if journeys
        else ("No dated rail connection meets the reviewed London and Paris transfer buffers.",),
    )


async def acquire(spec: SearchSpec, mode: str) -> SearchBatch:
    if not spec.route.enabled:
        return SearchBatch(gaps=("This catalog pattern has not passed its evidence review.",))
    async with httpx.AsyncClient(follow_redirects=False) as client:
        api = SearchApi(client, Settings(), limit=REQUEST_CAPS[mode])
        try:
            async with asyncio.timeout(80):
                if mode == "stay":
                    return await search_stays(api, spec)
                if mode == "flight":
                    return await search_flights(api, spec)
                return await search_trains(api, spec)
        except (ProviderError, KeyError, ValueError, TimeoutError):
            return SearchBatch(
                gaps=("Travel evidence is currently incomplete; please check the provider.",),
                calls=api.calls,
            )
