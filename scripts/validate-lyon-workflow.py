"""Paid live Lyon validation: bounded SearchApi/Gemini calls; preview email only."""

import argparse
import asyncio
import json
import logging
import shutil
import time
from pathlib import Path
from uuid import uuid4

from pydantic_ai.durable_exec.temporal import PydanticAIPlugin
from temporalio.client import WorkflowHistory
from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Replayer, Worker

from cpfc_trip.catalog import load_catalog
from cpfc_trip.config import Settings
from cpfc_trip.domain import Brief, Command, CreateSession, MessageCommand
from cpfc_trip.persistence.database import engine
from cpfc_trip.persistence.repository import Repository
from cpfc_trip.planner.agent import configure_model, model
from cpfc_trip.temporal.activities import (
    DeliveryActivities,
    search_flights,
    search_stays,
    search_trains,
)
from cpfc_trip.temporal.workflow import TravelPlanningSessionWorkflow as Workflow


async def ready(handle, previous=None):  # type: ignore[no-untyped-def]
    async with asyncio.timeout(210):
        while True:
            state = await handle.query(Workflow.get_snapshot)
            if state.phase == "draft_ready" and state.last_committed_turn_id != previous:
                return state
            if state.phase in {"failed", "email_failed", "emailed"}:
                raise RuntimeError(f"Unexpected phase: {state.phase}")
            await asyncio.sleep(1)


async def main() -> None:
    settings = Settings(planner_mode="live", email_mode="preview")
    await configure_model(settings)
    db = engine(settings)
    repo = Repository(db, settings)
    fixture = next(f for f in load_catalog()[0] if f.city == "Lyon")
    data = await repo.create(
        CreateSession(
            submission_id=uuid4(),
            email="lyon-validation@example.com",
            brief=Brief(fixture_ids=(fixture.id,)),
        ),
        str(uuid4()),
    )
    delivery = DeliveryActivities(repo)
    activities = [search_flights, search_stays, search_trains, delivery.deliver_itinerary]
    queue = str(uuid4())
    states, timings = [], {}
    folder = Path(".data/lyon-live-workflow")
    await asyncio.to_thread(folder.mkdir, parents=True, exist_ok=True)
    try:
        async with await WorkflowEnvironment.start_local(
            dev_server_existing_path=shutil.which("temporal"), plugins=[PydanticAIPlugin()]
        ) as env:
            async with Worker(
                env.client, task_queue=queue, workflows=[Workflow], activities=activities
            ):
                start = time.monotonic()
                handle = await env.client.start_workflow(
                    Workflow.run, data, id=str(data.public_session_id), task_queue=queue
                )
                try:
                    first = await ready(handle)
                finally:
                    (folder / "history.json").write_text((await handle.fetch_history()).to_json())
                timings["initial_seconds"] = round(time.monotonic() - start, 2)
                assert first.itinerary and first.itinerary.trips[0].journey
                states.append(first)
                print(f"Initial live draft: {timings['initial_seconds']} seconds", flush=True)
                await handle.execute_update(
                    Workflow.submit_message,
                    MessageCommand(id=uuid4(), text="What is included in the known total?"),
                )
                second = await ready(handle, first.last_committed_turn_id)
                assert second.itinerary == first.itinerary
                states.append(second)
                print("Q&A preserved the itinerary", flush=True)
            async with Worker(
                env.client, task_queue=queue, workflows=[Workflow], activities=activities
            ):
                recovered = await handle.query(Workflow.get_snapshot)
                assert recovered.itinerary == second.itinerary
                start = time.monotonic()
                await handle.execute_update(
                    Workflow.submit_message,
                    MessageCommand(
                        id=uuid4(),
                        text="Use trains only, no flights, and make it cheaper. Dorms and shared bathrooms are fine.",
                    ),
                )
                third = await ready(handle, second.last_committed_turn_id)
                timings["revision_seconds"] = round(time.monotonic() - start, 2)
                assert third.itinerary and third.itinerary.revision == first.itinerary.revision + 1
                trip = third.itinerary.trips[0]
                assert trip.journey and all(
                    leg.mode == "rail" for leg in trip.journey.outbound + trip.journey.inbound
                )
                states.append(third)
                print(
                    f"Restart and train-only revision: {timings['revision_seconds']} seconds",
                    flush=True,
                )
                await handle.execute_update(Workflow.request_finalize, Command(id=uuid4()))
                final = await handle.result()
                assert final.phase == "emailed"
                receipt = await delivery.deliver_itinerary(final)
                assert receipt.startswith("preview-")
            history = await handle.fetch_history()
            (folder / "history.json").write_text(history.to_json())
            await Replayer(workflows=[Workflow], plugins=[PydanticAIPlugin()]).replay_workflow(
                history
            )
            (folder / "results.json").write_text(
                json.dumps(
                    {
                        "real_travel": True,
                        "real_email_sent": False,
                        "snapshots": [s.model_dump(mode="json") for s in states],
                        "final": final.model_dump(mode="json"),
                        "timings": timings,
                        "restart": "passed",
                        "replay": "passed",
                        "preview_receipt": receipt,
                    },
                    indent=2,
                )
            )
            print("Live draft, Q&A, restart, rail revision, idempotent preview and replay passed.")
    finally:
        await db.dispose()
        await model.client.aio.aclose()


async def replay_only() -> None:
    history = WorkflowHistory.from_json(
        "lyon-saved-validation",
        await asyncio.to_thread(Path(".data/lyon-live-workflow/history.json").read_text),
    )
    await Replayer(workflows=[Workflow], plugins=[PydanticAIPlugin()]).replay_workflow(history)
    print("Saved live Lyon history replay passed; no model, search or email requests.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--replay-only", action="store_true", help="Replay saved history without paid calls"
    )
    args = parser.parse_args()
    logging.basicConfig(level=logging.WARNING)
    logging.getLogger("cpfc_trip.model_usage").setLevel(logging.INFO)
    asyncio.run(replay_only() if args.replay_only else main())
