"""Resend transport with sanitized failures; retries belong to Temporal."""

from typing import Any

import httpx
from temporalio.exceptions import ApplicationError


async def send(api_key: str, payload: dict[str, Any], idempotency_key: str) -> str:
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.post(
                "https://api.resend.com/emails",
                headers={"Authorization": f"Bearer {api_key}", "Idempotency-Key": idempotency_key},
                json=payload,
            )
    except httpx.RequestError:
        # The provider might have accepted the message. Retry only with the same key/body.
        raise ApplicationError("Email provider connection failed; outcome unknown") from None
    if not response.is_success:
        code = ""
        try:
            code = response.json().get("name", "")
        except (ValueError, AttributeError):
            pass
        known_codes = {
            "invalid_idempotency_key",
            "validation_error",
            "missing_api_key",
            "restricted_api_key",
            "invalid_api_key",
            "invalid_idempotent_request",
            "concurrent_idempotent_requests",
            "invalid_from_address",
            "missing_required_field",
            "monthly_quota_exceeded",
            "daily_quota_exceeded",
            "rate_limit_exceeded",
            "security_error",
        }
        label = code if isinstance(code, str) and code in known_codes else "unclassified"
        raise ApplicationError(
            f"Email provider rejected the request (HTTP {response.status_code}; {label})",
            non_retryable=(
                400 <= response.status_code < 500
                and response.status_code not in {408, 429}
                and not (response.status_code == 409 and code == "concurrent_idempotent_requests")
            ),
        )
    try:
        provider_id = response.json()["id"]
        if not isinstance(provider_id, str) or not provider_id or len(provider_id) > 100:
            raise ValueError
    except (ValueError, KeyError, TypeError):
        raise ApplicationError(
            "Email provider returned an invalid receipt; outcome unknown"
        ) from None
    return provider_id
