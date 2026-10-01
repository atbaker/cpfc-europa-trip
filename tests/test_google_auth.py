import json
import subprocess
from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from cpfc_trip.config import Settings
from cpfc_trip.planner.google_auth import credentials


def test_work_credentials_are_explicit_refreshable_and_not_adc(monkeypatch):
    settings = Settings(
        _env_file=None,
        google_auth_mode="gcloud",
        google_cloud_project="work-project",
        google_gcloud_account="work@example.com",
        google_gcloud_configuration="work-profile",
    )
    calls = []

    def fake_run(args, **kwargs):
        calls.append(args)
        return subprocess.CompletedProcess(
            args,
            0,
            json.dumps(
                {
                    "credential": {
                        "access_token": "test-token",
                        "token_expiry": (datetime.now(UTC) + timedelta(hours=1)).isoformat(),
                    }
                }
            ),
        )

    monkeypatch.setattr(subprocess, "run", fake_run)
    value = credentials(settings)
    assert not calls  # Creating a workflow/model does not run gcloud.
    value.refresh(None)
    assert value.token == "test-token" and value.quota_project_id == "work-project"
    assert "--configuration=work-profile" in calls[0]
    assert "--account=work@example.com" in calls[0]
    assert "--project=work-project" in calls[0]
    assert value.expiry.tzinfo is None  # google-auth contract is naive UTC.


def test_auth_errors_do_not_expose_credential_output(monkeypatch):
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *a, **kw: subprocess.CompletedProcess(a, 1, "secret-output", "secret-error"),
    )
    value = credentials(
        Settings(
            _env_file=None,
            google_auth_mode="gcloud",
            google_gcloud_configuration="work",
            google_gcloud_account="work@example.com",
        )
    )
    with pytest.raises(RuntimeError) as exc:
        value.refresh(None)
    assert "secret" not in str(exc.value)
    with pytest.raises(ValidationError, match="ADC"):
        Settings(_env_file=None, app_env="production", google_auth_mode="gcloud")


def test_adc_does_not_call_gcloud(monkeypatch):
    monkeypatch.setattr(subprocess, "run", lambda *a, **kw: pytest.fail("Unexpected gcloud call"))
    assert credentials(Settings(_env_file=None, google_auth_mode="adc")) is None
