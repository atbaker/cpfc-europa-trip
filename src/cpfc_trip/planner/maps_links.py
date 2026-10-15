"""Fresh Google Maps handoffs for unpriced local travel."""

from urllib.parse import urlencode

from cpfc_trip.domain import Fixture, Journey, MapsTransfer, Stay


def _stop(name: str, flight: bool) -> str:
    return f"{name} Airport" if flight and len(name) == 3 and name.isalpha() else name


def _directions(origin: str, destination: str) -> str:
    return "https://www.google.com/maps/dir/?" + urlencode(
        {"api": "1", "origin": origin, "destination": destination, "travelmode": "transit"}
    )


def transfer_links(
    origin_city: str, journey: Journey, stay: Stay, fixture: Fixture
) -> tuple[MapsTransfer, MapsTransfer]:
    """Link central-city access and destination arrival to fresh Maps directions."""
    first = journey.outbound[0]
    arrival = journey.outbound[-1]
    departure_point = _stop(first.origin, first.mode == "flight")
    arrival_point = _stop(arrival.destination, arrival.mode == "flight")
    return (
        MapsTransfer(
            title=f"{origin_city} centre to departure point",
            description=(
                f"Start from {origin_city} city centre and check travel to {departure_point}. "
                "Change the starting point in Google Maps if needed. Time, changes and fares are not included."
            ),
            url=_directions(f"{origin_city} city centre, UK", departure_point),
        ),
        MapsTransfer(
            title=f"Arrival point to your stay in {fixture.city}",
            description=(
                f"Check local travel from {arrival_point} to {stay.property_name}. "
                "Time, changes and fares are not included."
            ),
            url=_directions(arrival_point, f"{stay.property_name}, {fixture.city}"),
        ),
    )
