"""Bounded live adapter check on the first fixture's dates; at most nine SearchApi calls."""

import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path

import httpx

from cpfc_trip.catalog import load_catalog, validate_brief
from cpfc_trip.config import Settings
from cpfc_trip.domain import Brief, Party
from cpfc_trip.planner.planning import enumerate_specs
from cpfc_trip.planner.providers.searchapi import SearchApi, search_flights, search_stays


async def main() -> None:
    fixtures, routes = load_catalog()
    brief = validate_brief(
        Brief(fixture_ids=(fixtures[0].id,), travellers=Party(adults=2)),
        fixtures,
        datetime.now(UTC),
    )
    spec = enumerate_specs(brief, (fixtures[0],), routes, recorded=True)[0]
    result = {"spec": spec.model_dump(mode="json")}
    async with httpx.AsyncClient() as client:
        for name, function, limit in [("flights", search_flights, 5), ("stays", search_stays, 4)]:
            api = SearchApi(client, Settings(), limit=limit)
            batch = await function(api, spec)
            result[name] = batch.model_dump(mode="json")
            print(
                f"{name}: {api.calls} calls; {len(batch.journeys)} journeys; {len(batch.stays)} stays; gaps={batch.gaps}",
                flush=True,
            )
    path = Path(".data/live-adapters.json")
    await asyncio.to_thread(path.write_text, json.dumps(result, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
