"""FastAPI boundary for the static web client."""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, suppress
from typing import Annotated, Any
from uuid import UUID, uuid4

import uvicorn
from fastapi import Cookie, Depends, FastAPI, Header, HTTPException, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, StreamingResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.exc import IntegrityError
from temporalio.api.workflowservice.v1 import GetSystemInfoRequest
from temporalio.client import Client, WorkflowHandle
from temporalio.contrib.workflow_streams import WorkflowStreamClient
from temporalio.exceptions import WorkflowAlreadyStartedError

from cpfc_trip.config import Settings, get_settings
from cpfc_trip.domain import (
    CommandReceipt,
    FinalizeCommand,
    FixtureSnapshot,
    MessageCommand,
    PlanningRequest,
    SessionCreateBody,
    SessionSnapshot,
    StreamEventEnvelope,
    TravellerParty,
    WorkflowStartInput,
)
from cpfc_trip.fixtures import all_fixtures, fixtures_by_id
from cpfc_trip.observability import instrument_fastapi
from cpfc_trip.persistence.database import engine
from cpfc_trip.persistence.repository import (
    StoredSession,
    create_session,
    find_session,
    find_session_by_request,
    latest_delivery,
)
from cpfc_trip.temporal.client import connect_temporal
from cpfc_trip.temporal.workflow import TravelPlanningSessionWorkflow

COOKIE_NAME = "cpfc_session"


class ApiModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SessionCreated(ApiModel):
    public_id: UUID
    snapshot_url: str


class MessageBody(ApiModel):
    command_id: UUID
    body: str = Field(min_length=1, max_length=2_000)


class FinalizeBody(ApiModel):
    command_id: UUID


class EmailPreview(ApiModel):
    status: str
    subject: str
    html: str


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    app.state.temporal = await connect_temporal()
    yield
    await engine().dispose()


app = FastAPI(
    title="Crystal Palace Away Days API",
    version="0.1.0",
    lifespan=lifespan,
)
settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Idempotency-Key", "Last-Event-ID"],
)
instrument_fastapi(app)


@app.middleware("http")
async def disable_api_caching(request: Request, call_next: Any) -> Response:
    response: Response = await call_next(request)
    if request.url.path.startswith(("/api", "/healthz", "/readyz")):
        response.headers["Cache-Control"] = "no-store"
    return response


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/readyz")
async def readyz(request: Request) -> dict[str, str]:
    temporal: Client = request.app.state.temporal
    try:
        await temporal.workflow_service.get_system_info(GetSystemInfoRequest())
    except Exception as exc:  # pragma: no cover - service boundary
        raise HTTPException(status_code=503, detail="Temporal is unavailable") from exc
    return {"status": "ready"}


@app.get("/api/fixtures", response_model=tuple[FixtureSnapshot, ...])
async def get_fixtures() -> tuple[FixtureSnapshot, ...]:
    return all_fixtures()


@app.post("/api/sessions", response_model=SessionCreated, status_code=status.HTTP_202_ACCEPTED)
async def start_session(
    body: SessionCreateBody, response: Response, request: Request
) -> SessionCreated:
    try:
        selected_fixtures = fixtures_by_id(body.fixture_ids)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    stored = await find_session_by_request(body.request_id)
    if stored is None:
        public_id = uuid4()
        token = _access_token(public_id, settings)
        try:
            stored = await create_session(
                request_id=body.request_id,
                email=str(body.email),
                public_id=public_id,
                token_hash=_hash_token(token),
            )
        except IntegrityError:
            stored = await find_session_by_request(body.request_id)
            if stored is None:  # pragma: no cover - defensive concurrency guard
                raise

    token = _access_token(stored.public_id, settings)
    planning_request = PlanningRequest(
        fixture_ids=body.fixture_ids,
        origin=body.origin,
        travellers=TravellerParty(adults=body.adults, child_ages=body.child_ages, rooms=body.rooms),
        flexibility_days=body.flexibility_days,
        budget_tier=body.budget_tier,
        extra_instructions=body.extra_instructions,
        contact_id=stored.contact_id,
        request_id=body.request_id,
    )
    workflow_input = WorkflowStartInput(
        public_id=stored.public_id,
        request=planning_request,
        fixtures=selected_fixtures,
        inactivity_timeout_seconds=settings.inactivity_timeout_seconds,
        planner_mode=settings.planner_mode,
    )
    temporal: Client = request.app.state.temporal
    try:
        await temporal.start_workflow(
            TravelPlanningSessionWorkflow.run,
            workflow_input,
            id=stored.workflow_id,
            task_queue=settings.temporal_task_queue,
        )
    except WorkflowAlreadyStartedError:
        pass
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Unable to start the planning session") from exc

    response.set_cookie(
        COOKIE_NAME,
        f"{stored.public_id}.{token}",
        httponly=True,
        secure=settings.app_env == "production",
        samesite="lax",
        max_age=30 * 24 * 60 * 60,
        path="/",
    )
    return SessionCreated(
        public_id=stored.public_id,
        snapshot_url=f"/api/sessions/{stored.public_id}",
    )


