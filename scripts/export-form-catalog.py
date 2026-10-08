"""Export the reviewed live choices for the statically rendered trip form."""

import argparse
import json
from pathlib import Path

from cpfc_trip.catalog import load_catalog
from cpfc_trip.origins import UK_ORIGINS, UK_RAIL

OUTPUT = Path(__file__).resolve().parents[1] / "frontend/lib/form-catalog.json"


def render_catalog() -> str:
    """Render choices from the same fixtures and origins used by the API."""
    fixtures, routes = load_catalog()
    enabled_ids = {route.fixture_id for route in routes if route.enabled}
    data = {
        "fixtures": [
            fixture.model_dump(mode="json") for fixture in fixtures if fixture.id in enabled_ids
        ],
        "origin_cities": sorted(UK_ORIGINS),
        "rail_cities": ["London", *sorted(UK_RAIL)],
    }
    return json.dumps(data, ensure_ascii=False, indent=2) + "\n"


def main() -> None:
    """Write the bundled choices, or verify that they match the backend."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check", action="store_true", help="Fail if the committed catalog is stale"
    )
    args = parser.parse_args()
    content = render_catalog()
    if args.check:
        if not OUTPUT.exists() or OUTPUT.read_text() != content:
            raise SystemExit(
                "Form catalog is stale. Run: uv run python scripts/export-form-catalog.py"
            )
        return
    OUTPUT.write_text(content)


if __name__ == "__main__":
    main()
