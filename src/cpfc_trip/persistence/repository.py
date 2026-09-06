"""Small persistence boundary for access and email data."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy import select

from cpfc_trip.persistence.database import session_factory
from cpfc_trip.persistence.models import ContactRow, EmailDeliveryRow, SessionRow


@dataclass(frozen=True)
class StoredSession:
    public_id: UUID
    workflow_id: str
    request_id: UUID
    contact_id: UUID
    access_token_hash: str


async def find_session_by_request(request_id: UUID) -> StoredSession | None:
    async with session_factory()() as db:
        row = await db.scalar(select(SessionRow).where(SessionRow.request_id == str(request_id)))
        return _stored_session(row) if row else None


async def find_session(public_id: UUID) -> StoredSession | None:
    async with session_factory()() as db:
        row = await db.get(SessionRow, str(public_id))
        return _stored_session(row) if row else None


async def create_session(
    *, request_id: UUID, email: str, public_id: UUID, token_hash: str
) -> StoredSession:
    now = datetime.now(UTC)
    contact_id = uuid4()
    workflow_id = f"travel-session/{public_id}"
    async with session_factory()() as db:
        db.add(
            ContactRow(
                id=str(contact_id),
                email=email,
                created_at=now,
                expires_at=now + timedelta(days=30),
            )
        )
        db.add(
            SessionRow(
                public_id=str(public_id),
                workflow_id=workflow_id,
                request_id=str(request_id),
                contact_id=str(contact_id),
                access_token_hash=token_hash,
                created_at=now,
            )
        )
        await db.commit()
    return StoredSession(public_id, workflow_id, request_id, contact_id, token_hash)


async def get_contact_email(contact_id: UUID) -> str:
    async with session_factory()() as db:
        row = await db.get(ContactRow, str(contact_id))
        if row is None:
            raise LookupError(f"contact not found: {contact_id}")
        return row.email


async def find_delivery(idempotency_key: str) -> EmailDeliveryRow | None:
    async with session_factory()() as db:
        row: EmailDeliveryRow | None = await db.scalar(
            select(EmailDeliveryRow).where(EmailDeliveryRow.idempotency_key == idempotency_key)
        )
        return row


async def create_delivery(
    *,
    idempotency_key: str,
    public_id: UUID,
    contact_id: UUID,
    itinerary_revision: int,
    subject: str,
    preview_html: str,
    status: str,
    provider_message_id: str | None,
) -> EmailDeliveryRow:
    now = datetime.now(UTC)
    row = EmailDeliveryRow(
        id=str(uuid4()),
        idempotency_key=idempotency_key,
        public_id=str(public_id),
        contact_id=str(contact_id),
        itinerary_revision=itinerary_revision,
        status=status,
        provider_message_id=provider_message_id,
        subject=subject,
        preview_html=preview_html,
        created_at=now,
        sent_at=now if status == "sent" else None,
    )
    async with session_factory()() as db:
        db.add(row)
        await db.commit()
        await db.refresh(row)
    return row


async def latest_delivery(public_id: UUID) -> EmailDeliveryRow | None:
    async with session_factory()() as db:
        row: EmailDeliveryRow | None = await db.scalar(
            select(EmailDeliveryRow)
            .where(EmailDeliveryRow.public_id == str(public_id))
            .order_by(EmailDeliveryRow.created_at.desc())
            .limit(1)
        )
        return row


def _stored_session(row: SessionRow) -> StoredSession:
    return StoredSession(
        public_id=UUID(row.public_id),
        workflow_id=row.workflow_id,
        request_id=UUID(row.request_id),
        contact_id=UUID(row.contact_id),
        access_token_hash=row.access_token_hash,
    )
