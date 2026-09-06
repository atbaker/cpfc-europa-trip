"""Temporal client creation shared by API and local utilities."""

from __future__ import annotations

from pydantic_ai.durable_exec.temporal import LogfirePlugin, PydanticAIPlugin
from temporalio.client import Client, Plugin

from cpfc_trip.config import get_settings
from cpfc_trip.observability import require_logfire


async def connect_temporal() -> Client:
    settings = get_settings()
    plugins: list[Plugin] = [PydanticAIPlugin()]
    if settings.logfire_enabled:
        plugins.append(LogfirePlugin(setup_logfire=require_logfire))
    return await Client.connect(
        settings.temporal_address,
        namespace=settings.temporal_namespace,
        api_key=settings.temporal_api_key,
        tls=settings.temporal_tls,
        plugins=plugins,
    )
