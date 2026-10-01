import asyncio
import shutil
from uuid import uuid4

import pytest
from pydantic_ai.durable_exec.temporal import PydanticAIPlugin
from temporalio import activity
from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Replayer, Worker

from cpfc_trip.domain import Command, Limits, MessageCommand, Snapshot
from cpfc_trip.temporal.workflow import TravelPlanningSessionWorkflow as Workflow


@pytest.fixture
async def environment():
    async with await WorkflowEnvironment.start_local(
        dev_server_existing_path=shutil.which("temporal"), plugins=[PydanticAIPlugin()]
    ) as env:
        yield env


async def ready(handle):
    for _ in range(100):
        state = await handle.query(Workflow.get_snapshot)
        if state.phase == "draft_ready":
            return state
        if state.phase in {"failed", "email_failed"}:
            pytest.fail(str(state))
        await asyncio.sleep(0.05)
    pytest.fail("Draft did not become ready")


async def test_manual_dedup_query_replay_and_restart(environment, session_input):
    emails = []

    @activity.defn(name="deliver_itinerary")
    async def deliver(state: Snapshot) -> str:
        emails.append(state)
        return "test-email"

    queue = str(uuid4())
    async with Worker(
        environment.client, task_queue=queue, workflows=[Workflow], activities=[deliver]
    ):
        handle = await environment.client.start_workflow(
            Workflow.run, session_input, id=str(uuid4()), task_queue=queue
        )
        first = await ready(handle)
        assert first.itinerary and first.itinerary.revision == 1
        deadline = first.email_deadline
        for _ in range(3):
            assert await handle.query(Workflow.get_snapshot, first.state_revision) is None
        assert (await handle.query(Workflow.get_snapshot)).email_deadline == deadline
        cmd = MessageCommand(id=uuid4(), text="What's included?")
        receipt = await handle.execute_update(Workflow.submit_message, cmd)
        assert receipt.accepted
        assert await handle.execute_update(Workflow.submit_message, cmd) == receipt
        second = await ready(handle)
        assert second.follow_ups_remaining == 9
    # No worker-side in-memory state survives this fresh Worker instance.
    async with Worker(
        environment.client, task_queue=queue, workflows=[Workflow], activities=[deliver]
    ):
        recovered = await handle.query(Workflow.get_snapshot)
        assert recovered.itinerary == second.itinerary
        await handle.execute_update(Workflow.request_finalize, Command(id=uuid4()))
        result = await handle.result()
    assert result.phase == "emailed" and len(emails) == 1
    assert emails[0].itinerary == first.itinerary
    history = await handle.fetch_history()
    await Replayer(workflows=[Workflow], plugins=[PydanticAIPlugin()]).replay_workflow(history)
    assert len(result.model_dump_json().encode()) < 100_000


@pytest.mark.parametrize("reason", ["inactivity", "limit"])
async def test_automatic_finalization(environment, session_input, reason):
    emails = []

    @activity.defn(name="deliver_itinerary")
    async def deliver(state: Snapshot) -> str:
        emails.append(state)
        return "test-email"

    limits = Limits(
        inactivity_seconds=1 if reason == "inactivity" else 600,
        interaction_seconds=1 if reason == "limit" else 1800,
    )
    value = session_input.model_copy(update={"limits": limits})
    queue = str(uuid4())
    async with Worker(
        environment.client, task_queue=queue, workflows=[Workflow], activities=[deliver]
    ):
        result = await environment.client.execute_workflow(
            Workflow.run, value, id=str(uuid4()), task_queue=queue
        )
    assert result.finalization_reason == reason and len(emails) == 1


async def test_no_draft_sends_failure_notice(environment, session_input):
    emails = []

    @activity.defn(name="deliver_itinerary")
    async def deliver(state: Snapshot) -> str:
        emails.append(state)
        return "test-email"

    value = session_input.model_copy(update={"routes": ()})
    queue = str(uuid4())
    async with Worker(
        environment.client, task_queue=queue, workflows=[Workflow], activities=[deliver]
    ):
        result = await environment.client.execute_workflow(
            Workflow.run, value, id=str(uuid4()), task_queue=queue
        )
    assert result.phase == "failed" and result.email_kind == "failure_notice" and len(emails) == 1


