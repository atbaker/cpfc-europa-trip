"""Versioned, fail-closed source and browser authorization policy."""

from __future__ import annotations

import json
from collections.abc import Iterable
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from functools import lru_cache
from importlib.resources import files
from typing import Literal
from urllib.parse import urlsplit

from pydantic import Field, TypeAdapter, field_validator

from cpfc_trip.domain import FrozenModel


class LaunchMode(StrEnum):
    PUBLIC_SELF_SERVE = "public_self_serve"
    INVITE_ONLY_CONCIERGE = "invite_only_concierge"
    EDITORIAL_SOCIAL = "editorial_social"
    INTERNAL_R_AND_D = "internal_r_and_d"


class AcquisitionMethod(StrEnum):
    API_MCP = "api_mcp"
    AUTHORIZED_BROWSER = "authorized_browser"
    HUMAN_CONCIERGE = "human_concierge"
    GENERIC_LINK = "generic_link"


class BrowserAction(StrEnum):
    SEARCH = "search"
    READ = "read"


class BrowserAccessPolicy(FrozenModel):
    allowed_hosts: tuple[str, ...]
    allowed_path_prefixes: tuple[str, ...]
    allowed_actions: tuple[BrowserAction, ...]
    max_concurrency: int = Field(ge=1, le=10)
    max_requests_per_minute: int = Field(ge=1, le=120)
    stop_on_access_challenge: Literal[True] = True
    captcha_solving_enabled: Literal[False] = False

    @field_validator("allowed_hosts")
    @classmethod
    def require_exact_hosts(cls, hosts: tuple[str, ...]) -> tuple[str, ...]:
        if not hosts:
            raise ValueError("at least one browser host is required")
        for host in hosts:
            if "://" in host or "/" in host or "*" in host:
                raise ValueError(
                    "browser hosts must be exact hostnames without schemes or wildcards"
                )
        return tuple(host.lower() for host in hosts)

    @field_validator("allowed_path_prefixes")
    @classmethod
    def require_absolute_paths(cls, paths: tuple[str, ...]) -> tuple[str, ...]:
        if not paths or any(not path.startswith("/") for path in paths):
            raise ValueError("browser path prefixes must be non-empty absolute paths")
        return paths


class SourcePolicy(FrozenModel):
    id: str
    version: str
    provider: str
    enabled: bool
    acquisition_methods: tuple[AcquisitionMethod, ...]
    launch_modes: tuple[LaunchMode, ...]
    display_fields: tuple[str, ...]
    workflow_history_fields: tuple[str, ...]
    cache_fields: tuple[str, ...]
    email_fields: tuple[str, ...]
    trace_fields: tuple[str, ...]
    quote_ttl: timedelta | None = None
    booking_link_policies: tuple[Literal["direct_web", "refresh_in_app", "generic_search"], ...]
    browser: BrowserAccessPolicy | None = None
    recording_permitted: bool = False
    authorization_reference: str
    owner: str
    review_expires_at: datetime

    @field_validator("review_expires_at")
    @classmethod
    def require_explicit_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("review expiry must be timezone-aware")
        return value


class SourcePolicyDenied(RuntimeError):
    """A provider action is not authorized by the active policy registry."""


class PolicyRegistry:
    """Immutable policy view selected by the server, never by an LLM or browser."""

    def __init__(
        self,
        policies: Iterable[SourcePolicy],
        *,
        emergency_disabled_policy_ids: Iterable[str] = (),
    ) -> None:
        policy_by_provider: dict[str, SourcePolicy] = {}
        for policy in policies:
            if policy.provider in policy_by_provider:
                raise ValueError(f"duplicate source policy for provider: {policy.provider}")
            policy_by_provider[policy.provider] = policy
        self._policies = policy_by_provider
        self._emergency_disabled = frozenset(emergency_disabled_policy_ids)

    def authorize(
        self,
        provider: str,
        method: AcquisitionMethod,
        launch_mode: LaunchMode,
        *,
        now: datetime | None = None,
    ) -> SourcePolicy:
        policy = self._get_current(provider, now=now)
        if method not in policy.acquisition_methods:
            raise SourcePolicyDenied(f"{provider} does not allow acquisition method {method}")
        if launch_mode not in policy.launch_modes:
            raise SourcePolicyDenied(f"{provider} is not enabled for launch mode {launch_mode}")
        if method is AcquisitionMethod.AUTHORIZED_BROWSER and policy.browser is None:
            raise SourcePolicyDenied(f"{provider} has no browser allowlist")
        return policy

    def authorize_browser(
        self,
        provider: str,
        launch_mode: LaunchMode,
        *,
        url: str,
        action: BrowserAction,
        now: datetime | None = None,
    ) -> SourcePolicy:
        policy = self.authorize(
            provider,
            AcquisitionMethod.AUTHORIZED_BROWSER,
            launch_mode,
            now=now,
        )
        browser = policy.browser
        if browser is None:  # Kept explicit so this invariant remains obvious to type-checkers.
            raise SourcePolicyDenied(f"{provider} has no browser allowlist")
        parsed = urlsplit(url)
        host = (parsed.hostname or "").lower()
        if parsed.scheme != "https" or not host or parsed.username or parsed.password:
            raise SourcePolicyDenied("browser target must be an HTTPS URL without credentials")
        if host not in browser.allowed_hosts:
            raise SourcePolicyDenied(f"browser host is not allowlisted: {host or '<missing>'}")
        if not any(parsed.path.startswith(prefix) for prefix in browser.allowed_path_prefixes):
            raise SourcePolicyDenied("browser path is not allowlisted")
        if action not in browser.allowed_actions:
            raise SourcePolicyDenied(f"browser action is not allowlisted: {action}")
        return policy

    def select_first_allowed(
        self,
        candidates: Iterable[tuple[str, AcquisitionMethod]],
        launch_mode: LaunchMode,
        *,
        now: datetime | None = None,
    ) -> tuple[str, AcquisitionMethod, SourcePolicy]:
        denials: list[str] = []
        for provider, method in candidates:
            try:
                policy = self.authorize(provider, method, launch_mode, now=now)
            except SourcePolicyDenied as exc:
                denials.append(str(exc))
                continue
            return provider, method, policy
        raise SourcePolicyDenied("no source is allowed: " + "; ".join(denials))

    def fields_for(
        self, provider: str, channel: Literal["display", "history", "cache", "email", "trace"]
    ) -> frozenset[str]:
        policy = self._get_current(provider)
        fields = {
            "display": policy.display_fields,
            "history": policy.workflow_history_fields,
            "cache": policy.cache_fields,
            "email": policy.email_fields,
            "trace": policy.trace_fields,
        }[channel]
        return frozenset(fields)

    def _get_current(self, provider: str, *, now: datetime | None = None) -> SourcePolicy:
        policy = self._policies.get(provider)
        if policy is None:
            raise SourcePolicyDenied(f"no source policy exists for provider: {provider}")
        if not policy.enabled or policy.id in self._emergency_disabled:
            raise SourcePolicyDenied(f"source policy is disabled: {policy.id}")
        checked_at = now or datetime.now(UTC)
        if checked_at >= policy.review_expires_at:
            raise SourcePolicyDenied(f"source policy review has expired: {policy.id}")
        return policy


_POLICIES_ADAPTER = TypeAdapter(tuple[SourcePolicy, ...])


@lru_cache
def load_policy_registry() -> PolicyRegistry:
    raw = files("cpfc_trip.data").joinpath("source_policies.json").read_text(encoding="utf-8")
    policies = _POLICIES_ADAPTER.validate_python(json.loads(raw))
    return PolicyRegistry(policies)
