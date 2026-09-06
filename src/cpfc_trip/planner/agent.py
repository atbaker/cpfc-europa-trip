"""Pydantic AI planner configuration with Temporal durability."""

from __future__ import annotations

from collections.abc import AsyncIterable
from datetime import timedelta
from typing import Any

from pydantic_ai import Agent
from pydantic_ai.durable_exec.temporal import TemporalDurability
from pydantic_ai.messages import PartDeltaEvent, PartStartEvent, TextPart, TextPartDelta
from pydantic_ai.models.openai import OpenAIResponsesModelSettings
from pydantic_ai.tools import RunContext
from temporalio import activity
from temporalio.contrib.workflow_streams import WorkflowStreamClient
from temporalio.workflow import ActivityConfig

from cpfc_trip.config import get_settings
from cpfc_trip.domain import Itinerary, TextDeltaEvent


async def publish_agent_text(ctx: RunContext[Any], events: AsyncIterable[Any]) -> None:
    """Publish only display-safe prose; never tool data, thinking, or structured JSON."""

    turn_id = str((ctx.metadata or {}).get("turn_id", "agent-turn"))
    attempt = activity.info().attempt
    stream = WorkflowStreamClient.from_within_activity(batch_interval=timedelta(milliseconds=200))
    first = True
    async with stream:
        topic = stream.topic("text_delta", type=TextDeltaEvent)
        async for event in events:
            text: str | None = None
            if isinstance(event, PartStartEvent) and isinstance(event.part, TextPart):
                text = event.part.content
            elif isinstance(event, PartDeltaEvent) and isinstance(event.delta, TextPartDelta):
                text = event.delta.content_delta
            if text:
                topic.publish(
                    TextDeltaEvent(turn_id=turn_id, attempt=attempt, text=text),
                    force_flush=first,
                )
                first = False


_settings = get_settings()

planner_agent: Agent[None, Itinerary] = Agent(
    f"openai:{_settings.openai_model}",
    output_type=Itinerary,
    name="cpfc_trip_planner_v1",
    instructions=(
        "You are a careful football away-travel planner. Return only a valid typed itinerary. "
        "Use only the fixture and normalized candidate evidence supplied in the prompt. Never "
        "invent live availability, exact prices, operators, schedules, or booking links. Preserve "
        "all provenance and uncertainty labels. Match tickets are never included."
    ),
    model_settings=OpenAIResponsesModelSettings(
        openai_reasoning_effort=_settings.openai_reasoning_effort
    ),
    capabilities=[
        TemporalDurability(
            event_stream_handler=publish_agent_text,
            model_activity_config=ActivityConfig(
                start_to_close_timeout=timedelta(minutes=4),
                heartbeat_timeout=timedelta(seconds=30),
            ),
        )
    ],
)
