from unittest.mock import Mock

import pytest
from pydantic import SecretStr, ValidationError

from cpfc_trip.config import Settings
from cpfc_trip.telemetry import configure_telemetry, safe_api_route


def test_logfire_requires_token_only_when_enabled() -> None:
    assert not Settings(_env_file=None).logfire_enabled
    with pytest.raises(ValidationError, match="Logfire token"):
        Settings(_env_file=None, logfire_enabled=True)


def test_worker_telemetry_omits_model_content(monkeypatch: pytest.MonkeyPatch) -> None:
    configure = Mock()
    instrument = Mock()
    monkeypatch.setattr("cpfc_trip.telemetry.logfire.configure", configure)
    monkeypatch.setattr("cpfc_trip.telemetry.logfire.instrument_pydantic_ai", instrument)
    configure_telemetry(Settings(_env_file=None), "worker")
    configure.assert_not_called()
    configure_telemetry(
        Settings(_env_file=None, logfire_enabled=True, logfire_token=SecretStr("test-token")),
        "worker",
    )
    assert configure.call_args.kwargs["service_name"] == "eagles-away-worker"
    assert configure.call_args.kwargs["console"] is False
    instrument.assert_called_once_with(include_content=False)


def test_api_route_labels_exclude_session_ids_and_queries() -> None:
    assert safe_api_route("POST", "/api/sessions") == "create_plan"
    assert safe_api_route("GET", "/api/sessions/private-id/snapshot") == "plan_snapshot"
    assert safe_api_route("POST", "/api/sessions/private-id/messages") == "plan_message"
    assert safe_api_route("POST", "/api/sessions/private-id/finalize") == "plan_finalize"
    assert safe_api_route("GET", "/api/unknown/private-id") is None
