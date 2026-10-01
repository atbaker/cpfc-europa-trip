# /// script
# requires-python = ">=3.13"
# dependencies = ["httpx==0.28.1", "pydantic==2.13.5", "pydantic-settings==2.15.0"]
# ///
"""Small, bounded SearchApi experiment. Dry-run unless --live is supplied."""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import httpx
from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[1]
ENDPOINT = "https://www.searchapi.io/api/v1/search"


class Credentials(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ROOT / ".env", env_prefix="SEARCHAPI_", extra="ignore"
    )
    api_key: SecretStr | None = None


def scenarios(start: date, nights: int, selected: str) -> list[tuple[str, dict[str, Any]]]:
    end = start + timedelta(days=nights)
    departure = datetime.combine(start, datetime.min.time(), ZoneInfo("Europe/Paris"))
    departure = departure.replace(hour=10)
    cases = [
        (
            "flights",
            {
                "engine": "google_flights",
                "departure_id": "LHR,LGW,STN,LTN",
                "arrival_id": "LYS",
                "flight_type": "round_trip",
                "outbound_date": str(start),
                "return_date": str(end),
                "adults": 2,
                "currency": "GBP",
                "gl": "uk",
                "hl": "en",
            },
        ),
        (
            "hotels",
            {
                "engine": "booking",
                "q": "Lyon, France",
                "check_in_date": str(start),
                "check_out_date": str(end),
                "adults": 2,
                "rooms": 1,
                "currency": "GBP",
                "language": "en-gb",
                "sort_by": "price_low_to_high",
            },
        ),
        (
            "trains-uk",
            {
                "engine": "google",
                "q": f"trains from London to Manchester on {start:%d %B %Y}",
                "gl": "uk",
                "hl": "en",
            },
        ),
        (
            "trains-cross-border",
            {
                "engine": "google",
                "q": f"trains from London to Paris on {start:%d %B %Y}",
                "gl": "uk",
                "hl": "en",
            },
        ),
        (
            "transit",
            {
                "engine": "google_maps_directions",
                "from": "Lyon Saint-Exupery Airport, France",
                "to": "Lyon Part-Dieu station, France",
                "travel_mode": "transit",
                "time": f"depart_at:{int(departure.timestamp())}",
                "gl": "fr",
                "hl": "en",
            },
        ),
    ]
    return [
        (name, params)
        for name, params in cases
        if selected == "all"
        or name == selected
        or (selected == "trains" and name.startswith("trains-"))
    ]


def redact(value: Any, secret: str) -> Any:
    """Remove credentials, including a key echoed inside an error or response URL."""
    if isinstance(value, dict):
        return {
            k: "[REDACTED]" if k.lower() in {"api_key", "authorization"} else redact(v, secret)
            for k, v in value.items()
        }
    if isinstance(value, list):
        return [redact(v, secret) for v in value]
    if isinstance(value, str) and secret:
        return value.replace(secret, "[REDACTED]")
    return value


def summarize(name: str, payload: dict[str, Any], requested: date) -> dict[str, Any]:
    notes = []
    if name in {"flights", "flight-returns"}:
        items = payload.get("best_flights", []) + payload.get("other_flights", [])
        items += payload.get("flights", [])
        notes.append(
            "Selection candidates only; a booking response is needed for the complete itinerary."
        )
    elif name == "flight-booking":
        items = payload.get("booking_options", [])
        notes.append("Selected itinerary and seller offers; requires browser verification.")
    elif name == "hotels":
        items = payload.get("properties", [])
        notes.append("Verify whole-stay total, taxes, occupancy, and cancellation at the supplier.")
    elif name == "hotel-detail":
        items = payload.get("rooms", [])
    elif name.startswith("trains-"):
        trains = payload.get("train_results") or {}
        items = trains.get("trains", [])
        if trains.get("date") != str(requested):
            notes.append(
                f"DATE NOT VERIFIED: requested {requested}, returned {trains.get('date')}."
            )
        notes.append("Rail fares are not verified for two adults or railcards.")
    else:
        items = payload.get("directions", [])
        notes.append("A timetable is not proof of fare availability; check returned service times.")
    if not items:
        notes.append(
            "Expected result block missing/empty; do not infer that no travel is available."
        )
    # Keep full responses separately; this index is deliberately small enough to review.
    return {
        "result_count": len(items),
        "notes": notes,
        "examples": [
            {
                k: item[k]
                for k in (
                    "book_with",
                    "flight_numbers",
                    "flights",
                    "baggage_prices",
                    "title",
                    "name",
                    "link",
                    "price",
                    "extracted_price",
                    "nightly_price",
                    "taxes_and_charges",
                    "currency",
                    "room_type",
                    "bed_configuration",
                    "has_free_cancellation",
                    "time_window",
                    "formatted_duration",
                    "transfers",
                    "service_provider",
                    "buy_ticket",
                    "travel_mode",
                )
                if k in item
            }
            for item in items[:3]
        ],
    }


