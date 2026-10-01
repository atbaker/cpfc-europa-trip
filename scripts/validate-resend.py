"""Preview by default; --send-to explicitly sends one saved itinerary through the delivery Activity."""

import argparse
import asyncio
import hashlib
import hmac
from email.utils import parseaddr
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

import httpx
from pydantic import EmailStr, TypeAdapter
from temporalio.testing import ActivityEnvironment

from cpfc_trip.config import Settings
from cpfc_trip.domain import Brief, CreateSession, Snapshot
from cpfc_trip.emailing import render
from cpfc_trip.persistence.database import engine
from cpfc_trip.persistence.repository import Repository
from cpfc_trip.temporal.activities import DeliveryActivities


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--snapshot", type=Path, default=Path(".data/email-previews/lyon-live-review.json")
    )
    parser.add_argument("--check-domain", action="store_true", help="Read-only Resend API check")
    parser.add_argument("--send-to", help="Explicitly authorized recipient; sends a real email")
    parser.add_argument(
        "--case",
        default="",
        help="Separate explicitly authorized test case; never change after an ambiguous send",
    )
    args = parser.parse_args()
    settings = Settings()
    source = await asyncio.to_thread(args.snapshot.read_text)
    snapshot = Snapshot.model_validate_json(source)
    payload = render(snapshot)
    output = Path(".data/email-previews/eagles-away-review.html")
    await asyncio.to_thread(output.parent.mkdir, parents=True, exist_ok=True)
    await asyncio.to_thread(output.write_text, payload["html"])
    print(f"Email preview: {output}")
    if args.check_domain:
        await check_domain(settings)
    if args.send_to:
        recipient = TypeAdapter(EmailStr).validate_python(args.send_to)
        if not snapshot.itinerary or snapshot.development_mode:
            raise SystemExit("Live validation requires a saved, non-synthetic itinerary")
        # Repeat runs for the same evidence/recipient resume the original delivery. No new key
        # after an ambiguous response, and neither recipient nor secret is written to reports.
        fingerprint = hashlib.sha256(source.encode()).hexdigest()
        if args.case:
            fingerprint = hashlib.sha256(f"{fingerprint}/{args.case}".encode()).hexdigest()
        token = hmac.new(
            settings.session_secret.get_secret_value().encode(),
            f"resend-validation/{recipient}/{fingerprint}".encode(),
            "sha256",
        ).hexdigest()
        request = CreateSession(
            submission_id=uuid5(NAMESPACE_URL, token),
            email=recipient,
            brief=Brief(fixture_ids=tuple(t.fixture.id for t in snapshot.itinerary.trips)),
        )
        config = settings.model_copy(update={"email_mode": "resend"})
        db = engine(config)
        try:
            repo = Repository(db, config)
            data = await repo.create(request, token)
            snapshot = snapshot.model_copy(update={"public_session_id": data.public_session_id})
            deliver = DeliveryActivities(repo).deliver_itinerary
            first = await ActivityEnvironment().run(deliver, snapshot)
            assert await ActivityEnvironment().run(deliver, snapshot) == first
            print(f"Resend accepted email: {first}; repeated delivery returned the same receipt.")
            print("Inbox arrival and live webhook delivery are separate checks.")
        finally:
            await db.dispose()
    else:
        print("No email sent; original price observations preserved.")


async def check_domain(settings: Settings) -> None:
    _, sender = parseaddr(settings.resend_from_email)
    domain = sender.partition("@")[2].lower()
    if not domain or not settings.resend_api_key.get_secret_value():
        raise SystemExit("Resend sender/key missing")
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.get(
                "https://api.resend.com/domains",
                headers={"Authorization": f"Bearer {settings.resend_api_key.get_secret_value()}"},
            )
    except httpx.RequestError:
        raise SystemExit("Could not reach Resend; credentials were not logged") from None
    if response.status_code == 401 and response.json().get("name") == "restricted_api_key":
        print(
            "Sending-only key: domain listing is restricted. Verify the domain in Resend's dashboard."
        )
        return
    if not response.is_success:
        raise SystemExit(
            f"Resend domain check failed (HTTP {response.status_code}); response omitted"
        )
    for entry in response.json().get("data", []):
        if entry.get("name") == domain:
            print(f"Sender domain: {domain}; status: {entry.get('status')}")
            return
    raise SystemExit("Sender domain was not found in this domain-list page")


if __name__ == "__main__":
    asyncio.run(main())
