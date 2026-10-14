"""JSON-only API. All active session reads Query Temporal directly."""

import base64
import binascii
import re
import secrets
import time
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from typing import Annotated, Any, cast
from uuid import UUID

import uvicorn
from fastapi import FastAPI, Header, HTTPException, Query, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from svix.webhooks import Webhook, WebhookVerificationError
from temporalio.client import Client, WorkflowQueryFailedError, WorkflowUpdateFailedError
from temporalio.common import WorkflowIDConflictPolicy, WorkflowIDReusePolicy
from temporalio.exceptions import WorkflowAlreadyStartedError
from temporalio.service import RPCError

from cpfc_trip.catalog import load_catalog
from cpfc_trip.config import Settings
from cpfc_trip.domain import Command, CreateSession, MessageCommand, Receipt, Snapshot
from cpfc_trip.origins import LIVE_ORIGINS, UK_RAIL
from cpfc_trip.persistence.database import engine
from cpfc_trip.persistence.models import DeliveryRow, WebhookRow
from cpfc_trip.persistence.repository import Repository
from cpfc_trip.temporal.client import connect
from cpfc_trip.temporal.workflow import TravelPlanningSessionWorkflow


class EmailEventData(BaseModel):
    email_id: str = Field(min_length=1, max_length=100)
    tags: dict[str, str] = Field(default_factory=dict)


class EmailEvent(BaseModel):
    type: str = Field(min_length=1, max_length=64)
    data: EmailEventData


DELIVERY_STATUS_ORDER = {"email.delivered": 1, "email.bounced": 2, "email.complained": 3}


class LocalLimiter:
    """Local development limiter. The public deployment also requires shared edge quotas."""

    def __init__(self) -> None:
        self.hits: dict[str, deque[float]] = defaultdict(deque)

    def check(self, key: str, limit: int, seconds: int = 60) -> None:
        now = time.monotonic()
        if len(self.hits) > 10000:
            self.hits = defaultdict(
                deque, {k: v for k, v in self.hits.items() if v and v[-1] > now - seconds}
            )
        q = self.hits[key]
        while q and q[0] < now - seconds:
            q.popleft()
        if len(q) >= limit:
            raise HTTPException(
                429, "Too many requests; please try again shortly", headers={"Retry-After": "10"}
            )
        q.append(now)


