from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from temporalio.client import WorkflowQueryFailedError
from temporalio.exceptions import ApplicationError
from temporalio.testing import ActivityEnvironment

from cpfc_trip.api import create_app
from cpfc_trip.catalog import load_catalog
from cpfc_trip.config import Settings
from cpfc_trip.domain import Brief, CreateSession, Itinerary, SessionInput, Snapshot
from cpfc_trip.emailing import render
from cpfc_trip.persistence.models import DeliveryRow, SessionRow
from cpfc_trip.persistence.repository import Repository
from cpfc_trip.planner.agent import Intent
from cpfc_trip.planner.planning import choose, enumerate_specs
from cpfc_trip.planner.recorded import sample
from cpfc_trip.temporal.activities import DeliveryActivities


def frozen(data):
    spec = enumerate_specs(data.brief, data.fixtures, data.routes, True)[0]
    trip = choose(
        data.fixtures[0],
        [sample(spec, "flight"), sample(spec, "stay")],
        data.brief,
        data.routes,
        Intent(action="revise", answer=""),
    )
    return Snapshot(
        public_session_id=data.public_session_id,
        email_deadline=datetime.now(UTC),
        interaction_deadline=datetime.now(UTC),
        phase="finalizing",
        email_status="pending",
        itinerary=Itinerary(revision=1, generated_at=datetime.now(UTC), trips=(trip,)),
    )


