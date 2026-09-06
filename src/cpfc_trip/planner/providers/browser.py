"""Provider-neutral authorized browser seam; no vendor is activated yet."""

from __future__ import annotations

from dataclasses import dataclass

from cpfc_trip.planner.providers.policy import (
    BrowserAction,
    LaunchMode,
    PolicyRegistry,
    SourcePolicyDenied,
)


@dataclass(frozen=True)
class AuthorizedBrowserRequest:
    provider: str
    url: str
    action: BrowserAction
    policy_id: str
    policy_version: str
    record_session: bool = False
    solve_captcha: bool = False


class AuthorizedBrowserAdapter:
    """Checks policy before a typed Kernel/Browserbase implementation can run."""

    def __init__(self, registry: PolicyRegistry, launch_mode: LaunchMode) -> None:
        self._registry = registry
        self._launch_mode = launch_mode

    def prepare(self, provider: str, url: str, action: BrowserAction) -> AuthorizedBrowserRequest:
        policy = self._registry.authorize_browser(
            provider,
            self._launch_mode,
            url=url,
            action=action,
        )
        browser = policy.browser
        if browser is None:
            raise SourcePolicyDenied(f"{provider} has no browser allowlist")
        return AuthorizedBrowserRequest(
            provider=provider,
            url=url,
            action=action,
            policy_id=policy.id,
            policy_version=policy.version,
            record_session=policy.recording_permitted,
            solve_captcha=browser.captcha_solving_enabled,
        )

    async def execute(self, request: AuthorizedBrowserRequest) -> None:
        del request
        raise SourcePolicyDenied(
            "no browser vendor is activated; downgrade to concierge or a generic link"
        )
