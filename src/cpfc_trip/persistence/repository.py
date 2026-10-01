import hashlib
import hmac
import json
from datetime import UTC, datetime
from uuid import UUID, uuid4

from cryptography.fernet import Fernet
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

from cpfc_trip.catalog import load_catalog, validate_brief
from cpfc_trip.config import Settings
from cpfc_trip.domain import CreateSession, Limits, SessionInput
from cpfc_trip.persistence.models import SessionRow


def digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


class Repository:
    def __init__(self, engine: AsyncEngine, settings: Settings):
        self.sessions = async_sessionmaker(engine, expire_on_commit=False)
        self.settings = settings
        self.cipher = Fernet(settings.contact_encryption_key.get_secret_value().encode())

    async def create(self, request: CreateSession, token: str) -> SessionInput:
        fingerprint = digest(request.model_dump_json())
        async with self.sessions() as db:
            old = await db.scalar(
                select(SessionRow).where(SessionRow.submission_id == str(request.submission_id))
            )
            if old:
                if old.deleted_at or not hmac.compare_digest(old.access_hash, digest(token)):
                    raise PermissionError("Submission is not accessible")
                if old.request_hash != fingerprint:
                    raise ValueError("Submission ID was already used with a different brief")
                return SessionInput.model_validate(old.workflow_input)
            fixtures, routes = load_catalog()
            brief = validate_brief(request.brief, fixtures, datetime.now(UTC))
            if self.settings.planner_mode == "live":
                enabled = {r.fixture_id for r in routes if r.enabled}
                if not set(brief.fixture_ids) <= enabled:
                    raise ValueError("Live planning is not yet enabled for this fixture")
                if brief.travellers.child_ages or brief.travellers.rooms != 1:
                    raise ValueError(
                        "The live Lyon preview currently supports adults sharing one room. Child and multi-room pricing are still being validated."
                    )
            sid = uuid4()
            data = SessionInput(
                public_session_id=sid,
                contact_id=sid,
                brief=brief,
                fixtures=tuple(f for f in fixtures if f.id in brief.fixture_ids),
                routes=tuple(r for r in routes if r.fixture_id in brief.fixture_ids),
                planner_mode=self.settings.planner_mode,
                limits=Limits(inactivity_seconds=self.settings.inactivity_timeout_seconds),
            )
            email = str(request.email)
            db.add(
                SessionRow(
                    id=str(sid),
                    submission_id=str(request.submission_id),
                    request_hash=fingerprint,
                    access_hash=digest(token),
                    email_hash=hmac.new(
                        self.settings.session_secret.get_secret_value().encode(),
                        email.casefold().encode(),
                        "sha256",
                    ).hexdigest(),
                    encrypted_email=self.cipher.encrypt(email.encode()),
                    created_at=datetime.now(UTC),
                    workflow_input=json.loads(data.model_dump_json()),
                )
            )
            try:
                await db.commit()
            except IntegrityError:
                await db.rollback()
                return await self.create(request, token)
            return data

    async def authorize(self, sid: UUID, token: str) -> bool:
        async with self.sessions() as db:
            row = await db.get(SessionRow, str(sid))
            return bool(
                row
                and row.deleted_at is None
                and hmac.compare_digest(row.access_hash, digest(token))
            )