async def _authorized_session(
    public_id: UUID,
    cookie: Annotated[str | None, Cookie(alias=COOKIE_NAME)] = None,
) -> StoredSession:
    if cookie is None:
        raise HTTPException(status_code=401, detail="Session cookie is missing")
    cookie_public_id, separator, token = cookie.partition(".")
    if not separator or cookie_public_id != str(public_id):
        raise HTTPException(status_code=403, detail="Session cookie does not match")
    stored = await find_session(public_id)
    if stored is None or not hmac.compare_digest(_hash_token(token), stored.access_token_hash):
        raise HTTPException(status_code=403, detail="Session access is invalid")
    return stored


@app.get("/api/sessions/{public_id}", response_model=SessionSnapshot)
async def get_snapshot(
    request: Request,
    session: Annotated[StoredSession, Depends(_authorized_session)],
) -> SessionSnapshot:
    handle = _workflow_handle(request, session)
    try:
        return await handle.query(TravelPlanningSessionWorkflow.get_snapshot)
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Planning session is unavailable") from exc


@app.get("/api/sessions/{public_id}/events")
async def session_events(
    request: Request,
    session: Annotated[StoredSession, Depends(_authorized_session)],
    last_event_id: Annotated[str | None, Header(alias="Last-Event-ID")] = None,
) -> StreamingResponse:
    try:
        from_offset = int(last_event_id) + 1 if last_event_id is not None else 0
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Last-Event-ID must be an integer") from exc
    if from_offset < 0:
        raise HTTPException(status_code=400, detail="Last-Event-ID is out of range")

    temporal: Client = request.app.state.temporal
    stream = WorkflowStreamClient.create(temporal, session.workflow_id)

    async def event_source() -> AsyncIterator[str]:
        iterator = stream.subscribe(from_offset=from_offset, result_type=StreamEventEnvelope)
        pending: asyncio.Future[Any] | None = None
        try:
            while True:
                pending = asyncio.ensure_future(anext(iterator))
                while not pending.done():
                    done, _ = await asyncio.wait({pending}, timeout=15)
                    if not done:
                        yield ": heartbeat\n\n"
                try:
                    item = pending.result()
                except StopAsyncIteration:
                    return
                data = item.data.model_dump(mode="json")
                yield f"id: {item.offset}\ndata: {json.dumps(data, separators=(',', ':'))}\n\n"
                if await request.is_disconnected():
                    return
        finally:
            if pending and not pending.done():
                pending.cancel()
                with suppress(asyncio.CancelledError):
                    await pending

    return StreamingResponse(
        event_source(),
        media_type="text/event-stream",
        headers={"X-Accel-Buffering": "no", "Connection": "keep-alive"},
    )


@app.post("/api/sessions/{public_id}/messages", response_model=CommandReceipt)
async def submit_message(
    body: MessageBody,
    request: Request,
    session: Annotated[StoredSession, Depends(_authorized_session)],
) -> CommandReceipt:
    handle = _workflow_handle(request, session)
    try:
        return await handle.execute_update(
            TravelPlanningSessionWorkflow.submit_message,
            MessageCommand(command_id=body.command_id, body=body.body),
        )
    except Exception as exc:
        raise HTTPException(status_code=409, detail="Message was not accepted") from exc


@app.post("/api/sessions/{public_id}/finalize", response_model=CommandReceipt)
async def finalize_session(
    body: FinalizeBody,
    request: Request,
    session: Annotated[StoredSession, Depends(_authorized_session)],
) -> CommandReceipt:
    handle = _workflow_handle(request, session)
    try:
        return await handle.execute_update(
            TravelPlanningSessionWorkflow.request_finalize,
            FinalizeCommand(command_id=body.command_id),
        )
    except Exception as exc:
        raise HTTPException(status_code=409, detail="Finalization was not accepted") from exc


@app.get("/api/sessions/{public_id}/email-preview", response_model=EmailPreview)
async def email_preview(
    session: Annotated[StoredSession, Depends(_authorized_session)],
) -> EmailPreview:
    if settings.app_env == "production":
        raise HTTPException(status_code=404, detail="Not found")
    delivery = await latest_delivery(session.public_id)
    if delivery is None:
        raise HTTPException(status_code=404, detail="No email has been generated yet")
    return EmailPreview(
        status=delivery.status,
        subject=delivery.subject,
        html=delivery.preview_html,
    )


@app.get("/api/sessions/{public_id}/email-preview/render", response_class=HTMLResponse)
async def render_email_preview(
    session: Annotated[StoredSession, Depends(_authorized_session)],
) -> HTMLResponse:
    if settings.app_env == "production":
        raise HTTPException(status_code=404, detail="Not found")
    delivery = await latest_delivery(session.public_id)
    if delivery is None:
        raise HTTPException(status_code=404, detail="No email has been generated yet")
    return HTMLResponse(delivery.preview_html)


def _workflow_handle(request: Request, session: StoredSession) -> WorkflowHandle[Any, Any]:
    temporal: Client = request.app.state.temporal
    return temporal.get_workflow_handle(session.workflow_id)


def _access_token(public_id: UUID, settings: Settings) -> str:
    return hmac.new(
        settings.session_secret.encode(), str(public_id).encode(), hashlib.sha256
    ).hexdigest()


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def run() -> None:
    uvicorn.run("cpfc_trip.api:app", host="0.0.0.0", port=8000)