def create_app(
    settings: Settings | None = None,
    repository: Repository | None = None,
    temporal: Client | None = None,
) -> FastAPI:
    config = settings or Settings()
    limiter = LocalLimiter()

    @asynccontextmanager
    async def lifespan(app: FastAPI):  # type: ignore[no-untyped-def]
        db = engine(config)
        app.state.repository = repository or Repository(db, config)
        app.state.temporal = temporal or await connect(config)
        try:
            yield
        finally:
            await db.dispose()

    app = FastAPI(title="Eagles Away", version="0.1.0", lifespan=lifespan)
    allowed_frontend_origins = {config.frontend_origin}
    allowed_frontend_origins.update(
        origin.strip() for origin in config.additional_frontend_origins.split(",") if origin.strip()
    )
    if config.app_env in {"development", "test"}:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=sorted(allowed_frontend_origins),
            allow_credentials=True,
            allow_methods=["GET", "POST"],
            allow_headers=["Content-Type", "X-Submission-Token"],
        )

    @app.middleware("http")
    async def protect(request: Request, call_next: Any) -> Response:
        if (
            config.app_env == "preview"
            and config.preview_access_required
            and request.url.path != "/healthz"
        ):
            encoded = request.headers.get("authorization", "").removeprefix("Basic ")
            try:
                decoded = base64.b64decode(encoded, validate=True).decode("utf-8")
                username, separator, password = decoded.partition(":")
            except (binascii.Error, UnicodeDecodeError):
                username, separator, password = "", "", ""
            if (
                not separator
                or not secrets.compare_digest(username.encode(), config.preview_username.encode())
                or not secrets.compare_digest(
                    password.encode(), config.preview_password.get_secret_value().encode()
                )
            ):
                return Response(
                    status_code=401,
                    headers={
                        "WWW-Authenticate": 'Basic realm="Eagles Away preview"',
                        "Cache-Control": "no-store",
                    },
                )
        if (
            request.method == "POST"
            and request.url.path.startswith("/api/")
            and request.headers.get("origin") not in allowed_frontend_origins
        ):
            return JSONResponse({"detail": "Request origin is not allowed"}, status_code=403)
        if int(request.headers.get("content-length", "0")) > 32000:
            return JSONResponse({"detail": "Request is too large"}, status_code=413)
        response: Response = await call_next(request)
        response.headers.update(
            {
                "Cache-Control": "no-store",
                "X-Content-Type-Options": "nosniff",
                "Referrer-Policy": "no-referrer",
            }
        )
        return response

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError) -> Response:
        # FastAPI's default errors include input values, potentially echoing an email/token.
        return JSONResponse(
            {"detail": [{"loc": x["loc"], "msg": x["msg"]} for x in exc.errors()]}, status_code=422
        )

    def repo(request: Request) -> Repository:
        return request.app.state.repository  # type: ignore[no-any-return]

    def client(request: Request) -> Client:
        return request.app.state.temporal  # type: ignore[no-any-return]

    def ip(request: Request) -> str:
        # Do not trust arbitrary forwarded IP headers. The deployment proxy is configured separately.
        return request.client.host if request.client else "unknown"

    async def authorize(request: Request, public_id: UUID) -> None:
        token = request.cookies.get(f"cpfc_{public_id}", "")
        if not token or not await repo(request).authorize(public_id, token):
            raise HTTPException(404, "Session not found or access expired")

    @app.get("/api/catalog")
    async def catalog() -> dict[str, Any]:
        fixtures, routes = load_catalog()
        if config.planner_mode == "live":
            enabled = {r.fixture_id for r in routes if r.enabled}
            fixtures = tuple(f for f in fixtures if f.id in enabled)
        return {
            "fixtures": fixtures,
            "origin": "London",
            "origin_cities": LIVE_ORIGINS,
            "rail_cities": ["London", *(city for city in sorted(UK_RAIL) if city in LIVE_ORIGINS)],
            "development_mode": config.planner_mode == "recorded",
        }

    @app.post("/api/sessions", status_code=202)
    async def create(
        body: CreateSession,
        request: Request,
        response: Response,
        token: Annotated[str, Header(alias="X-Submission-Token")],
    ) -> dict[str, Any]:
        if not re.fullmatch(r"[A-Za-z0-9_-]{43,128}", token):
            raise HTTPException(422, "A strong submission token is required")
        limiter.check(f"create:{ip(request)}", 5)
        try:
            data = await repo(request).create(body, token)
        except ValueError as error:
            raise HTTPException(422, str(error)) from None
        except PermissionError:
            raise HTTPException(409, "Submission ID is already in use") from None
        try:
            await client(request).start_workflow(
                TravelPlanningSessionWorkflow.run,
                data,
                id=f"travel-session/{data.public_session_id}",
                task_queue=config.temporal_task_queue,
                id_conflict_policy=WorkflowIDConflictPolicy.USE_EXISTING,
                id_reuse_policy=WorkflowIDReusePolicy.REJECT_DUPLICATE,
                rpc_timeout=timedelta(seconds=5),
            )
        except WorkflowAlreadyStartedError:
            pass
        except RPCError:
            raise HTTPException(
                503, "Planning is temporarily unavailable. Retry this same submission."
            ) from None
        response.set_cookie(
            f"cpfc_{data.public_session_id}",
            token,
            httponly=True,
            secure=config.app_env in {"preview", "production"},
            samesite="lax",
            path=f"/api/sessions/{data.public_session_id}",
        )
        return {"public_session_id": data.public_session_id}

    @app.get("/api/sessions/{public_id}/snapshot", response_model=Snapshot | None)
    async def snapshot(
        public_id: UUID, request: Request, after_revision: Annotated[int | None, Query(ge=0)] = None
    ) -> Snapshot | Response:
        await authorize(request, public_id)
        limiter.check(f"poll:{public_id}", 90)
        handle = client(request).get_workflow_handle(f"travel-session/{public_id}")
        try:
            value = await handle.query(
                TravelPlanningSessionWorkflow.get_snapshot,
                after_revision,
                rpc_timeout=timedelta(seconds=5),
            )
        except (RPCError, WorkflowQueryFailedError):
            raise HTTPException(503, "Reconnecting to your saved planning session") from None
        return value if value else Response(status_code=204)

    async def update(
        request: Request, public_id: UUID, command: Command, finalize: bool
    ) -> Receipt:
        await authorize(request, public_id)
        limiter.check(f"command:{public_id}", 20)
        handle = client(request).get_workflow_handle(f"travel-session/{public_id}")
        name = "request_finalize" if finalize else "submit_message"
        try:
            result = await handle.execute_update(
                name,
                command,
                id=f"{name}/{command.id}",
                result_type=Receipt,
                rpc_timeout=timedelta(seconds=5),
            )
        except (RPCError, WorkflowUpdateFailedError):
            raise HTTPException(
                503, "Could not confirm acceptance. Retry the same command."
            ) from None
        if not result.accepted:
            raise HTTPException(409, result.reason)
        return cast(Receipt, result)

    @app.post("/api/sessions/{public_id}/messages", response_model=Receipt, status_code=202)
    async def message(public_id: UUID, body: MessageCommand, request: Request) -> Receipt:
        return await update(request, public_id, body, False)

    @app.post("/api/sessions/{public_id}/finalize", response_model=Receipt, status_code=202)
    async def finalize(public_id: UUID, body: Command, request: Request) -> Receipt:
        return await update(request, public_id, body, True)

    @app.post("/webhooks/resend")
    async def webhook(request: Request) -> Response:
        key = config.resend_webhook_secret.get_secret_value()
        if not key:
            raise HTTPException(503, "Webhook is not configured")
        raw = await request.body()
        if len(raw) > 32000:
            raise HTTPException(413)
        try:
            Webhook(key).verify(raw.decode(), dict(request.headers))
            event = EmailEvent.model_validate_json(raw)
        except (WebhookVerificationError, ValueError):
            raise HTTPException(400, "Invalid signature") from None
        event_id = request.headers["svix-id"]
        if len(event_id) > 128:
            raise HTTPException(400, "Invalid event ID")
        if event.type not in DELIVERY_STATUS_ORDER:
            return Response(status_code=200)
        async with repo(request).sessions() as db, db.begin():
            if await db.get(WebhookRow, event_id):
                return Response(status_code=200)
            # A signed session tag also reconciles an accepted send whose HTTP receipt was lost.
            # Locking serializes this with the send transaction, even before provider_id is saved.
            sid = event.data.tags.get("session_id")
            delivery = await db.scalar(
                select(DeliveryRow)
                .where(
                    DeliveryRow.session_id == sid
                    if sid
                    else DeliveryRow.provider_id == event.data.email_id
                )
                .with_for_update()
            )
            if delivery:
                if delivery.provider_id and delivery.provider_id != event.data.email_id:
                    raise HTTPException(409, "Email receipt does not match the saved delivery")
                delivery.provider_id = event.data.email_id
                if DELIVERY_STATUS_ORDER[event.type] > DELIVERY_STATUS_ORDER.get(
                    delivery.status, 0
                ):
                    delivery.status = event.type
                db.add(
                    WebhookRow(id=event_id, received_at=datetime.now(UTC), event_type=event.type)
                )
            try:
                await db.flush()
            except IntegrityError:
                await db.rollback()
        return Response(status_code=200)

    @app.get("/healthz")
    async def health() -> dict[str, bool]:
        return {"ok": True}

    @app.get("/readyz")
    async def ready(request: Request) -> dict[str, bool]:
        try:
            async with repo(request).sessions() as db:
                await db.execute(text("SELECT 1"))
            await client(request).service_client.check_health(timeout=timedelta(seconds=3))
        except Exception:
            raise HTTPException(503, "Dependencies are not ready") from None
        return {"ok": True}

    if config.static_export_dir:
        app.mount("/", StaticFiles(directory=config.static_export_dir, html=True), name="frontend")

    return app


def main() -> None:
    uvicorn.run(
        "cpfc_trip.api:create_app", factory=True, host="0.0.0.0", port=8000, access_log=False
    )
