"""Opt-in, PII-scrubbed Logfire instrumentation."""

from __future__ import annotations

from functools import lru_cache
from typing import Any

import logfire
from fastapi import FastAPI
from logfire import ScrubbingOptions
from pydantic_ai import Agent

from cpfc_trip.config import get_settings


@lru_cache
def configured_logfire() -> logfire.Logfire | None:
    """Configure export only when an explicit token-backed switch is enabled."""

    settings = get_settings()
    if not settings.logfire_enabled:
        return None
    return logfire.configure(
        send_to_logfire=True,
        token=settings.logfire_token,
        service_name="cpfc-away-days",
        service_version="0.1.0",
        environment=settings.app_env,
        console=False,
        metrics=False,
        inspect_arguments=False,
        scrubbing=ScrubbingOptions(
            extra_patterns=(
                "authorization",
                "cookie",
                "email",
                "session_secret",
                "api_key",
                "access_token",
            )
        ),
    )


def require_logfire() -> logfire.Logfire:
    configured = configured_logfire()
    if configured is None:
        raise RuntimeError("Logfire is not enabled")
    return configured


def instrument_fastapi(app: FastAPI) -> None:
    if configured_logfire() is not None:
        logfire.instrument_fastapi(
            app,
            capture_headers=False,
            record_send_receive=False,
            excluded_urls="healthz,readyz",
        )


def instrument_planner(agent: Agent[Any, Any]) -> None:
    if configured_logfire() is not None:
        logfire.instrument_pydantic_ai(
            agent,
            include_content=False,
            include_binary_content=False,
        )
