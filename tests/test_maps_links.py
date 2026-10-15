"""Google Maps links are handoffs to fresh directions, not stored schedules."""

from urllib.parse import parse_qs, urlparse

from cpfc_trip.planner.links import flight_url, safe_url
from cpfc_trip.planner.maps_links import transfer_links
from cpfc_trip.planner.planning import enumerate_specs
from cpfc_trip.planner.recorded import sample


def test_transfer_links_use_city_centre_and_actual_journey_stops(session_input) -> None:
    """The selected airport and hotel should appear in editable transit directions."""
    spec = enumerate_specs(session_input.brief, session_input.fixtures, session_input.routes)[0]
    journey = sample(spec, "flight").journeys[0]
    stay = sample(spec, "stay").stays[0]

    links = transfer_links("Manchester", journey, stay, spec.fixture)

    assert len(links) == 2
    first = urlparse(links[0].url)
    assert safe_url(links[0].url) == links[0].url
    assert flight_url(links[0].url) is None
    assert first.netloc == "www.google.com" and first.path == "/maps/dir/"
    assert parse_qs(first.query) == {
        "api": ["1"],
        "origin": ["Manchester city centre, UK"],
        "destination": [journey.outbound[0].origin + " Airport"],
        "travelmode": ["transit"],
    }
    second = parse_qs(urlparse(links[1].url).query)
    assert second["origin"] == [journey.outbound[-1].destination + " Airport"]
    assert second["destination"] == [f"{stay.property_name}, {spec.fixture.city}"]
