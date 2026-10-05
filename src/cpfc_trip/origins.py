"""Reviewed UK departure cities, airports and direct London rail gateways."""

from datetime import UTC, datetime

from cpfc_trip.domain import Route, TransferGuidance

# Explicit airport coverage keeps a typed city from silently becoming a different airport.
UK_ORIGINS: dict[str, tuple[str, ...]] = {
    "Aberdeen": ("ABZ",),
    "Belfast": ("BFS", "BHD"),
    "Birmingham": ("BHX",),
    "Bournemouth": ("BOH",),
    "Bristol": ("BRS",),
    "Cardiff": ("CWL",),
    "Edinburgh": ("EDI",),
    "Exeter": ("EXT",),
    "Glasgow": ("GLA",),
    "Inverness": ("INV",),
    "Leeds": ("LBA",),
    "Liverpool": ("LPL",),
    "London": ("LHR", "LGW", "STN", "LTN"),
    "Manchester": ("MAN",),
    "Newcastle": ("NCL",),
    "Norwich": ("NWI",),
    "Nottingham": ("EMA",),
    "Southampton": ("SOU",),
}

# Provider city, UK departure station, London arrival station. These direct station
# pairs were checked against dated SearchApi train results on 5 October 2026.
UK_RAIL: dict[str, tuple[str, str, str]] = {
    "Birmingham": ("Birmingham", "Birmingham New Street", "Euston"),
    "Bristol": ("Bristol", "Bristol Temple Meads", "Paddington"),
    "Cardiff": ("Cardiff", "Cardiff Central", "Paddington"),
    "Edinburgh": ("Edinburgh", "Edinburgh Waverley", "King’s Cross"),
    "Leeds": ("Leeds", "Leeds", "King’s Cross"),
    "Liverpool": ("Liverpool", "Liverpool Lime Street", "Euston"),
    "Manchester": ("Manchester", "Manchester Piccadilly", "Euston"),
    "Newcastle": ("Newcastle upon Tyne", "Newcastle", "King’s Cross"),
}

LONDON_TRANSFER = TransferGuidance(
    title="Changing stations in London",
    description=(
        "The UK train arrives at a London terminal. Transfer to St Pancras International "
        "separately; the planner allows at least three hours before Eurostar. Confirm local "
        "transport, the Eurostar check-in time and any disruption. Separate tickets may not "
        "protect a missed connection; London transfer fares are not included."
    ),
    source_url="https://www.eurostar.com/uk-en/travel-info/your-trip/check-in",
    reviewed_at=datetime(2026, 10, 5, tzinfo=UTC),
)


def canonical_origin(city: str) -> str:
    """Return a supported UK city name, ignoring case and surrounding whitespace."""
    name = next((name for name in UK_ORIGINS if name.casefold() == city.strip().casefold()), None)
    if name is None:
        raise ValueError("Choose a supported UK departure city from the suggestions")
    return name


def airports_for(city: str) -> tuple[str, ...]:
    """Return the airports that this planner searches for a supported city."""
    return UK_ORIGINS[canonical_origin(city)]


def routes_for_origin(routes: tuple[Route, ...], city: str) -> tuple[Route, ...]:
    """Freeze selected city's reviewed air and rail gateways into route templates."""
    name = canonical_origin(city)
    if name == "London":
        return routes
    airports = ",".join(airports_for(name))
    slug = name.lower().replace(" ", "-")
    selected = []
    for route in routes:
        if route.mode == "flight":
            selected.append(
                route.model_copy(update={"id": f"{slug}-{route.id}", "origin": airports})
            )
        elif route.mode == "rail" and name in UK_RAIL:
            selected.append(
                route.model_copy(
                    update={
                        "id": f"{slug}-{route.id}",
                        "origin": name,
                        "onward_stations": ("London", *route.onward_stations),
                        # The reviewed Edinburgh connection reaches Lyon after 23:00.
                        "gateway_arrival_hours": (6, 24)
                        if name == "Edinburgh"
                        else route.gateway_arrival_hours,
                        "guidance": (LONDON_TRANSFER, *route.guidance),
                        "transfer_note": (
                            route.transfer_note
                            + " Edinburgh rail can arrive late; confirm hotel check-in before booking."
                            if name == "Edinburgh"
                            else route.transfer_note
                        ),
                        "source_urls": (*route.source_urls, LONDON_TRANSFER.source_url),
                    }
                )
            )
    return tuple(selected)