class Spike:
    def __init__(self, client: httpx.Client, output: Path, secret: str, limit: int):
        self.client, self.output, self.secret, self.limit = client, output, secret, limit
        self.count = 0
        self.stop = False
        self.results: list[dict[str, Any]] = []

    def request(self, name: str, params: dict[str, Any], requested: date) -> dict[str, Any] | None:
        if self.stop or self.count >= self.limit:
            print(f"{name}: skipped (request cap or account/rate-limit error)")
            return None
        self.count += 1
        started = time.monotonic()
        record: dict[str, Any] = {"scenario": name, "params": params}
        payload = None
        try:
            response = self.client.get(ENDPOINT, params=params)
            record["http_status"] = response.status_code
            try:
                payload = response.json()
            except ValueError:
                record["error"] = "Non-JSON response (body omitted)."
            if not isinstance(payload, dict):
                payload = None
                record.setdefault("error", "Expected a JSON object.")
            if payload is not None:
                record["response"] = payload
                if not response.is_success or payload.get("error") or payload.get("errors"):
                    record["error"] = "Provider error; see redacted response."
                else:
                    record["summary"] = summarize(name, payload, requested)
            if not response.is_success:
                record.setdefault("error", f"HTTP {response.status_code}")
            if response.status_code in {401, 402, 403, 429}:
                self.stop = True
        except httpx.RequestError as exc:
            # Exception messages can contain URLs. Persist only the error type.
            record["error"] = type(exc).__name__
        record["elapsed_seconds"] = round(time.monotonic() - started, 2)
        safe = redact(record, self.secret)
        self.output.joinpath(f"{self.count:02d}-{name}.json").write_text(
            json.dumps(safe, indent=2, ensure_ascii=False) + "\n"
        )
        self.results.append({k: v for k, v in safe.items() if k != "response"})
        print(f"{name}: {safe.get('error', 'response saved')} ({record['elapsed_seconds']}s)")
        return payload if "error" not in record else None


def flight_followups(spike: Spike, payload: dict, params: dict, requested: date) -> None:
    """Resolve one cheapest token-bearing round trip, preserving all search constraints."""
    for name, token_key in (
        ("flight-returns", "departure_token"),
        ("flight-booking", "booking_token"),
    ):
        items = payload.get("best_flights", []) + payload.get("other_flights", [])
        candidates = [item for item in items if item.get(token_key)]
        if not candidates:
            print(f"{name}: skipped (no {token_key})")
            return
        selected = min(candidates, key=lambda item: item.get("price", float("inf")))
        payload = spike.request(name, {**params, token_key: selected[token_key]}, requested)
        if not payload:
            return


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--live", action="store_true", help="Use the API and consume account credits"
    )
    parser.add_argument(
        "--scenario", choices=["all", "flights", "hotels", "trains", "transit"], default="all"
    )
    parser.add_argument(
        "--date", type=date.fromisoformat, default=date.today() + timedelta(days=28)
    )
    parser.add_argument("--nights", type=int, default=2)
    parser.add_argument(
        "--flight-followups",
        action="store_true",
        help="Resolve one outbound, return, and seller offers (two extra requests)",
    )
    parser.add_argument(
        "--max-requests", type=int, default=6, help="Hard cap; no retries or pagination"
    )
    args = parser.parse_args()
    if args.date <= date.today() or not 1 <= args.nights <= 30 or args.max_requests < 1:
        parser.error("Use a future date, 1-30 nights, and a positive request cap.")
    cases = scenarios(args.date, args.nights, args.scenario)
    print(
        json.dumps(
            {
                "mode": "live" if args.live else "dry-run",
                "scenarios": cases,
                "flight_followups": args.flight_followups,
                "hotel_followup": "One property request after a successful hotel search",
                "maximum_requests": min(
                    args.max_requests,
                    len(cases)
                    + int(args.scenario in {"all", "hotels"})
                    + 2 * int(args.flight_followups and args.scenario in {"all", "flights"}),
                ),
            },
            indent=2,
        )
    )
    if not args.live:
        print("No requests sent. Add --live to use SearchApi credits.")
        return 0
    key = Credentials().api_key
    if key is None or not key.get_secret_value().strip():
        print("Set SEARCHAPI_API_KEY in the root .env or your environment.", file=sys.stderr)
        return 2
    secret = key.get_secret_value().strip()
    output = (
        ROOT
        / "scripts"
        / ".data"
        / "searchapi-spike"
        / datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
    )
    output.mkdir(parents=True, exist_ok=False)
    with httpx.Client(
        headers={"Authorization": f"Bearer {secret}"}, timeout=60, follow_redirects=False
    ) as client:
        spike = Spike(client, output, secret, args.max_requests)
        for name, params in cases:
            payload = spike.request(name, params, args.date)
            if name == "flights" and payload and args.flight_followups:
                flight_followups(spike, payload, params, args.date)
            if name == "hotels" and payload:
                properties = payload.get("properties") or []
                link = next((p.get("link") for p in properties if p.get("link")), None)
                if link:
                    detail = {k: v for k, v in params.items() if k not in {"q", "sort_by"}}
                    detail.update(engine="booking_property", url=link)
                    spike.request("hotel-detail", detail, args.date)
                else:
                    print("hotel-detail: skipped (no property link)")
    (output / "summary.json").write_text(
        json.dumps(
            {
                "requested_date": str(args.date),
                "requests_sent": spike.count,
                "results": spike.results,
                "scope": "API responses only; supplier prices and links are not browser-verified.",
            },
            indent=2,
            ensure_ascii=False,
        )
        + "\n"
    )
    print(f"Saved redacted responses and summary to {output}")
    return 1 if any("error" in result for result in spike.results) else 0


if __name__ == "__main__":
    raise SystemExit(main())
