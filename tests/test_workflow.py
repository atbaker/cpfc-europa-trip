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
        deadline = first.interaction_deadline
        for _ in range(3):
            assert await handle.query(Workflow.get_snapshot, first.state_revision) is None
        assert (await handle.query(Workflow.get_snapshot)).interaction_deadline == deadline
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


async def test_session_limit_closes_without_email(environment, session_input):
    emails = []

    @activity.defn(name="deliver_itinerary")
    async def deliver(state: Snapshot) -> str:
        emails.append(state)
        return "test-email"

    limits = Limits(interaction_seconds=1)
    value = session_input.model_copy(update={"limits": limits})
    queue = str(uuid4())
    async with Worker(
        environment.client, task_queue=queue, workflows=[Workflow], activities=[deliver]
    ):
        result = await environment.client.execute_workflow(
            Workflow.run, value, id=str(uuid4()), task_queue=queue
        )
    assert result.finalization_reason == "limit"
    assert result.phase == "closed"
    assert result.itinerary is not None
    assert result.email_status == "not_requested"
    assert emails == []


async def test_no_draft_finishes_without_email(environment, session_input):
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
        handle = await environment.client.start_workflow(
            Workflow.run, value, id=str(uuid4()), task_queue=queue
        )
        result = await handle.result()
    assert result.phase == "failed"
    assert result.itinerary is None
    assert result.email_kind is None
    assert result.email_status == "not_requested"
    assert result.email_provider_id is None
    assert emails == []
    history = await handle.fetch_history()
    await Replayer(workflows=[Workflow], plugins=[PydanticAIPlugin()]).replay_workflow(history)


@pytest.mark.parametrize(
    ("origin", "fixture_id", "destination", "suggest_trains", "mixed_failure"),
    [
        ("Edinburgh", "uel-2026-lyon-away", "Lyon", True, False),
        ("Nottingham", "uel-2026-jagiellonia-away", "Warsaw", False, False),
        ("Nottingham", "uel-2026-jagiellonia-away", "Warsaw", False, True),
    ],
)
async def test_no_nonstop_flights_explains_failed_city_search(
    environment,
    session_input,
    origin,
    fixture_id,
    destination,
    suggest_trains,
    mixed_failure,
):
    from datetime import UTC, datetime

    from cpfc_trip.catalog import load_catalog, validate_brief
    from cpfc_trip.domain import SearchBatch, SearchSpec
    from cpfc_trip.origins import routes_for_origin
    from cpfc_trip.planner.recorded import sample

    flight_calls = 0

    @activity.defn(name="search_flights")
    async def flights(spec: SearchSpec) -> SearchBatch:
        nonlocal flight_calls
        flight_calls += 1
        if mixed_failure and flight_calls == 2:
            return SearchBatch(
                gaps=("No complete flight and Warsaw–Białystok train connection was verified.",)
            )
        return SearchBatch(
            gaps=(
                "No nonstop or suitable one-stop flights were found for this route and date pair.",
            )
        )

    @activity.defn(name="search_stays")
    async def stays(spec: SearchSpec) -> SearchBatch:
        return sample(spec, "stay")

    emails = []

    @activity.defn(name="deliver_itinerary")
    async def deliver(state: Snapshot) -> str:
        emails.append(state)
        return "test-email"

    fixtures, catalog_routes = load_catalog()
    fixture = next(item for item in fixtures if item.id == fixture_id)
    brief = session_input.brief.model_copy(
        update={
            "origin_city": origin,
            "transport_mode": "flight",
            "fixture_ids": (fixture_id,),
            "windows": (),
        }
    )
    brief = validate_brief(brief, (fixture,), datetime.now(UTC))
    routes = routes_for_origin(
        tuple(route for route in catalog_routes if route.fixture_id == fixture_id), origin
    )
    value = session_input.model_copy(
        update={"brief": brief, "fixtures": (fixture,), "routes": routes, "planner_mode": "live"}
    )
    queue = str(uuid4())
    async with Worker(
        environment.client,
        task_queue=queue,
        workflows=[Workflow],
        activities=[flights, stays, deliver],
    ):
        handle = await environment.client.start_workflow(
            Workflow.run, value, id=str(uuid4()), task_queue=queue
        )
        result = await handle.result()
    assert result.phase == "failed" and result.email_kind is None
    assert result.email_status == "not_requested" and emails == []
    if mixed_failure:
        assert "No nonstop or suitable one-stop flights" not in result.transcript_tail[-1].content
        assert "couldn't find a complete trip" in result.transcript_tail[-1].content
        return
    assert (
        f"No nonstop or suitable one-stop flights were found from {origin} to {destination}"
        in result.transcript_tail[-1].content
    )
    assert ("Try trains" in result.transcript_tail[-1].content) is suggest_trains
    if destination == "Warsaw":
        assert "train to Białystok" in result.transcript_tail[-1].content