async def test_submission_and_email_idempotency(repository, session_input, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    request = CreateSession(
        submission_id=uuid4(), email="supporter@example.com", brief=session_input.brief
    )
    data = await repository.create(request, "x" * 64)
    again = await repository.create(request, "x" * 64)
    assert data == again
    with pytest.raises(PermissionError):
        await repository.create(request, "y" * 64)
    assert await repository.authorize(data.public_session_id, "x" * 64)
    assert not await repository.authorize(data.public_session_id, "y" * 64)
    async with repository.sessions() as db:
        row = await db.get(SessionRow, str(data.public_session_id))
        assert b"supporter@example.com" not in row.encrypted_email
        assert "supporter@example.com" not in str(row.workflow_input)
    snapshot = frozen(data)
    deliver = DeliveryActivities(repository).deliver_itinerary
    env = ActivityEnvironment()
    first = await env.run(deliver, snapshot)
    assert await env.run(deliver, snapshot) == first
    async with repository.sessions() as db:
        rows = (await db.scalars(select(DeliveryRow))).all()
        assert len(rows) == 1 and rows[0].attempts == 1
    changed = snapshot.model_copy(
        update={
            "itinerary": snapshot.itinerary.model_copy(
                update={"caveats": ("Different frozen content",)}
            )
        }
    )
    with pytest.raises(ApplicationError, match="mismatch"):
        await env.run(deliver, changed)


async def test_session_uses_selected_departure_airports(repository, session_input):
    brief = session_input.brief.model_copy(update={"origin_city": "Manchester"})
    data = await repository.create(
        CreateSession(submission_id=uuid4(), email="supporter@example.com", brief=brief),
        "x" * 64,
    )
    assert data.brief.origin_city == "Manchester"
    assert {route.origin for route in data.routes} == {"MAN", "Manchester"}


async def test_unsupported_train_city_and_city_fail_before_search(repository, session_input):
    brief = session_input.brief.model_copy(
        update={"origin_city": "Manchester", "transport_mode": "rail"}
    )
    rail = await repository.create(
        CreateSession(submission_id=uuid4(), email="supporter@example.com", brief=brief),
        "x" * 64,
    )
    assert any(route.mode == "rail" for route in rail.routes)
    unsupported_rail = brief.model_copy(update={"origin_city": "Belfast"})
    with pytest.raises(ValueError, match="Train search is not available"):
        await repository.create(
            CreateSession(
                submission_id=uuid4(), email="supporter@example.com", brief=unsupported_rail
            ),
            "x" * 64,
        )
    unsupported = brief.model_copy(update={"origin_city": "Paris", "transport_mode": "flight"})
    with pytest.raises(ValueError, match="supported UK departure city"):
        await repository.create(
            CreateSession(submission_id=uuid4(), email="supporter@example.com", brief=unsupported),
            "x" * 64,
        )


@pytest.mark.parametrize("city", ["London", "Manchester"])
@pytest.mark.parametrize("destination", ["Istanbul", "Białystok", "Salzburg"])
async def test_train_mode_requires_a_route_for_the_selected_match(
    repository: Repository, city: str, destination: str
) -> None:
    fixture = next(item for item in load_catalog()[0] if item.city == destination)
    brief = Brief(fixture_ids=(fixture.id,), origin_city=city, transport_mode="rail")
    with pytest.raises(ValueError, match="Train search is not available"):
        await repository.create(
            CreateSession(submission_id=uuid4(), email="supporter@example.com", brief=brief),
            "x" * 64,
        )


async def test_ambiguous_email_expires_without_resend(repository, session_input):
    request = CreateSession(
        submission_id=uuid4(), email="supporter@example.com", brief=session_input.brief
    )
    data = await repository.create(request, "x" * 64)
    snapshot = frozen(data)
    import json

    from cpfc_trip.persistence.repository import digest

    payload = render(snapshot)
    async with repository.sessions() as db, db.begin():
        db.add(
            DeliveryRow(
                session_id=str(data.public_session_id),
                payload_hash=digest(json.dumps(payload, sort_keys=True)),
                payload=payload,
                created_at=datetime.now(UTC) - timedelta(hours=24),
                status="pending",
                attempts=1,
            )
        )
    with pytest.raises(ApplicationError, match="reconciliation"):
        await ActivityEnvironment().run(DeliveryActivities(repository).deliver_itinerary, snapshot)


def test_email_escapes_and_has_no_script_links(session_input):
    snapshot = frozen(session_input)
    trip = snapshot.itinerary.trips[0].model_copy(
        update={"summary": '<script>alert("bad")</script>'}
    )
    snapshot = snapshot.model_copy(
        update={"itinerary": snapshot.itinerary.model_copy(update={"trips": (trip,)})}
    )
    payload = render(snapshot)
    assert "<script>" not in payload["html"] and "&lt;script&gt;" in payload["html"]
    assert "Prices may have changed" in payload["text"]


async def test_api_auth_polling_204_and_csrf(
    settings: Settings, session_input: SessionInput
) -> None:
    repository = AsyncMock()
    repository.authorize.return_value = False
    temporal = AsyncMock()
    handle = Mock()
    handle.query = AsyncMock(return_value=None)
    temporal.get_workflow_handle = Mock(return_value=handle)
    app = create_app(settings, repository, temporal)
    sid = session_input.public_session_id
    async with (
        app.router.lifespan_context(app),
        AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client,
    ):
        assert (await client.get(f"/api/sessions/{sid}/snapshot")).status_code == 404
        assert not handle.query.called
        repository.authorize.return_value = True
        client.cookies.set(f"cpfc_{sid}", "x" * 64)
        response = await client.get(f"/api/sessions/{sid}/snapshot?after_revision=3")
        assert response.status_code == 204 and response.headers["cache-control"] == "no-store"
        assert (
            await client.post(
                f"/api/sessions/{sid}/finalize",
                json={"id": str(uuid4())},
                headers={"Origin": "https://evil.example"},
            )
        ).status_code == 403
        handle.query.assert_awaited_once()
        handle.query.side_effect = WorkflowQueryFailedError("sensitive upstream diagnostics")
        response = await client.get(f"/api/sessions/{sid}/snapshot")
        assert response.status_code == 503
        assert "sensitive" not in response.text


async def test_preview_serves_export_and_uses_secure_session_cookie(
    settings: Settings, session_input: SessionInput, tmp_path
) -> None:
    """A hosted preview serves static pages and keeps session access on HTTPS."""
    export = tmp_path / "out"
    (export / "plan").mkdir(parents=True)
    (export / "index.html").write_text("<h1>Eagles Away preview</h1>")
    (export / "plan" / "index.html").write_text("<h1>Your plan</h1>")
    preview = settings.model_copy(
        update={
            "app_env": "preview",
            "frontend_origin": "https://preview.example",
            "static_export_dir": str(export),
        }
    )
    repository = AsyncMock()
    repository.create.return_value = session_input
    temporal = AsyncMock()
    app = create_app(preview, repository, temporal)
    async with (
        app.router.lifespan_context(app),
        AsyncClient(transport=ASGITransport(app=app), base_url="https://preview.example") as client,
    ):
        assert "Eagles Away preview" in (await client.get("/")).text
        assert "Your plan" in (await client.get("/plan/")).text
        assert (await client.get("/api/catalog")).status_code == 200
        response = await client.post(
            "/api/sessions",
            json={
                "submission_id": str(uuid4()),
                "email": "supporter@example.com",
                "brief": session_input.brief.model_dump(mode="json"),
            },
            headers={"Origin": "https://preview.example", "X-Submission-Token": "x" * 64},
        )
        assert response.status_code == 202
        assert "Secure" in response.headers["set-cookie"]
