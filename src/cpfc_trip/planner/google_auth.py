"""Explicit local work-profile credentials; deployed workers use their attached identity."""

import json
import subprocess
from datetime import UTC, datetime
from typing import Any

from google.auth.credentials import Credentials as BaseCredentials
from google.oauth2.credentials import Credentials

from cpfc_trip.config import Settings


def credentials(settings: Settings) -> BaseCredentials | None:
    if settings.google_auth_mode == "adc":
        return None
    if settings.app_env == "production":
        raise ValueError("gcloud authentication is local development only")
    if not settings.google_gcloud_configuration or not settings.google_gcloud_account:
        raise ValueError("Local gcloud mode requires an explicit configuration and account")

    def refresh(request: Any, scopes: Any = None) -> tuple[str, datetime]:
        # SDK refreshes credentials in a thread. Keep token/config JSON out of logs and disk.
        result = subprocess.run(
            [
                "gcloud",
                "config",
                "config-helper",
                "--format=json",
                "--quiet",
                f"--configuration={settings.google_gcloud_configuration}",
                f"--account={settings.google_gcloud_account}",
                f"--project={settings.google_cloud_project}",
            ],
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        )
        if result.returncode:
            raise RuntimeError("Work-profile authentication failed; check gcloud login")
        try:
            data = json.loads(result.stdout)
            token = data["credential"]["access_token"]
            expiry = datetime.fromisoformat(data["credential"]["token_expiry"])
            if not isinstance(token, str) or not token or expiry.tzinfo is None:
                raise ValueError
            if expiry <= datetime.now(UTC):
                raise ValueError
        except (KeyError, ValueError, TypeError):
            raise RuntimeError("Work-profile authentication returned invalid credentials") from None
        # google-auth's credential expiry uses naive UTC datetimes.
        return token, expiry.astimezone(UTC).replace(tzinfo=None)

    return Credentials(  # type: ignore[no-untyped-call]
        token=None, refresh_handler=refresh, quota_project_id=settings.google_cloud_project
    )
