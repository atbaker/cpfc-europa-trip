"""Reviewed fixture catalog loader."""

from __future__ import annotations

import json
from functools import lru_cache
from importlib.resources import files

from pydantic import TypeAdapter

from cpfc_trip.domain import FixtureSnapshot

_FIXTURE_LIST = TypeAdapter(tuple[FixtureSnapshot, ...])


@lru_cache
def all_fixtures() -> tuple[FixtureSnapshot, ...]:
    path = files("cpfc_trip.data").joinpath("fixtures.json")
    return _FIXTURE_LIST.validate_python(json.loads(path.read_text(encoding="utf-8")))


def fixtures_by_id(fixture_ids: tuple[str, ...]) -> tuple[FixtureSnapshot, ...]:
    catalog = {fixture.id: fixture for fixture in all_fixtures()}
    unknown = sorted(set(fixture_ids) - catalog.keys())
    if unknown:
        raise ValueError(f"unknown fixture IDs: {', '.join(unknown)}")
    return tuple(catalog[fixture_id] for fixture_id in fixture_ids)
