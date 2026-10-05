"""One bounded session; Updates enqueue, Queries read, the main loop alone commits."""

import asyncio
from datetime import datetime, timedelta
from typing import Any

from temporalio import workflow

with workflow.unsafe.imports_passed_through():
    from pydantic_ai.durable_exec.temporal import PydanticAIWorkflow
    from pydantic_ai.usage import UsageLimits
    from temporalio.common import RetryPolicy

    from cpfc_trip.domain import (
        ChatTurn,
        Command,
        Itinerary,
        MessageCommand,
        Receipt,
        SearchBatch,
        SearchSpec,
        SessionInput,
        Snapshot,
        Trip,
    )
    from cpfc_trip.planner.agent import MODEL_SETTINGS, Intent, planner
    from cpfc_trip.planner.planning import choose, enumerate_specs
    from cpfc_trip.planner.providers.searchapi import REQUEST_CAPS, fingerprint
    from cpfc_trip.planner.recorded import sample
    from cpfc_trip.temporal.activities import (
        search_flights,
        search_stays,
        search_trains,
    )


class UnsupportedRequirements(Exception):
    pass


class PlanningServiceUnavailable(Exception):
    pass


@workflow.defn(name="TravelPlanningSessionWorkflowV3")
class TravelPlanningSessionWorkflow(PydanticAIWorkflow):
    __pydantic_ai_agents__ = [planner]

    @workflow.init
    def __init__(self, data: SessionInput):
        self.data = data
        self.pending: MessageCommand | None = None
        self.receipts: dict[str, Receipt] = {}
        self.finalize_requested = False
        self.search_reserved = 0
        self.model_reserved = 0
        self.search_cache: dict[str, SearchBatch] = {}
        self.intent = Intent(
            action="revise",
            answer="",
            private_room=data.brief.private_room,
            private_bathroom=data.brief.private_bathroom,
            transport_mode=data.brief.transport_mode,
        )
        self.brief = data.brief
        now = workflow.now()
        self.state = Snapshot(
            development_mode=data.planner_mode == "recorded",
            public_session_id=data.public_session_id,
            email_deadline=now + timedelta(seconds=data.limits.inactivity_seconds),
            interaction_deadline=now + timedelta(seconds=data.limits.interaction_seconds),
            follow_ups_remaining=data.limits.follow_ups,
        )

    def change(self, **fields: Any) -> None:
        self.state = self.state.model_copy(
            update={**fields, "state_revision": self.state.state_revision + 1}
        )

    def closed(self) -> bool:
        return (
            self.finalize_requested
            or self.state.phase in {"finalizing", "emailed", "failed", "email_failed"}
            or workflow.now() >= min(self.state.email_deadline, self.state.interaction_deadline)
            or self.state.follow_ups_remaining <= 0
        )

    @workflow.update
    def submit_message(self, command: MessageCommand) -> Receipt:
        key = str(command.id)
        if key in self.receipts:
            return self.receipts[key]
        reason = "accepted"
        if self.closed():
            reason = "closed"
        elif self.pending or self.state.active_turn_id or self.state.phase != "draft_ready":
            reason = "busy"
        elif (
            command.expected_revision is not None
            and command.expected_revision != self.state.state_revision
        ):
            reason = "stale"
        receipt = Receipt(command_id=command.id, accepted=reason == "accepted", reason=reason)
        if not receipt.accepted:
            return receipt
        self.pending = command
        self.receipts[key] = receipt
        turn = ChatTurn(
            id=f"{command.id}-user",
            turn_id=command.id,
            role="user",
            content=command.text,
            created_at=workflow.now(),
        )
        self.change(
            email_deadline=workflow.now() + timedelta(seconds=self.data.limits.inactivity_seconds),
            follow_ups_remaining=self.state.follow_ups_remaining - 1,
            transcript_tail=(*self.state.transcript_tail, turn),
            active_turn_id=command.id,
        )
        return receipt

    @workflow.update
    def request_finalize(self, command: Command) -> Receipt:
        # Finalization is one idempotent state transition; no unbounded list of finalize IDs.
        if not self.finalize_requested and self.state.phase not in {
            "emailed",
            "failed",
            "email_failed",
        }:
            self.finalize_requested = True
            self.change(
                finalization_reason="manual", progress_message="Finishing your accepted request…"
            )
        return Receipt(command_id=command.id, accepted=True)

    @workflow.query
    def get_snapshot(self, after_revision: int | None = None) -> Snapshot | None:
        if after_revision == self.state.state_revision:
            return None
        return self.state

    async def plan_turn(self, command: MessageCommand | None, turn_deadline: datetime) -> None:
        initial = command is None
        tid = command.id if command else self.data.public_session_id
        self.change(
            phase="researching" if initial else "revising",
            active_turn_id=tid,
            progress_message="Checking your travel preferences…",
        )
        if self.data.planner_mode == "recorded":
            intent = self.intent.model_copy(
                update={
                    "action": "revise" if initial else "question",
                    "answer": "This is a synthetic development example, not a live travel quote.",
                }
            )
        else:
            if self.model_reserved >= self.data.limits.model_session:
                raise ValueError("Model request budget exhausted")
            self.model_reserved += 1
            context = {
                "initial": initial,
                "brief": self.brief.model_dump(mode="json"),
                "previous_constraints": self.intent.model_dump(mode="json"),
                "itinerary": self.state.itinerary.model_dump(mode="json")
                if self.state.itinerary
                else None,
                "message": command.text if command else self.brief.extra_instructions,
            }
            try:
                result = await planner.run(
                    str(context),
                    usage_limits=UsageLimits(request_limit=1),
                    model_settings=MODEL_SETTINGS,
                )
            except Exception:
                raise PlanningServiceUnavailable from None
            intent = result.output
        if intent.unsupported_requirements:
            raise UnsupportedRequirements(
                "We cannot support these requirements yet: "
                + "; ".join(intent.unsupported_requirements)[:1500]
                + ". Your last saved draft is unchanged."
            )
        new_itinerary = self.state.itinerary
        if initial or intent.action == "revise":
            effective = self.brief.model_copy(
                update={"budget_tier": intent.budget_tier or self.brief.budget_tier}
            )
            specs = enumerate_specs(
                effective,
                self.data.fixtures,
                self.data.routes,
                recorded=self.data.planner_mode == "recorded",
            )
            specs = [
                spec.model_copy(
                    update={
                        "private_room": intent.private_room,
                        "private_bathroom": intent.private_bathroom,
                    }
                )
                for spec in specs
                if not intent.transport_mode or spec.route.mode == intent.transport_mode
            ]
            # Cache is bounded session-local workflow state, never a separate price/progress store.
            allowance = (
                self.data.limits.search_initial if initial else self.data.limits.search_follow_up
            )
            used = 0
            batches: dict[str, list[SearchBatch]] = {f.id: [] for f in self.data.fixtures}
            by_fixture = {
                f.id: [s for s in specs if s.fixture.id == f.id] for f in self.data.fixtures
            }
            waves = [
                [options[index] for options in by_fixture.values() if index < len(options)]
                for index in range(max(map(len, by_fixture.values()), default=0))
            ]
            seen: set[str] = set()
            self.change(progress_message="Comparing transport and accommodation…")
            semaphore = asyncio.Semaphore(4)

            async def acquire_job(
                key: str, kind: str, spec: SearchSpec, cap: int
            ) -> tuple[str, str, SearchBatch, int, bool]:
                fn = (
                    search_stays
                    if kind == "stay"
                    else search_flights
                    if kind == "flight"
                    else search_trains
                )
                async with semaphore:
                    try:
                        response = await workflow.execute_activity(
                            fn,
                            spec,
                            start_to_close_timeout=timedelta(seconds=85),
                            schedule_to_close_timeout=timedelta(seconds=90),
                            # A paid request may have completed before worker loss. Do not replay
                            # the whole adapter outside the reserved session call budget.
                            retry_policy=RetryPolicy(maximum_attempts=1),
                        )
                        known_calls = True
                    except Exception:
                        response = SearchBatch(gaps=("This travel search could not be completed.",))
                        known_calls = False
                return key, spec.fixture.id, response, cap, known_calls

            trips: tuple[Trip, ...] = ()
            for wave_index, wave in enumerate(waves):
                if (
                    self.data.planner_mode != "recorded"
                    and (turn_deadline - workflow.now()).total_seconds() <= 2
                ):
                    break
                jobs: list[tuple[str, str, SearchSpec, int]] = []
                for spec in wave:
                    for kind in (spec.route.mode, "stay"):
                        if self.data.planner_mode == "recorded":
                            batches[spec.fixture.id].append(sample(spec, kind))
                            continue
                        key = fingerprint(
                            (
                                spec.fixture.id,
                                kind,
                                spec.route.id if kind != "stay" else "",
                                str(spec.outbound_date),
                                str(spec.return_date),
                                spec.party.model_dump(mode="json"),
                                (spec.budget_tier, spec.private_room, spec.private_bathroom)
                                if kind == "stay"
                                else None,
                            )
                        )
                        if key in seen:
                            continue
                        seen.add(key)
                        if key in self.search_cache:
                            batches[spec.fixture.id].append(self.search_cache[key])
                            continue
                        cap = REQUEST_CAPS[kind]
                        if (
                            used + cap > allowance
                            or self.search_reserved + cap > self.data.limits.search_session
                        ):
                            continue
                        used += cap
                        self.search_reserved += cap
                        jobs.append((key, kind, spec, cap))
                responses: list[tuple[str, str, SearchBatch, int, bool]] = []
                timed_out = False
                if jobs:
                    tasks = [asyncio.create_task(acquire_job(*job)) for job in jobs]
                    done, pending = await workflow.wait(
                        tasks,
                        timeout=max(0, (turn_deadline - workflow.now()).total_seconds() - 2),
                    )
                    for task in pending:
                        task.cancel()
                    if pending:
                        await asyncio.gather(*pending, return_exceptions=True)
                        timed_out = True
                    responses = [task.result() for task in tasks if task in done]
                for key, fixture_id, response, cap, known_calls in responses:
                    if known_calls:
                        unused = cap - min(cap, response.calls)
                        used -= unused
                        self.search_reserved -= unused
                    if response.journeys or response.stays:
                        self.search_cache[key] = response
                    batches[fixture_id].append(response)
                trips = tuple(
                    choose(f, batches[f.id], effective, self.data.routes, intent)
                    for f in self.data.fixtures
                )
                if timed_out or (wave_index >= 1 and all(t.journey and t.stay for t in trips)):
                    break
            if not any(t.journey and t.stay for t in trips):
                raise ValueError("No valid draft")
            new_itinerary = Itinerary(
                revision=(self.state.itinerary.revision + 1) if self.state.itinerary else 1,
                generated_at=workflow.now(),
                trips=trips,
            )
            self.intent, self.brief = intent, effective
        answer = (
            intent.answer
            if intent.action == "question" and not initial
            else (
                "Here are the transport and stay options we could verify. Review each outstanding check before booking."
                if self.data.planner_mode == "live"
                else "Development sample only — these are synthetic trips and prices."
            )
        )
        message = ChatTurn(
            id=f"{tid}-assistant",
            turn_id=tid,
            role="assistant",
            content=answer,
            created_at=workflow.now(),
        )
        # This entire commit is synchronous. A Query sees the previous or complete new revision.
        self.change(
            itinerary=new_itinerary,
            transcript_tail=(*self.state.transcript_tail, message),
            last_committed_turn_id=tid,
            active_turn_id=None,
            phase="draft_ready",
            progress_message="Your draft is ready. Check the outstanding details before booking.",
        )

    async def bounded_turn(self, command: MessageCommand | None) -> None:
        remaining = (self.state.interaction_deadline - workflow.now()).total_seconds()
        deadline = min(
            remaining,
            self.data.limits.follow_up_seconds if command else self.data.limits.initial_seconds,
        )
        try:
            if deadline <= 0:
                raise TimeoutError
            await asyncio.wait_for(
                self.plan_turn(command, workflow.now() + timedelta(seconds=deadline)),
                timeout=deadline,
            )
        except Exception as exc:
            # Deliberately omit raw provider/model errors and preserve the last committed plan.
            tid = command.id if command else self.data.public_session_id
            if isinstance(exc, UnsupportedRequirements):
                failure_message = str(exc)
            elif isinstance(exc, PlanningServiceUnavailable):
                failure_message = (
                    "We couldn't reach the planning service. Your last saved draft is unchanged."
                    if self.state.itinerary
                    else "We couldn't reach the planning service. Please start a new trip in a moment."
                )
            elif self.state.itinerary:
                failure_message = (
                    "We couldn't complete this search within its limits. "
                    "Your last saved draft is unchanged."
                )
            else:
                failure_message = (
                    "We couldn't find a complete trip matching this request within the search "
                    "limits. Try again or adjust your preferences."
                )
            message = ChatTurn(
                id=f"{tid}-assistant",
                turn_id=tid,
                role="assistant",
                created_at=workflow.now(),
                content=failure_message,
            )
            self.change(
                active_turn_id=None,
                phase="draft_ready",
                transcript_tail=(*self.state.transcript_tail, message),
                last_committed_turn_id=tid,
                progress_message="The search could not be completed.",
            )
            if self.state.itinerary is None:
                self.finalize_requested = True
                self.change(finalization_reason="planning_failed")

    @workflow.run
    async def run(self, data: SessionInput) -> Snapshot:
        await self.bounded_turn(None)
        while not self.finalize_requested:
            if self.pending:
                command, self.pending = self.pending, None
                await self.bounded_turn(command)
                continue
            now = workflow.now()
            if (
                now >= self.state.interaction_deadline
                or self.state.follow_ups_remaining <= 0
                or self.search_reserved >= data.limits.search_session
                or self.model_reserved >= data.limits.model_session
            ):
                self.change(finalization_reason="limit")
                break
            if now >= self.state.email_deadline:
                self.change(finalization_reason="inactivity")
                break
            timeout = (
                min(self.state.email_deadline, self.state.interaction_deadline) - now
            ).total_seconds()
            try:
                await workflow.wait_condition(
                    lambda: self.pending is not None or self.finalize_requested,
                    timeout=timedelta(seconds=timeout),
                )
            except TimeoutError:
                pass
        # A manual send may arrive after a message was accepted but before the loop started it.
        if self.pending:
            command, self.pending = self.pending, None
            await self.bounded_turn(command)
        self.finalize_requested = True
        self.change(
            phase="finalizing",
            active_turn_id=None,
            email_status="pending",
            email_kind="itinerary" if self.state.itinerary else "failure_notice",
            progress_message="Preparing your email from the saved itinerary…",
        )
        frozen = self.state
        try:
            provider_id = await workflow.execute_activity(
                "deliver_itinerary",
                frozen,
                result_type=str,
                start_to_close_timeout=timedelta(seconds=30),
                schedule_to_close_timeout=timedelta(hours=23),
                retry_policy=RetryPolicy(
                    initial_interval=timedelta(seconds=5),
                    maximum_interval=timedelta(minutes=15),
                    maximum_attempts=20,
                ),
            )
            self.change(
                phase="emailed" if self.state.itinerary else "failed",
                email_status="sent",
                email_provider_id=provider_id,
                progress_message="Your email has been prepared."
                if provider_id.startswith("preview-")
                else "Your email has been submitted for delivery.",
            )
        except Exception:
            self.change(
                phase="email_failed",
                email_status="failed",
                progress_message="We couldn't confirm email delivery. Your saved draft remains visible.",
            )
        await workflow.wait_condition(workflow.all_handlers_finished)
        return self.state