async def test_durable_pydantic_model_and_query_during_activity(
    environment, session_input, monkeypatch
):
    import json

    from google.genai.types import GenerateContentResponse

    from cpfc_trip.planner.agent import model

    calls = []

    async def fake_response(**kwargs):
        calls.append(kwargs)
        await asyncio.sleep(0.3)
        return GenerateContentResponse.model_validate(
            {
                "modelVersion": "gemini-3.8-flash",
                "candidates": [
                    {
                        "finishReason": "STOP",
                        "content": {
                            "role": "model",
                            "parts": [
                                {
                                    "text": json.dumps(
                                        {
                                            "action": "revise",
                                            "answer": "The request is being checked.",
                                        }
                                    )
                                }
                            ],
                        },
                    }
                ],
                "usageMetadata": {
                    "promptTokenCount": 100,
                    "candidatesTokenCount": 30,
                    "thoughtsTokenCount": 20,
                    "totalTokenCount": 150,
                },
            }
        )

    monkeypatch.setattr(model.client.aio.models, "generate_content", fake_response)

    @activity.defn(name="deliver_itinerary")
    async def deliver(state: Snapshot) -> str:
        return "test-email"

    value = session_input.model_copy(update={"planner_mode": "live", "routes": ()})
    queue = str(uuid4())
    async with Worker(
        environment.client, task_queue=queue, workflows=[Workflow], activities=[deliver]
    ):
        handle = await environment.client.start_workflow(
            Workflow.run, value, id=str(uuid4()), task_queue=queue
        )
        for _ in range(50):
            if calls:
                break
            await asyncio.sleep(0.02)
        snapshot = await handle.query(Workflow.get_snapshot)
        assert snapshot.phase == "researching" and snapshot.itinerary is None
        result = await handle.result()
    assert result.phase == "failed"  # No routes; the model cannot manufacture an itinerary.
    assert len(calls) == 1
    assert calls[0]["config"]["thinking_config"]["thinking_level"] == "LOW"
    assert calls[0]["config"]["max_output_tokens"] == 4096
    history = await handle.fetch_history()
    await Replayer(workflows=[Workflow], plugins=[PydanticAIPlugin()]).replay_workflow(history)
    assert len(calls) == 1  # Replay uses the completed model Activity result.


async def test_live_revision_reuses_searches_after_worker_restart(
    environment, session_input, monkeypatch
):
    import json

    from google.genai.types import GenerateContentResponse

    from cpfc_trip.domain import SearchBatch, SearchSpec
    from cpfc_trip.planner.agent import model
    from cpfc_trip.planner.recorded import sample

    searches = []

    async def fake_model(**kwargs):
        return GenerateContentResponse.model_validate(
            {
                "candidates": [
                    {
                        "finishReason": "STOP",
                        "content": {
                            "role": "model",
                            "parts": [
                                {
                                    "text": json.dumps(
                                        {
                                            "action": "revise",
                                            "answer": "Falsely announced success",
                                            "budget_tier": "budget",
                                        }
                                    )
                                }
                            ],
                        },
                    }
                ]
            }
        )

    monkeypatch.setattr(model.client.aio.models, "generate_content", fake_model)

    @activity.defn(name="search_flights")
    async def flights(spec: SearchSpec) -> SearchBatch:
        searches.append(("flight", spec.outbound_date, spec.return_date))
        return sample(spec, "flight")

    @activity.defn(name="search_stays")
    async def stays(spec: SearchSpec) -> SearchBatch:
        searches.append(("stay", spec.outbound_date, spec.return_date))
        return sample(spec, "stay")

    @activity.defn(name="deliver_itinerary")
    async def deliver(state: Snapshot) -> str:
        return "test-email"

    value = session_input.model_copy(
        update={
            "planner_mode": "live",
            "routes": (session_input.routes[0].model_copy(update={"enabled": True}),),
        }
    )
    queue = str(uuid4())
    activities = [flights, stays, deliver]
    async with Worker(
        environment.client, task_queue=queue, workflows=[Workflow], activities=activities
    ):
        handle = await environment.client.start_workflow(
            Workflow.run, value, id=str(uuid4()), task_queue=queue
        )
        first = await ready(handle)
        assert "Falsely" not in first.transcript_tail[-1].content
        count = len(searches)
        assert count == 6  # Three date pairs; each hotel search runs only once.
    async with Worker(
        environment.client, task_queue=queue, workflows=[Workflow], activities=activities
    ):
        await handle.execute_update(
            Workflow.submit_message, MessageCommand(id=uuid4(), text="Keep it cheap.")
        )
        second = await ready(handle)
        assert second.itinerary.revision == first.itinerary.revision + 1
        assert len(searches) == count
        await handle.execute_update(Workflow.request_finalize, Command(id=uuid4()))
        await handle.result()
    await Replayer(workflows=[Workflow], plugins=[PydanticAIPlugin()]).replay_workflow(
        await handle.fetch_history()
    )
    assert len(searches) == count
