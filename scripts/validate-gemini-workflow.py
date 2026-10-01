"""Three paid Gemini calls through local Temporal; synthetic travel, no email send."""

import asyncio
import json
import logging
import shutil
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from pydantic_ai.durable_exec.temporal import PydanticAIPlugin
from temporalio import activity
from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Replayer, Worker

from cpfc_trip.catalog import load_catalog, validate_brief
from cpfc_trip.config import Settings
from cpfc_trip.domain import (
    Brief,
    Command,
    MessageCommand,
    SearchBatch,
    SearchSpec,
    SessionInput,
    Snapshot,
)
from cpfc_trip.planner.agent import configure_model, model
from cpfc_trip.planner.recorded import sample
from cpfc_trip.temporal.workflow import TravelPlanningSessionWorkflow as Workflow


@activity.defn(name="search_flights")
async def flight(spec: SearchSpec) -> SearchBatch:
    return sample(spec, "flight")


@activity.defn(name="search_stays")
async def stay(spec: SearchSpec) -> SearchBatch:
    return sample(spec, "stay")


@activity.defn(name="deliver_itinerary")
async def deliver(state: Snapshot) -> str:
    return "synthetic-delivery-no-email-sent"


async def ready(handle, previous=None):  # type: ignore[no-untyped-def]
    async with asyncio.timeout(180):
        while True:
            state = await handle.query(Workflow.get_snapshot)
            if state.phase == "draft_ready" and state.last_committed_turn_id != previous:
                return state
            if state.phase in {"failed", "email_failed"}:
                raise RuntimeError("Workflow failed; inspect local history")
            await asyncio.sleep(0.2)


async def main() -> None:
    settings = Settings()
    await configure_model(settings)
    fixtures, routes = load_catalog()
    now = datetime.now(UTC)
    brief = validate_brief(Brief(fixture_ids=(fixtures[0].id,)), fixtures, now)
    session_id = uuid4()
    data = SessionInput(
        public_session_id=session_id,
        contact_id=session_id,
        brief=brief,
        fixtures=(fixtures[0],),
        routes=(routes[0].model_copy(update={"enabled": True}),),
        planner_mode="live",
    )
    queue = str(uuid4())
    activities = [flight, stay, deliver]
    states = []
    async with await WorkflowEnvironment.start_local(
        dev_server_existing_path=shutil.which("temporal"), plugins=[PydanticAIPlugin()]
    ) as env:
        async with Worker(
            env.client, task_queue=queue, workflows=[Workflow], activities=activities
        ):
            handle = await env.client.start_workflow(
                Workflow.run, data, id=str(session_id), task_queue=queue
            )
            first = await ready(handle)
            states.append(first)
            await handle.execute_update(
                Workflow.submit_message,
                MessageCommand(id=uuid4(), text="What is included in the known total?"),
            )
            second = await ready(handle, first.last_committed_turn_id)
            assert second.itinerary == first.itinerary
            states.append(second)
        # Recreate the Worker, recover workflow state, then execute another real model turn.
        async with Worker(
            env.client, task_queue=queue, workflows=[Workflow], activities=activities
        ):
            recovered = await handle.query(Workflow.get_snapshot)
            assert recovered.itinerary == second.itinerary
            await handle.execute_update(
                Workflow.submit_message,
                MessageCommand(
                    id=uuid4(), text="Make it cheaper; dorms and shared bathrooms are fine."
                ),
            )
            third = await ready(handle, second.last_committed_turn_id)
            assert third.itinerary.revision == first.itinerary.revision + 1
            states.append(third)
            await handle.execute_update(Workflow.request_finalize, Command(id=uuid4()))
            final = await handle.result()
            assert final.phase == "emailed"
        history = await handle.fetch_history()
        await Replayer(workflows=[Workflow], plugins=[PydanticAIPlugin()]).replay_workflow(history)
        folder = Path(".data/gemini-workflow")
        await asyncio.to_thread(folder.mkdir, parents=True, exist_ok=True)
        (folder / "history.json").write_text(history.to_json())
        (folder / "results.json").write_text(
            json.dumps(
                {
                    "synthetic_travel": True,
                    "real_email_sent": False,
                    "snapshots": [s.model_dump(mode="json") for s in states],
                    "final": final.model_dump(mode="json"),
                    "replay": "passed",
                    "restart": "passed",
                },
                indent=2,
            )
        )
        print("Live Gemini initial/Q&A/revision, worker restart, finalization and replay passed.")
    await model.client.aio.aclose()


if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING)
    logging.getLogger("cpfc_trip.model_usage").setLevel(logging.INFO)
    asyncio.run(main())
