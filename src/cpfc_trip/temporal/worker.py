import asyncio
import logging
import signal
from datetime import timedelta

from temporalio.common import VersioningBehavior, WorkerDeploymentVersion
from temporalio.worker import Worker, WorkerDeploymentConfig

from cpfc_trip.config import Settings
from cpfc_trip.persistence.database import engine
from cpfc_trip.persistence.repository import Repository
from cpfc_trip.planner.agent import configure_model, model
from cpfc_trip.temporal.activities import (
    DeliveryActivities,
    search_flights,
    search_stays,
    search_trains,
)
from cpfc_trip.temporal.client import connect
from cpfc_trip.temporal.workflow import TravelPlanningSessionWorkflow


async def run() -> None:
    settings = Settings()
    if settings.planner_mode == "live":
        await configure_model(settings)
    db = engine(settings)
    try:
        client = await connect(settings)
        delivery = DeliveryActivities(Repository(db, settings))
        deployment = (
            WorkerDeploymentConfig(
                version=WorkerDeploymentVersion(
                    deployment_name="cpfc-trip", build_id=settings.worker_build_id
                ),
                use_worker_versioning=True,
                default_versioning_behavior=VersioningBehavior.PINNED,
            )
            if settings.worker_build_id
            else None
        )
        stop = asyncio.Event()
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, stop.set)
        async with Worker(
            client,
            task_queue=settings.temporal_task_queue,
            workflows=[TravelPlanningSessionWorkflow],
            activities=[search_flights, search_trains, search_stays, delivery.deliver_itinerary],
            deployment_config=deployment,
            max_concurrent_activities=16,
            graceful_shutdown_timeout=timedelta(seconds=25),
        ):
            await stop.wait()
    finally:
        await db.dispose()
        await model.client.aio.aclose()


def main() -> None:
    logging.basicConfig(level=logging.WARNING)
    logging.getLogger("cpfc_trip.model_usage").setLevel(logging.INFO)
    asyncio.run(run())
