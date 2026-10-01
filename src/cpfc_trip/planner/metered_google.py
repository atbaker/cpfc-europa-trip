"""Token-only model telemetry, emitted per actual Activity attempt without prompt contents."""

import json
import logging
import time

from pydantic_ai.exceptions import ModelHTTPError
from pydantic_ai.messages import ModelMessage, ModelResponse
from pydantic_ai.models import ModelRequestParameters
from pydantic_ai.models.google import GoogleModel
from pydantic_ai.settings import ModelSettings
from temporalio import activity
from temporalio.exceptions import ApplicationError

logger = logging.getLogger("cpfc_trip.model_usage")


class MeteredGoogleModel(GoogleModel):
    async def request(
        self,
        messages: list[ModelMessage],
        model_settings: ModelSettings | None,
        model_request_parameters: ModelRequestParameters,
    ) -> ModelResponse:
        started = time.monotonic()
        record: dict[str, str | int | float] = {"event": "model_request", "model": self.model_name}
        if activity.in_activity():
            info = activity.info()
            record.update(
                workflow_id=info.workflow_id or "",
                activity_id=info.activity_id,
                attempt=info.attempt,
            )
        try:
            response = await super().request(messages, model_settings, model_request_parameters)
            record.update(
                outcome="success",
                input_tokens=response.usage.input_tokens,
                output_tokens=response.usage.output_tokens,
                cached_input_tokens=response.usage.cache_read_tokens,
            )
            return response
        except ModelHTTPError as exc:
            record.update(outcome="error", status=exc.status_code)
            raise ApplicationError(
                "Gemini rejected the model request",
                type="GeminiRequestError",
                non_retryable=400 <= exc.status_code < 500 and exc.status_code not in {408, 429},
            ) from None
        except Exception:
            record.update(outcome="error")
            raise ApplicationError("Gemini request failed", type="GeminiRequestError") from None
        finally:
            record["seconds"] = round(time.monotonic() - started, 3)
            logger.info(json.dumps(record))
