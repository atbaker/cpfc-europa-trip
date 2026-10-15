import base64
import json
from datetime import UTC, datetime
from uuid import uuid4

import httpx
import pytest
import respx
from pydantic import SecretStr
from sqlalchemy import select
from svix.webhooks import Webhook
from temporalio.exceptions import ApplicationError
from temporalio.testing import ActivityEnvironment
from test_api_email import frozen

from cpfc_trip.api import create_app
from cpfc_trip.domain import CreateSession
from cpfc_trip.persistence.models import DeliveryRow, SessionRow, WebhookRow
from cpfc_trip.resend import send
from cpfc_trip.temporal.activities import DeliveryActivities


@pytest.mark.parametrize(
    ("status", "name", "permanent"),
    [
        (403, "invalid_api_key", True),
        (409, "invalid_idempotent_request", True),
        (409, "concurrent_idempotent_requests", False),
        (429, "rate_limit_exceeded", False),
        (500, "internal_server_error", False),
    ],
)
async def test_resend_retry_policy_does_not_expose_provider_body(status, name, permanent):
    with respx.mock:
        respx.post("https://api.resend.com/emails").respond(
            status, json={"name": name, "message": "private recipient and provider diagnostics"}
        )
        with pytest.raises(ApplicationError) as caught:
            await send("test-key", {"subject": "Example"}, "fixed-key")
        assert caught.value.non_retryable is permanent
        assert "private" not in str(caught.value)


async def test_ambiguous_send_reuses_frozen_body_sender_and_key(repository, session_input):
    repository.settings.email_mode = "resend"
    repository.settings.resend_api_key = SecretStr("test-key")
    repository.settings.resend_from_email = "Eagles Away <pete@send.eaglesaway.com>"
    data = await repository.create(
        CreateSession(submission_id=uuid4(), email="fan@example.com", brief=session_input.brief),
        "x" * 64,
    )
    snapshot = frozen(data)
    deliver = DeliveryActivities(repository).deliver_itinerary
    with respx.mock:
        route = respx.post("https://api.resend.com/emails")
        route.side_effect = httpx.ReadTimeout("private network diagnostics")
        with pytest.raises(ApplicationError, match="outcome unknown"):
            await ActivityEnvironment().run(deliver, snapshot)
        async with repository.sessions() as db:
            session = await db.get(SessionRow, str(data.public_session_id))
            assert session is not None and session.encrypted_email
        original = route.calls[0].request
        repository.settings.resend_from_email = "New name <changed@send.eaglesaway.com>"
        route.side_effect = None
        route.respond(200, json={"id": "resend-test-id"})
        assert await ActivityEnvironment().run(deliver, snapshot) == "resend-test-id"
        assert original.content == route.calls[1].request.content
        assert (
            original.headers["idempotency-key"] == route.calls[1].request.headers["idempotency-key"]
        )
        assert await ActivityEnvironment().run(deliver, snapshot) == "resend-test-id"
        assert route.call_count == 2
        async with repository.sessions() as db:
            session = await db.get(SessionRow, str(data.public_session_id))
            delivery = await db.get(DeliveryRow, str(data.public_session_id))
            assert session is not None
            assert session.encrypted_email == b""
            assert session.email_hash == ""
            assert delivery is not None and "to" not in delivery.payload


async def test_webhook_signatures_order_duplicates_and_lost_receipt(repository, session_input):
    key = "whsec_" + base64.b64encode(b"local-test-signature-secret").decode()
    repository.settings.resend_webhook_secret = SecretStr(key)
    data = await repository.create(
        CreateSession(submission_id=uuid4(), email="fan@example.com", brief=session_input.brief),
        "x" * 64,
    )
    sid = str(data.public_session_id)
    async with repository.sessions() as db, db.begin():
        db.add(
            DeliveryRow(
                session_id=sid,
                payload_hash="test",
                payload={},
                created_at=datetime.now(UTC),
                attempts=1,
            )
        )
    app = create_app(repository.settings)
    app.state.repository = repository
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:

        async def event(kind, event_id, valid=True):
            body = json.dumps(
                {
                    "type": kind,
                    "data": {
                        "email_id": "accepted-before-timeout",
                        "tags": {"session_id": sid},
                        "to": ["not-to-be-stored@example.com"],
                    },
                }
            )
            now = datetime.now(UTC)
            return await client.post(
                "/webhooks/resend",
                content=body,
                headers={
                    "svix-id": event_id,
                    "svix-timestamp": str(int(now.timestamp())),
                    "svix-signature": Webhook(key).sign(event_id, now, body)
                    if valid
                    else "v1,invalid",
                },
            )

        assert (await event("email.delivered", "invalid", False)).status_code == 400
        assert (await event("email.bounced", "bounce")).status_code == 200
        assert (await event("email.delivered", "late-delivery")).status_code == 200
        assert (await event("email.bounced", "bounce")).status_code == 200
        async with repository.sessions() as db:
            delivery = await db.get(DeliveryRow, sid)
            assert delivery.provider_id == "accepted-before-timeout"
            assert delivery.status == "email.bounced"
            assert len((await db.scalars(select(WebhookRow))).all()) == 2
        assert (await event("email.complained", "complaint")).status_code == 200
        async with repository.sessions() as db:
            assert (await db.get(DeliveryRow, sid)).status == "email.complained"
