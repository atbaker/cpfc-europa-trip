# Approved MVP simplifications

Approved and incorporated: 6 September 2026.
[The MVP plan](mvp-plan.md) is the implementation source of truth. All six simplifications
are now accepted; the rationale below records what was removed and why. The previous polling,
minimum-worker, Frankfurt-region, and UK flight-locale decisions remain in place.

## 1. Email the committed plan unchanged

Finalization freezes the latest completed itinerary and sends it with the existing prices,
retrieval timestamps, caveats, and links. It makes no SearchApi/model calls and cannot silently
select a different trip. Users can request a refresh or revision in chat before finalization.
Manual send, inactivity, and session limits share one frozen payload and email-delivery record.
Initial planning failure produces one honest failure notice when no valid draft exists.

This removes the provider-dependent repricing/repair stage and reduces differences between
the reviewed itinerary and email. Users confirm current availability and prices externally.

## 2. Direct outbound links

Use direct validated Google Flights, Booking.com, and train seller URLs. Preserve dates, party,
selected services, and explicit UK flight settings. Prefer contextual searches when a specific
link cannot be retained reliably; explain which selections users must repeat.

Remove the outbound redirect endpoint, signed offer tokens, click-audit records, automatic
link regeneration, and refresh-on-click. Keep private session authorization and email access
credentials. Removing outbound tracking does not make saved itineraries public.

## 3. No production browser tools

MVP travel acquisition consists of three typed SearchApi adapters with straightforward engine
configuration, limits, attribution, and an operational disable switch. Static route/venue
context comes from the reviewed catalog. Remove browser adapters and seams, vendor selection,
browser-only policies, generic acquisition routing, and secondary runtime research/provider paths.

Missing evidence produces an explicit gap and a direct search link. It does not trigger another
provider or justify inventing fares, operating hours, or feasible connections. Developer
research and browser-based UI/handoff QA remain ordinary development activities; no user session
depends on them.

## 4. Minimal London fixture-route catalog

Plan from Palace's London home area: Heathrow, Gatwick, Stansted, Luton, and St Pancras. Use
small route templates for Lyon, Istanbul, Białystok via Warsaw, and Salzburg, including the
few flight/rail alternatives listed in the main plan. These are candidates to verify, not
promises of operating services. Live prices/schedules still require SearchApi evidence.

Travel to/from the London hub is outside the itinerary totals. Defer arbitrary origin search,
nationwide positioning legs, coach/ferry discovery, and a general route graph. Preserve all
three budget styles, multiple selected fixtures, dorm/shared-bathroom eligibility, and honest
whole-trip comparison within the searched set.

## 5. Short, bounded conversations

Implementation starting defaults are ten follow-ups, a 30-minute interaction window, three
minutes for initial planning, and 90 seconds per follow-up. The main plan also bounds model and
SearchApi requests/retries. These settings are configurable and must be checked against actual
latency, cost, and coverage during implementation.

Keep one Workflow run, bounded conversation history, structured constraints, and ordinary
command deduplication. Defer chat summarization and Continue-As-New. Measure the maximum
permitted run's payload size, History growth, and cold replay; reduce bounds if necessary.
The interaction limit closes planning but does not kill durable email delivery. A failed
revision preserves the previous plan; initial failure reaches a defined notice and terminal state.

## 6. Deterministic evaluation plus developer review

Start with approximately 20–30 recorded/synthetic scenarios covering all enabled destinations
and budget styles, representative party shapes, provider discrepancies, and important failures.
Keep deterministic arithmetic/feasibility checks, contract tests, Workflow time-skipping/replay,
and basic Logfire traces. Developers review sample output for clarity, usefulness, and faithful
constraint handling.

Defer automated LLM judges, judge calibration, and tool-trajectory scoring. Public launch still
requires adequate measured coverage and quality for the features we enable. Developer QA is
separate from the fully automated production experience.

## Preserved foundations

Keep evidence-backed prices, correct party/tax/currency arithmetic, timezone and match-arrival
validation, atomic commits, session authorization, bounded requests, reliable email, and
explicit missing-data handling. Keep SearchApi, Temporal Serverless Workers, static Next.js,
Terraform/GCP in Frankfurt, UK flight defaults, and direct Temporal polling. Stable club/fixture
identifiers remain inexpensive future flexibility; multi-club administration is deferred.
