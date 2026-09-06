"""Long-lived Entity Workflow for one supporter planning session."""

from __future__ import annotations

from datetime import timedelta
from typing import Literal

from temporalio import workflow
from temporalio.common import RetryPolicy
from temporalio.contrib.workflow_streams import WorkflowStream

with workflow.unsafe.imports_passed_through():
    from pydantic_ai.durable_exec.temporal import PydanticAIWorkflow

    from cpfc_trip.domain import (
        CommandReceipt,
        EmailActivityInput,
        FinalizeCommand,
        Itinerary,
        MessageCommand,
        PlanActivityInput,
        SessionClosedEvent,
        SessionPhase,
        SessionSnapshot,
        StatusEvent,
        TranscriptMessage,
        TurnCommittedEvent,
        WorkflowStartInput,
    )
    from cpfc_trip.planner.agent import planner_agent
    from cpfc_trip.temporal.activities import (
        build_mock_itinerary_activity,
        send_final_itinerary_email,
    )


@workflow.defn
class TravelPlanningSessionWorkflow(PydanticAIWorkflow):
    """Own the request, revisions, inactivity deadline, and final email state."""

    __pydantic_ai_agents__ = [planner_agent]

    @workflow.init
    def __init__(self, input: WorkflowStartInput) -> None:
        self._input = input
        self._phase = SessionPhase.CREATED
        self._progress = "Getting your trip brief ready…"
        self._state_revision = 0
        self._itinerary: Itinerary | None = None
        self._messages: list[TranscriptMessage] = []
        self._commands: list[MessageCommand] = []
        self._seen_commands: set[str] = set()
        self._finalize_requested = False
        self._finalization_reason: Literal["manual", "inactivity"] | None = None
        self._email_status: Literal["not_sent", "sending", "sent", "failed"] = "not_sent"
        self._last_interaction_at = workflow.now()
        self._deadline = self._last_interaction_at + timedelta(
            seconds=input.inactivity_timeout_seconds
        )

        self._stream = WorkflowStream()
        self._status_topic = self._stream.topic("status", type=StatusEvent)
        self._commit_topic = self._stream.topic("turn_committed", type=TurnCommittedEvent)
        self._closed_topic = self._stream.topic("session_closed", type=SessionClosedEvent)

    @workflow.run
    async def run(self, input: WorkflowStartInput) -> SessionSnapshot:
        await self._plan(turn_id="initial", user_message=None)

        while not self._finalize_requested:
            if self._commands:
                command = self._commands.pop(0)
                await self._plan(turn_id=str(command.command_id), user_message=command.body)
                continue

            remaining = self._deadline - workflow.now()
            if remaining <= timedelta(0):
                self._finalize_requested = True
                self._finalization_reason = "inactivity"
                break
            try:
                await workflow.wait_condition(
                    lambda: bool(self._commands) or self._finalize_requested,
                    timeout=remaining,
                    timeout_summary="wait for a supporter message or inactivity deadline",
                )
            except TimeoutError:
                self._finalize_requested = True
                self._finalization_reason = "inactivity"

        await self._finalize()
        return self._snapshot()

    @workflow.update
    def submit_message(self, command: MessageCommand) -> CommandReceipt:
        key = str(command.command_id)
        if key in self._seen_commands:
            return CommandReceipt(accepted=True, duplicate=True)
        if self._finalize_requested or self._phase in {
            SessionPhase.FINALIZING,
            SessionPhase.EMAILED,
            SessionPhase.EMAIL_FAILED,
        }:
            return CommandReceipt(accepted=False)
        self._seen_commands.add(key)
        self._commands.append(command)
        now = workflow.now()
        self._last_interaction_at = now
        self._deadline = now + timedelta(seconds=self._input.inactivity_timeout_seconds)
        self._messages.append(
            TranscriptMessage(id=key, role="user", body=command.body, created_at=now)
        )
        return CommandReceipt(accepted=True)

    @workflow.update
    def request_finalize(self, command: FinalizeCommand) -> CommandReceipt:
        key = str(command.command_id)
        if key in self._seen_commands:
            return CommandReceipt(accepted=True, duplicate=True)
        self._seen_commands.add(key)
        if self._phase in {SessionPhase.EMAILED, SessionPhase.EMAIL_FAILED}:
            return CommandReceipt(accepted=True)
        self._finalize_requested = True
        self._finalization_reason = "manual"
        return CommandReceipt(accepted=True)

    @workflow.query
    def get_snapshot(self) -> SessionSnapshot:
        return self._snapshot()

    async def _plan(self, *, turn_id: str, user_message: str | None) -> None:
        revision = 1 if self._itinerary is None else self._itinerary.revision + 1
        self._set_status(
            SessionPhase.RESEARCHING if revision == 1 else SessionPhase.REVISING,
            "Comparing routes, nearby gateways, and sensible places to stay…",
        )
        activity_input = PlanActivityInput(
            public_id=self._input.public_id,
            request=self._input.request,
            fixtures=self._input.fixtures,
            revision=revision,
            turn_id=turn_id,
            user_message=user_message,
            planner_mode=self._input.planner_mode,
        )
        if self._input.planner_mode == "openai":
            prompt = (
                "Create the next itinerary revision from this reviewed request and fixture "
                "snapshot. No live provider evidence is available yet, so omit exact prices and "
                "use only generic booking references. Input:\n" + activity_input.model_dump_json()
            )
            result = await planner_agent.run(
                prompt,
                run_id=turn_id,
                metadata={"turn_id": turn_id},
            )
            itinerary = result.output.model_copy(
                update={"revision": revision, "id": f"itinerary-{self._input.public_id}"}
            )
        else:
            itinerary = await workflow.execute_activity(
                build_mock_itinerary_activity,
                activity_input,
                start_to_close_timeout=timedelta(minutes=2),
                heartbeat_timeout=timedelta(seconds=15),
                retry_policy=RetryPolicy(
                    initial_interval=timedelta(seconds=1),
                    maximum_attempts=3,
                    backoff_coefficient=2,
                ),
                activity_id=f"plan-{turn_id}",
                summary="build a validated itinerary revision",
            )
        self._itinerary = itinerary
        assistant_body = itinerary.summary
        self._messages.append(
            TranscriptMessage(
                id=f"assistant-{turn_id}",
                role="assistant",
                body=assistant_body,
                created_at=workflow.now(),
            )
        )
        self._set_status(SessionPhase.DRAFT_READY, "Your itinerary is ready to explore.")
        self._commit_topic.publish(
            TurnCommittedEvent(
                turn_id=turn_id,
                state_revision=self._state_revision,
                itinerary_revision=itinerary.revision,
            )
        )

    async def _finalize(self) -> None:
        if self._itinerary is None:
            return
        reason = self._finalization_reason or "inactivity"
        self._set_status(SessionPhase.FINALIZING, "Preparing your itinerary email…")
        self._email_status = "sending"
        try:
            await workflow.execute_activity(
                send_final_itinerary_email,
                EmailActivityInput(
                    public_id=self._input.public_id,
                    contact_id=self._input.request.contact_id,
                    itinerary=self._itinerary,
                    reason=reason,
                ),
                start_to_close_timeout=timedelta(seconds=30),
                retry_policy=RetryPolicy(
                    initial_interval=timedelta(seconds=2),
                    maximum_attempts=5,
                    maximum_interval=timedelta(minutes=2),
                ),
                activity_id=f"email-r{self._itinerary.revision}",
                summary="send the final itinerary exactly once",
            )
        except Exception:
            self._email_status = "failed"
            self._set_status(
                SessionPhase.EMAIL_FAILED,
                "We couldn't send the email. Your itinerary is still available here.",
            )
            raise
        self._email_status = "sent"
        self._set_status(SessionPhase.EMAILED, "Your itinerary has been emailed.")
        self._closed_topic.publish(SessionClosedEvent(state_revision=self._state_revision))

    def _set_status(self, phase: SessionPhase, progress: str) -> None:
        self._phase = phase
        self._progress = progress
        self._state_revision += 1
        self._status_topic.publish(
            StatusEvent(message=progress, state_revision=self._state_revision)
        )

    def _snapshot(self) -> SessionSnapshot:
        return SessionSnapshot(
            public_id=self._input.public_id,
            phase=self._phase,
            progress=self._progress,
            state_revision=self._state_revision,
            itinerary=self._itinerary,
            messages=tuple(self._messages[-30:]),
            email_status=self._email_status,
            finalization_reason=self._finalization_reason,
        )
