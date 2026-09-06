"""Temporal Worker process."""

from __future__ import annotations

import asyncio
import signal

from temporalio.worker import Worker

from cpfc_trip.config import get_settings
from cpfc_trip.observability import instrument_planner
from cpfc_trip.planner.agent import planner_agent
from cpfc_trip.temporal.activities import (
    build_mock_itinerary_activity,
    send_final_itinerary_email,
)
from cpfc_trip.temporal.client import connect_temporal
from cpfc_trip.temporal.workflow import TravelPlanningSessionWorkflow


async def serve() -> None:
    settings = get_settings()
    if settings.planner_mode == "openai" and not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY is required when PLANNER_MODE=openai")
    if settings.email_mode == "resend" and not settings.resend_api_key:
        raise RuntimeError("RESEND_API_KEY is required when EMAIL_MODE=resend")
    instrument_planner(planner_agent)
    client = await connect_temporal()
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop.set)

    worker = Worker(
        client,
        task_queue=settings.temporal_task_queue,
        workflows=[TravelPlanningSessionWorkflow],
        activities=[build_mock_itinerary_activity, send_final_itinerary_email],
    )
    async with worker:
        await stop.wait()


def run() -> None:
    asyncio.run(serve())
