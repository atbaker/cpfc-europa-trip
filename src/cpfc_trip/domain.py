"""Durable, club-neutral application contracts."""

from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, HttpUrl, field_validator


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class BudgetTier(StrEnum):
    BUDGET = "budget"
    VALUE = "value"
    COMFORT = "comfort"


class SessionPhase(StrEnum):
    CREATED = "created"
    RESEARCHING = "researching"
    DRAFT_READY = "draft_ready"
    REVISING = "revising"
    FINALIZING = "finalizing"
    EMAILED = "emailed"
    FAILED = "failed"
    EMAIL_FAILED = "email_failed"


class Place(FrozenModel):
    id: str
    name: str
    country_code: str
    latitude: float
    longitude: float
    timezone: str


class Venue(FrozenModel):
    id: str
    name: str
    city: Place
    latitude: float
    longitude: float
    status: Literal["provisional", "confirmed"]


class FixtureSnapshot(FrozenModel):
    id: str
    competition_season_id: str
    home_team_id: str
    away_team_id: str
    home_team_name: str
    away_team_name: str
    kickoff_at: datetime
    venue: Venue
    status: Literal["provisional", "confirmed", "rescheduled", "cancelled"]
    source_url: HttpUrl
    source_checked_at: datetime
    catalog_version: str

    @field_validator("kickoff_at", "source_checked_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("datetime must be timezone-aware")
        return value


class TravellerParty(FrozenModel):
    adults: int = Field(default=1, ge=1, le=8)
    child_ages: tuple[int, ...] = ()
    rooms: int = Field(default=1, ge=1, le=4)

    @field_validator("child_ages")
    @classmethod
    def validate_child_ages(cls, ages: tuple[int, ...]) -> tuple[int, ...]:
        if len(ages) > 6 or any(age < 0 or age > 17 for age in ages):
            raise ValueError("child ages must be between 0 and 17")
        return ages

    @property
    def size(self) -> int:
        return self.adults + len(self.child_ages)


class PlanningRequest(FrozenModel):
    team_id: str = "crystal-palace"
    fixture_ids: tuple[str, ...]
    origin: str = Field(default="London", min_length=2, max_length=100)
    travellers: TravellerParty = TravellerParty()
    flexibility_days: int = Field(default=1, ge=0, le=3)
    budget_tier: BudgetTier = BudgetTier.VALUE
    extra_instructions: str | None = Field(default=None, max_length=2_000)
    locale: str = "en-GB"
    currency: Literal["GBP"] = "GBP"
    contact_id: UUID
    request_id: UUID

    @field_validator("fixture_ids")
    @classmethod
    def require_fixtures(cls, fixture_ids: tuple[str, ...]) -> tuple[str, ...]:
        if not fixture_ids:
            raise ValueError("select at least one fixture")
        if len(set(fixture_ids)) != len(fixture_ids):
            raise ValueError("fixture IDs must be unique")
        if len(fixture_ids) > 4:
            raise ValueError("select no more than four fixtures")
        return fixture_ids


class SessionCreateBody(FrozenModel):
    request_id: UUID
    email: EmailStr
    fixture_ids: tuple[str, ...]
    origin: str = Field(default="London", min_length=2, max_length=100)
    adults: int = Field(default=1, ge=1, le=8)
    child_ages: tuple[int, ...] = ()
    rooms: int = Field(default=1, ge=1, le=4)
    flexibility_days: int = Field(default=1, ge=0, le=3)
    budget_tier: BudgetTier = BudgetTier.VALUE
    extra_instructions: str | None = Field(default=None, max_length=2_000)


class Money(FrozenModel):
    minor_units: int = Field(ge=0)
    currency: Literal["GBP"] = "GBP"


class BookingReference(FrozenModel):
    provider: str
    url: HttpUrl
    label: str = "Check current price"
    policy: Literal["direct_web", "refresh_in_app", "generic_search"] = "generic_search"


class TransportLeg(FrozenModel):
    kind: Literal["transport"] = "transport"
    id: str
    mode: Literal["flight", "rail", "coach", "ferry", "local_transit", "taxi", "walk"]
    origin_name: str
    destination_name: str
    origin_timezone: str
    destination_timezone: str
    departs_at: datetime
    arrives_at: datetime
    operator: str | None = None
    service_number: str | None = None
    price: Money | None = None
    price_confidence: Literal["live", "recent", "estimated", "unavailable"] = "unavailable"
    checked_at: datetime | None = None
    booking: BookingReference | None = None
    self_transfer: bool = False
    caveats: tuple[str, ...] = ()


class Stay(FrozenModel):
    kind: Literal["stay"] = "stay"
    id: str
    property_name: str
    place_name: str
    check_in: date
    check_out: date
    room_description: str | None = None
    price: Money | None = None
    price_confidence: Literal["live", "recent", "estimated", "unavailable"] = "unavailable"
    checked_at: datetime | None = None
    booking: BookingReference | None = None
    venue_transfer_note: str
    caveats: tuple[str, ...] = ()


class MatchEvent(FrozenModel):
    kind: Literal["match"] = "match"
    id: str
    fixture: FixtureSnapshot
    recommended_arrival_at: datetime
    ticket_included: Literal[False] = False


ItineraryItem = Annotated[TransportLeg | Stay | MatchEvent, Field(discriminator="kind")]


class TripAlternative(FrozenModel):
    id: str
    label: str
    summary: str
    estimated_total: Money | None = None


class FixtureTrip(FrozenModel):
    id: str
    fixture_ids: tuple[str, ...]
    title: str
    items: tuple[ItineraryItem, ...]
    alternatives: tuple[TripAlternative, ...] = ()
    estimated_total: Money | None = None
    per_person_total: Money | None = None
    tradeoffs: tuple[str, ...] = ()
    booking_order: tuple[str, ...] = ()


class Itinerary(FrozenModel):
    id: str
    revision: int = Field(ge=1)
    title: str
    summary: str
    trips: tuple[FixtureTrip, ...]
    assumptions: tuple[str, ...] = ()
    generated_at: datetime


class TranscriptMessage(FrozenModel):
    id: str
    role: Literal["user", "assistant"]
    body: str
    created_at: datetime


class SessionSnapshot(FrozenModel):
    public_id: UUID
    phase: SessionPhase
    progress: str
    state_revision: int = 0
    itinerary: Itinerary | None = None
    messages: tuple[TranscriptMessage, ...] = ()
    email_status: Literal["not_sent", "sending", "sent", "failed"] = "not_sent"
    finalization_reason: Literal["manual", "inactivity"] | None = None


class WorkflowStartInput(FrozenModel):
    public_id: UUID
    request: PlanningRequest
    fixtures: tuple[FixtureSnapshot, ...]
    inactivity_timeout_seconds: int
    planner_mode: Literal["mock", "openai"] = "mock"


class PlanActivityInput(FrozenModel):
    public_id: UUID
    request: PlanningRequest
    fixtures: tuple[FixtureSnapshot, ...]
    revision: int
    turn_id: str
    user_message: str | None = None
    planner_mode: Literal["mock", "openai"] = "mock"


class MessageCommand(FrozenModel):
    command_id: UUID
    body: str = Field(min_length=1, max_length=2_000)


class FinalizeCommand(FrozenModel):
    command_id: UUID


class CommandReceipt(FrozenModel):
    accepted: bool
    duplicate: bool = False


class EmailActivityInput(FrozenModel):
    public_id: UUID
    contact_id: UUID
    itinerary: Itinerary
    reason: Literal["manual", "inactivity"]


class EmailActivityResult(FrozenModel):
    provider_message_id: str


class StatusEvent(FrozenModel):
    type: Literal["status"] = "status"
    message: str
    state_revision: int


class TextDeltaEvent(FrozenModel):
    type: Literal["text_delta"] = "text_delta"
    turn_id: str
    attempt: int
    text: str


class TurnCommittedEvent(FrozenModel):
    type: Literal["turn_committed"] = "turn_committed"
    turn_id: str
    state_revision: int
    itinerary_revision: int


class RetryEvent(FrozenModel):
    type: Literal["retry"] = "retry"
    turn_id: str
    attempt: int


class SessionClosedEvent(FrozenModel):
    type: Literal["session_closed"] = "session_closed"
    state_revision: int


class StreamEventEnvelope(FrozenModel):
    """Common decode shape for a subscription spanning heterogeneous topics."""

    type: Literal["status", "text_delta", "turn_committed", "retry", "session_closed"]
    message: str | None = None
    state_revision: int | None = None
    turn_id: str | None = None
    attempt: int | None = None
    text: str | None = None
    itinerary_revision: int | None = None


StreamEvent = Annotated[
    StatusEvent | TextDeltaEvent | TurnCommittedEvent | RetryEvent | SessionClosedEvent,
    Field(discriminator="type"),
]
