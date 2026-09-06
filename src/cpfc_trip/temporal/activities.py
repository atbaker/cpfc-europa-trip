"""Application-owned Temporal Activities."""

from __future__ import annotations

import asyncio
from datetime import timedelta

from temporalio import activity
from temporalio.contrib.workflow_streams import WorkflowStreamClient

from cpfc_trip.domain import (
    EmailActivityInput,
    EmailActivityResult,
    Itinerary,
    PlanActivityInput,
    RetryEvent,
    TextDeltaEvent,
)
from cpfc_trip.emailing import deliver_itinerary
from cpfc_trip.planner.mock import build_mock_itinerary


@activity.defn(name="build_mock_itinerary")
async def build_mock_itinerary_activity(input: PlanActivityInput) -> Itinerary:
    """Exercise the real stream path while using deterministic demo inventory."""

    info = activity.info()
    stream = WorkflowStreamClient.from_within_activity(batch_interval=timedelta(milliseconds=200))
    async with stream:
        deltas = stream.topic("text_delta", type=TextDeltaEvent)
        retries = stream.topic("retry", type=RetryEvent)
        if info.attempt > 1:
            retries.publish(
                RetryEvent(turn_id=input.turn_id, attempt=info.attempt), force_flush=True
            )
        phrases = (
            "I've compared an illustrative set of routes and stays. ",
            "Here's a coherent starting point you can refine.",
        )
        for index, phrase in enumerate(phrases):
            deltas.publish(
                TextDeltaEvent(
                    turn_id=input.turn_id,
                    attempt=info.attempt,
                    text=phrase,
                ),
                force_flush=index == 0,
            )
            await asyncio.sleep(0.15)
            activity.heartbeat(index)
    return build_mock_itinerary(input)


@activity.defn(name="send_final_itinerary_email")
async def send_final_itinerary_email(input: EmailActivityInput) -> EmailActivityResult:
    return await deliver_itinerary(input)
