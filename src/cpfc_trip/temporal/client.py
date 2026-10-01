from pydantic_ai.durable_exec.temporal import PydanticAIPlugin
from temporalio.client import Client

from cpfc_trip.config import Settings


async def connect(settings: Settings) -> Client:
    return await Client.connect(
        settings.temporal_address,
        namespace=settings.temporal_namespace,
        tls=settings.temporal_tls,
        api_key=settings.temporal_api_key.get_secret_value() or None,
        plugins=[PydanticAIPlugin()],
    )
