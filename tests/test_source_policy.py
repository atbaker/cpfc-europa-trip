from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from cpfc_trip.planner.providers.browser import AuthorizedBrowserAdapter
from cpfc_trip.planner.providers.policy import (
    AcquisitionMethod,
    BrowserAccessPolicy,
    BrowserAction,
    LaunchMode,
    PolicyRegistry,
    SourcePolicy,
    SourcePolicyDenied,
    load_policy_registry,
)


def _browser_policy(
    *, enabled: bool = True, expires_in: timedelta = timedelta(days=1)
) -> SourcePolicy:
    return SourcePolicy(
        id="owned-test-v1",
        version="v1",
        provider="owned-test",
        enabled=enabled,
        acquisition_methods=(AcquisitionMethod.AUTHORIZED_BROWSER,),
        launch_modes=(LaunchMode.INTERNAL_R_AND_D,),
        display_fields=("title",),
        workflow_history_fields=(),
        cache_fields=(),
        email_fields=(),
        trace_fields=("outcome",),
        booking_link_policies=(),
        browser=BrowserAccessPolicy(
            allowed_hosts=("travel.example.com",),
            allowed_path_prefixes=("/search/",),
            allowed_actions=(BrowserAction.SEARCH,),
            max_concurrency=1,
            max_requests_per_minute=5,
        ),
        authorization_reference="Owned synthetic test surface.",
        owner="test",
        review_expires_at=datetime.now(UTC) + expires_in,
    )


def test_checked_in_registry_allows_only_honest_generic_fallback() -> None:
    registry = load_policy_registry()
    provider, method, policy = registry.select_first_allowed(
        (
            ("browser-evaluation", AcquisitionMethod.AUTHORIZED_BROWSER),
            ("generic-travel-search", AcquisitionMethod.GENERIC_LINK),
        ),
        LaunchMode.PUBLIC_SELF_SERVE,
    )

    assert provider == "generic-travel-search"
    assert method is AcquisitionMethod.GENERIC_LINK
    assert policy.booking_link_policies == ("generic_search",)
    assert "price" not in registry.fields_for(provider, "email")


def test_browser_requires_exact_host_path_action_and_https() -> None:
    registry = PolicyRegistry((_browser_policy(),))
    allowed = registry.authorize_browser(
        "owned-test",
        LaunchMode.INTERNAL_R_AND_D,
        url="https://travel.example.com/search/london",
        action=BrowserAction.SEARCH,
    )
    assert allowed.id == "owned-test-v1"

    for url in (
        "http://travel.example.com/search/london",
        "https://evil.example/search/london",
        "https://travel.example.com/admin/",
        "https://travel.example.com.evil.test/search/london",
    ):
        with pytest.raises(SourcePolicyDenied):
            registry.authorize_browser(
                "owned-test",
                LaunchMode.INTERNAL_R_AND_D,
                url=url,
                action=BrowserAction.SEARCH,
            )


def test_disabled_expired_and_emergency_killed_policies_fail_closed() -> None:
    with pytest.raises(SourcePolicyDenied):
        PolicyRegistry((_browser_policy(enabled=False),)).authorize(
            "owned-test", AcquisitionMethod.AUTHORIZED_BROWSER, LaunchMode.INTERNAL_R_AND_D
        )

    with pytest.raises(SourcePolicyDenied):
        PolicyRegistry((_browser_policy(expires_in=timedelta(seconds=-1)),)).authorize(
            "owned-test", AcquisitionMethod.AUTHORIZED_BROWSER, LaunchMode.INTERNAL_R_AND_D
        )

    with pytest.raises(SourcePolicyDenied):
        PolicyRegistry(
            (_browser_policy(),), emergency_disabled_policy_ids=("owned-test-v1",)
        ).authorize("owned-test", AcquisitionMethod.AUTHORIZED_BROWSER, LaunchMode.INTERNAL_R_AND_D)


@pytest.mark.asyncio
async def test_browser_adapter_cannot_execute_until_a_vendor_is_activated() -> None:
    adapter = AuthorizedBrowserAdapter(
        PolicyRegistry((_browser_policy(),)), LaunchMode.INTERNAL_R_AND_D
    )
    request = adapter.prepare(
        "owned-test", "https://travel.example.com/search/london", BrowserAction.SEARCH
    )
    assert request.solve_captcha is False
    assert request.record_session is False

    with pytest.raises(SourcePolicyDenied, match="no browser vendor"):
        await adapter.execute(request)
