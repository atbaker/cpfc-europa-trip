from cpfc_trip.api import app


def test_openapi_exposes_the_mvp_session_surface() -> None:
    paths = app.openapi()["paths"]
    assert "/api/sessions" in paths
    assert "/api/sessions/{public_id}" in paths
    assert "/api/sessions/{public_id}/events" in paths
    assert "/api/sessions/{public_id}/messages" in paths
    assert "/api/sessions/{public_id}/finalize" in paths