@pytest.mark.parametrize("available_airport", ["LHR", "LGW"])
async def test_airport_preference_uses_verified_fallback_only_when_needed(
    environment, session_input, monkeypatch, available_airport
):
    import json

    from google.genai.types import GenerateContentResponse

    from cpfc_trip.domain import SearchBatch, SearchSpec
    from cpfc_trip.planner.agent import model
    from cpfc_trip.planner.recorded import sample

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
                                            "answer": "",
                                            "preferred_airports": ["LGW"],
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
        batch = sample(spec, "flight")
        journey = batch.journeys[0]
        outbound = journey.outbound[0].model_copy(update={"origin": available_airport})
        inbound = journey.inbound[0].model_copy(update={"destination": available_airport})
        return SearchBatch(
            journeys=(journey.model_copy(update={"outbound": (outbound,), "inbound": (inbound,)}),)
        )

    @activity.defn(name="search_stays")
    async def stays(spec: SearchSpec) -> SearchBatch:
        return sample(spec, "stay")

    @activity.defn(name="deliver_itinerary")
    async def deliver(state: Snapshot) -> str:
        return "test-email"

    value = session_input.model_copy(
        update={
            "planner_mode": "live",
            "brief": session_input.brief.model_copy(
                update={"extra_instructions": "Gatwick only, please."}
            ),
            "routes": (session_input.routes[0].model_copy(update={"enabled": True}),),
        }
    )
    queue = str(uuid4())
    async with Worker(
        environment.client,
        task_queue=queue,
        workflows=[Workflow],
        activities=[flights, stays, deliver],
    ):
        handle = await environment.client.start_workflow(
            Workflow.run, value, id=str(uuid4()), task_queue=queue
        )
        state = await ready(handle)
        assert state.itinerary is not None
        trip = state.itinerary.trips[0]
        assert trip.journey and trip.journey.outbound[0].origin == available_airport
        if available_airport == "LHR":
            assert "couldn't accommodate" in trip.summary
            assert "LGW" in trip.summary and "LHR" in trip.summary
        else:
            assert "couldn't accommodate" not in trip.summary
        await handle.execute_update(Workflow.request_finalize, Command(id=uuid4()))
        await handle.result()
    await Replayer(workflows=[Workflow], plugins=[PydanticAIPlugin()]).replay_workflow(
        await handle.fetch_history()
    )


@pytest.mark.parametrize(
    ("reason", "expected"),
    [
        ("no_stay", "couldn't verify a stay"),
        ("late_return", "match timing and connection checks"),
        ("no_route", "no dated return journey was verified"),
    ],
)
async def test_no_complete_trip_explains_evidence_gap(environment, session_input, reason, expected):
    from datetime import timedelta

    from cpfc_trip.domain import SearchBatch, SearchSpec
    from cpfc_trip.planner.recorded import sample

    @activity.defn(name="search_flights")
    async def flights(spec: SearchSpec) -> SearchBatch:
        if reason == "no_route":
            return SearchBatch(gaps=("Complete outbound and return flights were not available.",))
        batch = sample(spec, "flight")
        if reason == "late_return":
            journey = batch.journeys[0]
            inbound = journey.inbound[0].model_copy(
                update={
                    "departs_at": spec.fixture.kickoff_at,
                    "arrives_at": spec.fixture.kickoff_at + timedelta(hours=2),
                }
            )
            return SearchBatch(journeys=(journey.model_copy(update={"inbound": (inbound,)}),))
        return batch

    @activity.defn(name="search_stays")
    async def stays(spec: SearchSpec) -> SearchBatch:
        return SearchBatch() if reason == "no_stay" else sample(spec, "stay")

    @activity.defn(name="deliver_itinerary")
    async def deliver(state: Snapshot) -> str:
        pytest.fail("A failed search must not send an email")

    value = session_input.model_copy(
        update={
            "planner_mode": "live",
            "routes": (session_input.routes[0].model_copy(update={"enabled": True}),),
        }
    )
    queue = str(uuid4())
    async with Worker(
        environment.client,
        task_queue=queue,
        workflows=[Workflow],
        activities=[flights, stays, deliver],
    ):
        handle = await environment.client.start_workflow(
            Workflow.run, value, id=str(uuid4()), task_queue=queue
        )
        for _ in range(100):
            state = await handle.query(Workflow.get_snapshot)
            if state.phase in {"draft_ready", "failed"}:
                break
            await asyncio.sleep(0.05)
        else:
            pytest.fail("Search did not finish")
        assert state.phase == "failed", state
        result = await handle.result()
    assert result.phase == "failed" and result.email_status == "not_requested"
    assert expected in result.transcript_tail[-1].content


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

    value = session_input.model_copy(
        update={
            "planner_mode": "live",
            "routes": (),
            "brief": session_input.brief.model_copy(
                update={"extra_instructions": "Please consider my request."}
            ),
        }
    )
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


