import pytest

from evals.mock_planner import DATASET, evaluate_planner_case


@pytest.mark.asyncio
async def test_mock_planner_eval_dataset() -> None:
    report = await DATASET.evaluate(evaluate_planner_case, progress=False)
    assert report.failures == []
    assert all(
        not case.evaluator_failures
        and all(assertion.value for assertion in case.assertions.values())
        for case in report.cases
    )
