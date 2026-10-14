"""Opt-in operational telemetry with fixed labels and no request or model content."""

import logfire

from cpfc_trip.config import Settings


def configure_telemetry(settings: Settings, service_name: str) -> None:
    if not settings.logfire_enabled:
        return
    logfire.configure(
        token=settings.logfire_token.get_secret_value(),
        service_name=f"eagles-away-{service_name}",
        environment=settings.app_env,
        console=False,
    )
    if service_name == "worker":
        logfire.instrument_pydantic_ai(include_content=False)


def safe_api_route(method: str, path: str) -> str | None:
    if method == "GET" and path == "/api/catalog":
        return "catalog"
    if method == "POST" and path == "/api/sessions":
        return "create_plan"
    parts = path.strip("/").split("/")
    if len(parts) == 4 and parts[:2] == ["api", "sessions"]:
        return {
            ("GET", "snapshot"): "plan_snapshot",
            ("POST", "messages"): "plan_message",
            ("POST", "finalize"): "plan_finalize",
        }.get((method, parts[3]))
    return None