async def test_model_failure_is_not_reported_as_search_exhaustion(
    environment, session_input, monkeypatch
):
    from cpfc_trip.planner.agent import model

    async def unavailable(**kwargs):
        raise RuntimeError("simulated private provider detail")

    monkeypatch.setattr(model.client.aio.models, "generate_content", unavailable)

    @activity.defn(name="deliver_itinerary")
    async def deliver(state: Snapshot) -> str:
        return "test-email"

    value = session_input.model_copy(
        update={
            "planner_mode": "live",
            "brief": session_input.brief.model_copy(
                update={"extra_instructions": "Please consider my request."}
            ),
        }
    )
    queue = str(uuid4())
    async with Worker(
        environment.client, task_queue=queue, workflows=[Workflow], activities=[deliver]
    ):
        result = await environment.client.execute_workflow(
            Workflow.run, value, id=str(uuid4()), task_queue=queue
        )
    assert result.phase == "failed"
    assert "planning service" in result.transcript_tail[-1].content.lower()
    assert "search limits" not in result.transcript_tail[-1].content.lower()
    assert "private provider detail" not in result.transcript_tail[-1].content


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
        assert count == 4  # Two waves give one verified option and one comparison.
        assert searches[0][1:] == searches[1][1:]
        assert searches[2][1:] == searches[3][1:]
        assert searches[0][1:] != searches[2][1:]
    async with Worker(
        environment.client, task_queue=queue, workflows=[Workflow], activities=activities
    ):
        await handle.execute_update(
            Workflow.submit_message, MessageCommand(id=uuid4(), text="Keep it cheap.")
        )
        second = await ready(handle)
        assert second.itinerary.revision == first.itinerary.revision + 1
        # A budget change refreshes hotel preferences while keeping transport evidence.
        assert [search for search in searches if search[0] == "flight"] == [
            search for search in searches[:count] if search[0] == "flight"
        ]
        assert len(searches) == count + 2
        await handle.execute_update(Workflow.request_finalize, Command(id=uuid4()))
        await handle.result()
    await Replayer(workflows=[Workflow], plugins=[PydanticAIPlugin()]).replay_workflow(
        await handle.fetch_history()
    )
    assert len(searches) == count + 2


async def test_live_search_retries_once_after_lost_attempt(environment, session_input):
    """A retryable lost attempt is recovered within the existing turn."""
    from cpfc_trip.domain import SearchBatch, SearchSpec
    from cpfc_trip.planner.recorded import sample

    attempts: list[int] = []

    @activity.defn(name="search_flights")
    async def flights(spec: SearchSpec) -> SearchBatch:
        attempt = activity.info().attempt
        attempts.append(attempt)
        if attempt == 1 and len(attempts) == 1:
            raise RuntimeError("simulated worker loss")
        return sample(spec, "flight").model_copy(update={"calls": 16 if attempt > 1 else 0})

    @activity.defn(name="search_stays")
    async def stays(spec: SearchSpec) -> SearchBatch:
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
    async with Worker(
        environment.client,
        task_queue=queue,
        workflows=[Workflow],
        activities=[flights, stays, deliver],
    ):
        handle = await environment.client.start_workflow(
            Workflow.run, value, id=str(uuid4()), task_queue=queue
        )
        result = await ready(handle)
    assert result.itinerary is not None
    assert attempts[:2] == [1, 2]


