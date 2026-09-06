from datetime import datetime
from zoneinfo import ZoneInfo

from cpfc_trip.fixtures import all_fixtures, fixtures_by_id


def test_catalog_has_four_unique_cpfc_away_fixtures() -> None:
    fixtures = all_fixtures()
    assert len(fixtures) == 4
    assert len({fixture.id for fixture in fixtures}) == 4
    assert all(fixture.away_team_id == "crystal-palace" for fixture in fixtures)


def test_kickoffs_convert_to_reviewed_local_times() -> None:
    expected = {
        "uel-2026-lyon-away": ("2026-10-15", "18:45"),
        "uel-2026-besiktas-away": ("2026-10-22", "22:00"),
        "uel-2026-jagiellonia-away": ("2026-12-10", "18:45"),
        "uel-2026-salzburg-away": ("2027-01-28", "21:00"),
    }
    for fixture in all_fixtures():
        local: datetime = fixture.kickoff_at.astimezone(ZoneInfo(fixture.venue.city.timezone))
        assert (local.strftime("%Y-%m-%d"), local.strftime("%H:%M")) == expected[fixture.id]


def test_fixture_lookup_preserves_requested_order() -> None:
    fixture_ids = ("uel-2026-salzburg-away", "uel-2026-lyon-away")
    assert tuple(fixture.id for fixture in fixtures_by_id(fixture_ids)) == fixture_ids
