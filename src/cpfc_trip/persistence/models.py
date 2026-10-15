from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, LargeBinary, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class SessionRow(Base):
    __tablename__ = "sessions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    submission_id: Mapped[str] = mapped_column(String(36), unique=True)
    request_hash: Mapped[str] = mapped_column(String(64))
    access_hash: Mapped[str] = mapped_column(String(64))
    email_hash: Mapped[str] = mapped_column(String(64), index=True)
    encrypted_email: Mapped[bytes] = mapped_column(LargeBinary)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    workflow_input: Mapped[dict[str, Any]] = mapped_column(JSON)
    saved_itinerary: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)


class DeliveryRow(Base):
    __tablename__ = "email_deliveries"
    session_id: Mapped[str] = mapped_column(ForeignKey("sessions.id"), primary_key=True)
    payload_hash: Mapped[str] = mapped_column(String(64))
    payload: Mapped[dict[str, Any]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    provider_id: Mapped[str | None] = mapped_column(String(100), nullable=True, unique=True)
    status: Mapped[str] = mapped_column(String(32), default="pending")
    attempts: Mapped[int] = mapped_column(Integer, default=0)


class WebhookRow(Base):
    __tablename__ = "email_webhooks"
    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    event_type: Mapped[str] = mapped_column(String(64))


class SearchCacheRow(Base):
    __tablename__ = "search_cache"
    namespace: Mapped[str] = mapped_column(String(16), primary_key=True)
    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    payload: Mapped[dict[str, object]] = mapped_column(JSON)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