async def test_second_worker_recovers_a_search_when_first_worker_stops(environment, session_input):
    """A lost in-flight Activity can resume on another poller without losing the plan."""
    from datetime import timedelta

    from cpfc_trip.domain import SearchBatch, SearchSpec
    from cpfc_trip.planner.recorded import sample

    first_started = asyncio.Event()
    recovered = asyncio.Event()

    @activity.defn(name="search_flights")
    async def interrupted_flight(spec: SearchSpec) -> SearchBatch:
        activity.heartbeat()
        first_started.set()
        while True:
            await asyncio.sleep(1)
            activity.heartbeat()

    @activity.defn(name="search_flights")
    async def recovered_flight(spec: SearchSpec) -> SearchBatch:
        assert activity.info().attempt == 2
        recovered.set()
        return sample(spec, "flight").model_copy(update={"calls": 16})

    @activity.defn(name="search_stays")
    async def stays(spec: SearchSpec) -> SearchBatch:
        return sample(spec, "stay")

    @activity.defn(name="deliver_itinerary")
    async def deliver(state: Snapshot) -> str:
        return "test-email"

    value = session_input.model_copy(
        update={
            "planner_mode": "live",
            "limits": Limits(initial_seconds=60, interaction_seconds=70),
            "routes": (session_input.routes[0].model_copy(update={"enabled": True}),),
        }
    )
    queue = str(uuid4())
    async with Worker(
        environment.client,
        task_queue=queue,
        workflows=[Workflow],
        activities=[interrupted_flight, stays, deliver],
        graceful_shutdown_timeout=timedelta(0),
    ) as first_worker:
        handle = await environment.client.start_workflow(
            Workflow.run, value, id=str(uuid4()), task_queue=queue
        )
        await asyncio.wait_for(first_started.wait(), timeout=5)
        await first_worker.shutdown()
        async with Worker(
            environment.client,
            task_queue=queue,
            workflows=[Workflow],
            activities=[recovered_flight, stays, deliver],
        ):
            await asyncio.wait_for(recovered.wait(), timeout=25)
            for _ in range(100):
                result = await handle.query(Workflow.get_snapshot)
                if result.itinerary:
                    break
                await asyncio.sleep(0.05)
            assert result.itinerary is not None


async def test_slow_comparison_keeps_first_complete_wave(environment, session_input):
    from cpfc_trip.domain import SearchBatch, SearchSpec
    from cpfc_trip.planner.planning import enumerate_specs
    from cpfc_trip.planner.recorded import sample

    first_spec = enumerate_specs(session_input.brief, session_input.fixtures, session_input.routes)[
        0
    ]
    first_dates = (first_spec.outbound_date, first_spec.return_date)

    @activity.defn(name="search_flights")
    async def flights(spec: SearchSpec) -> SearchBatch:
        if (spec.outbound_date, spec.return_date) != first_dates:
            await asyncio.sleep(6)
        return sample(spec, "flight")

    @activity.defn(name="search_stays")
    async def stays(spec: SearchSpec) -> SearchBatch:
        if (spec.outbound_date, spec.return_date) != first_dates:
            await asyncio.sleep(6)
        return sample(spec, "stay")

    @activity.defn(name="deliver_itinerary")
    async def deliver(state: Snapshot) -> str:
        return "test-email"

    value = session_input.model_copy(
        update={
            "planner_mode": "live",
            "limits": Limits(initial_seconds=5),
            "routes": (session_input.routes[0].model_copy(update={"enabled": True}),),
        }
    )
    queue = str(uuid4())
    async with Worker(
        environment.client,
        task_queue=queue,
        workflows=[Workflow],
        activities=[flights, stays, deliver],
    ):
        handle = await environment.client.start_workflow(
            Workflow.run, value, id=str(uuid4()), task_queue=queue
        )
        state = await ready(handle)
        assert state.itinerary and state.itinerary.trips[0].journey
        assert state.itinerary.trips[0].stay
        await handle.execute_update(Workflow.request_finalize, Command(id=uuid4()))
        await handle.result()


async def test_first_journey_is_visible_while_hotel_search_continues(
    environment, session_input, monkeypatch
):
    from cpfc_trip.domain import SearchBatch, SearchSpec
    from cpfc_trip.planner.agent import model
    from cpfc_trip.planner.recorded import sample

    async def fake_model(**kwargs):
        raise AssertionError("Structured form inputs should not need Gemini")

    monkeypatch.setattr(model.client.aio.models, "generate_content", fake_model)
    hotel_started = asyncio.Event()
    release_hotel = asyncio.Event()

    @activity.defn(name="search_flights")
    async def flights(spec: SearchSpec) -> SearchBatch:
        return sample(spec, "flight")

    @activity.defn(name="search_stays")
    async def stays(spec: SearchSpec) -> SearchBatch:
        hotel_started.set()
        await release_hotel.wait()
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
    async with Worker(
        environment.client,
        task_queue=queue,
        workflows=[Workflow],
        activities=[flights, stays, deliver],
    ):
        handle = await environment.client.start_workflow(
            Workflow.run, value, id=str(uuid4()), task_queue=queue
        )
        await asyncio.wait_for(hotel_started.wait(), timeout=5)
        for _ in range(50):
            state = await handle.query(Workflow.get_snapshot)
            if state.preview_trip:
                break
            await asyncio.sleep(0.05)
        assert state.phase == "researching"
        assert state.itinerary is None
        assert state.preview_trip is not None
        assert state.preview_trip.journey is not None
        assert state.preview_trip.stay is None
        release_hotel.set()
        completed = await ready(handle)
        assert completed.itinerary and completed.itinerary.trips[0].stay
        assert completed.preview_trip is None
        await handle.execute_update(Workflow.request_finalize, Command(id=uuid4()))
        await handle.result()
