from cpfc_trip.domain import BudgetTier, EmailActivityInput
from cpfc_trip.emailing import render_itinerary_email
from cpfc_trip.planner.mock import build_mock_itinerary

from .test_mock_planner import planner_input


def test_email_is_branded_and_honest() -> None:
    activity_input = planner_input(BudgetTier.VALUE)
    rendered = render_itinerary_email(
        EmailActivityInput(
            public_id=activity_input.public_id,
            contact_id=activity_input.request.contact_id,
            itinerary=build_mock_itinerary(activity_input),
            reason="manual",
        )
    )
    assert "Sponsored by Temporal" in rendered
    assert "Match ticket not included" in rendered
    assert "does not sell travel" in rendered
    assert "@" not in rendered
