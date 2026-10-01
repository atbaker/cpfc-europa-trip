"""Report configuration; optionally verify cloud authentication and SearchApi quota."""

import argparse

import google.auth
import httpx
from google.auth.transport.requests import Request

from cpfc_trip.config import Settings
from cpfc_trip.planner.google_auth import credentials


def check_live(settings: Settings) -> bool:
    ok = True
    try:
        if not settings.google_cloud_project:
            raise ValueError("Missing Google project")
        auth = credentials(settings)
        if auth is None:
            auth, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
        auth.refresh(Request())
        print("Google credential refresh: passed (model access is checked by live validation)")
    except Exception:
        # Do not print SDK exceptions: these can contain credential/project response bodies.
        print("Google credential refresh: failed; check the configured account, profile or ADC")
        ok = False
    try:
        if not settings.searchapi_enabled or not settings.searchapi_api_key.get_secret_value():
            raise ValueError("SearchApi unavailable")
        response = httpx.get(
            "https://www.searchapi.io/api/v1/me",
            headers={"Authorization": f"Bearer {settings.searchapi_api_key.get_secret_value()}"},
            timeout=20,
        )
        response.raise_for_status()
        account = response.json()["account"]
        used, allowance, credits = (
            int(account[key])
            for key in ("current_month_usage", "monthly_allowance", "remaining_credits")
        )
        available = max(allowance - used, credits)
        print(f"SearchApi account: {used}/{allowance} monthly requests used; {credits} credits")
        if available <= 0:
            print("SearchApi quota: exhausted; review the plan before running a paid validation")
            ok = False
    except Exception:
        print("SearchApi account check: failed; check the key, plan and network")
        ok = False
    return ok


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check-live",
        action="store_true",
        help="Refresh credentials and read quota; no paid searches or email",
    )
    args = parser.parse_args()
    settings = Settings()
    for name, value in [
        ("SearchApi", settings.searchapi_api_key.get_secret_value()),
        ("Resend", settings.resend_api_key.get_secret_value()),
        ("Resend webhook", settings.resend_webhook_secret.get_secret_value()),
        ("Contact encryption", settings.contact_encryption_key.get_secret_value()),
        ("Session secret", settings.session_secret.get_secret_value()),
    ]:
        print(f"{name}: {'configured' if value else 'missing'}")
    print(f"Planning mode: {settings.planner_mode}; email mode: {settings.email_mode}")
    print(
        f"Gemini project: {settings.google_cloud_project or 'missing'}; location: {settings.google_cloud_location}"
    )
    print(f"Google authentication: {settings.google_auth_mode}")
    if settings.google_auth_mode == "gcloud":
        print(
            f"Explicit local profile: {settings.google_gcloud_configuration or 'missing'}; account: {settings.google_gcloud_account or 'missing'}"
        )
    if args.check_live and not check_live(settings):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
