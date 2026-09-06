"""Fast deterministic baseline for the planner's core tier behavior."""

from __future__ import annotations

import asyncio
from typing import Literal
from uuid import UUID

from pydantic_evals import Case, Dataset
from pydantic_evals.evaluators import EqualsExpected

from cpfc_trip.domain import (
    BudgetTier,
    FrozenModel,
    PlanActivityInput,
    PlanningRequest,
    Stay,
    TransportLeg,
)
from cpfc_trip.fixtures import fixtures_by_id
from cpfc_trip.planner.mock import build_mock_itinerary


class PlannerEvalInput(FrozenModel):
    starting_tier: BudgetTier
    user_message: str | None = None


class PlannerEvalOutput(FrozenModel):
    transport_mode: Literal["flight", "rail"]
    room_description: str
    self_transfer: bool
    per_person_minor_units: int


def evaluate_planner_case(input: PlannerEvalInput) -> PlannerEvalOutput:
    fixture_ids = ("uel-2026-besiktas-away",)
    plan = build_mock_itinerary(
        PlanActivityInput(
            public_id=UUID("00000000-0000-0000-0000-000000000001"),
            request=PlanningRequest(
                fixture_ids=fixture_ids,
                budget_tier=input.starting_tier,
                contact_id=UUID("00000000-0000-0000-0000-000000000002"),
                request_id=UUID("00000000-0000-0000-0000-000000000003"),
            ),
            fixtures=fixtures_by_id(fixture_ids),
            revision=1,
            turn_id="eval",
            user_message=input.user_message,
        )
    )
    trip = plan.trips[0]
    outbound = trip.items[0]
    stay = trip.items[1]
    if not isinstance(outbound, TransportLeg) or not isinstance(stay, Stay):
        raise AssertionError("planner emitted an unexpected itinerary shape")
    if outbound.mode not in {"flight", "rail"}:
        raise AssertionError("baseline fixture should use flight or rail")
    if stay.room_description is None or trip.per_person_total is None:
        raise AssertionError("baseline fixture should include room and per-person estimate")
    return PlannerEvalOutput(
        transport_mode=outbound.mode,
        room_description=stay.room_description,
        self_transfer=outbound.self_transfer,
        per_person_minor_units=trip.per_person_total.minor_units,
    )


DATASET: Dataset[PlannerEvalInput, PlannerEvalOutput, None] = Dataset(
    name="cpfc-mock-planner-tier-behavior",
    cases=(
        Case(
            name="value-default",
            inputs=PlannerEvalInput(starting_tier=BudgetTier.VALUE),
            expected_output=PlannerEvalOutput(
                transport_mode="flight",
                room_description="Well-rated mid-range or boutique room",
                self_transfer=False,
                per_person_minor_units=31_000,
            ),
            evaluators=(EqualsExpected(),),
        ),
        Case(
            name="cheaper-follow-up",
            inputs=PlannerEvalInput(
                starting_tier=BudgetTier.VALUE,
                user_message="Please make this cheaper and use a hostel.",
            ),
            expected_output=PlannerEvalOutput(
                transport_mode="flight",
                room_description="Hostel or simple private room",
                self_transfer=True,
                per_person_minor_units=24_180,
            ),
            evaluators=(EqualsExpected(),),
        ),
        Case(
            name="comfort-follow-up",
            inputs=PlannerEvalInput(
                starting_tier=BudgetTier.BUDGET,
                user_message="Prioritise comfort and direct travel.",
            ),
            expected_output=PlannerEvalOutput(
                transport_mode="flight",
                room_description="Four/five-star room with convenient cancellation terms",
                self_transfer=False,
                per_person_minor_units=51_150,
            ),
            evaluators=(EqualsExpected(),),
        ),
    ),
)


def main() -> None:
    report = asyncio.run(DATASET.evaluate(evaluate_planner_case, progress=False))
    report.print(include_input=True, include_expected_output=True, include_output=True)
    failed_assertions = [
        case.name
        for case in report.cases
        if case.evaluator_failures
        or any(not assertion.value for assertion in case.assertions.values())
    ]
    if report.failures or failed_assertions:
        raise SystemExit(f"eval failures: {failed_assertions or report.failures}")


if __name__ == "__main__":
    main()
