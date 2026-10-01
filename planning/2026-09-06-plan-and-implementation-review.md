# Plan and implementation review — 6 September 2026

Historical review: the implementation reviewed here was removed on 6 September 2026 for a
fresh build. File/line links below refer to commit `fd2dc29`, not the current working tree.
The current build specification is [mvp-plan.md](mvp-plan.md).

Status: recommendations for discussion and implementation. This review does not change the approved baseline or application behavior.

Reviewed: the complete initial implementation at `fd2dc29` (`main`), the 1,193-line [MVP plan](mvp-plan.md), development scripts, tests/evals, and production Terraform. The working tree was clean at the start. Entire is installed but not enabled here; there are no checkpoint transcripts. Statements about intent come from the written plan and the owner's clarification, not reconstructed model conversations. Generated files and lockfile contents were not audited; locked dependencies were installed for verification.

## Recommendation

**Keep the project and its core architecture, but treat the current implementation as an internal demonstration of the workflow and UI. Do not enable real integrations and assume the remaining work is configuration.** The largest missing capability is reliable travel planning: acquiring evidence, representing it, enforcing constraints, preserving changes, and giving users a useful way to act on recommendations.

The plan has several strong choices: independent trips per fixture, one Temporal session workflow, code-owned feasibility and totals, structured itinerary commits, explicit uncertainty, and keeping contact details outside workflow input. FastAPI, a static Next.js frontend, and a single Pydantic AI planner remain reasonable choices. A rewrite or a network of agents would not solve the problems found here.

The immediate priorities are:

1. Repair session, revision, streaming, and email reliability using synthetic data.
2. Prove one complete journey using real evidence and a usable booking handoff.
3. Expand the supported travel envelope only as its coverage and tests become credible.
4. Complete deployment and public-service controls before inviting public traffic.

### Owner clarification captured during this review

- The target is a **public travel-planning service**, not merely a sponsor demonstration or concierge pilot.
- Browser acquisition is acceptable for some steps. Paid data providers, including a possible Duffel integration, are acceptable even if searches incur fees and the site does not book trips.
- Partnership discussions are early; no concrete provider access is available yet.
- Future development will use the current frontier model. That is a development-workflow choice; it does not automatically select the production application's model.
- A launch date and operating budget remain unspecified.

## Changes I recommend to the plan

### 1. Make evidence acquisition the next product milestone

The plan correctly identifies inventory access as the largest risk, but its early milestones combine provider work, two browser vendors, a streaming preview, serverless scaling, and substantial infrastructure. That makes it possible to complete much of the scaffolding without proving a useful journey.

Retain the architecture, but move the next acceptance gate to a complete London–Lyon trip: outbound travel, an identifiable stay, venue access, post-match return to the stay, return travel, total-cost coverage, and actionable links. Exercise all three budget styles against the same evidence. Add the late Istanbul kickoff as an early difficult case, before general expansion.

The initial public release can support a deliberately bounded set of origins, dates, and party sizes. State that coverage in the form. Keep all four fixtures in the intended scope, but do not accept arbitrary origins or family/room combinations merely because the schema can represent them. Accept a case publicly only when the planner can substantiate it or give a useful, explicit unsupported result.

### 2. Reopen the provider shortlist, including Duffel

Replace the categorical “Do not use for MVP” entry for Duffel with **“evaluate paid search access and booking handoff.”** Willingness to pay removes one objection, but search fees alone do not establish that an offer can be reproduced at an airline's checkout or displayed/emailed under the intended arrangement.

[Duffel's pricing page](https://duffel.com/pricing) publishes excess-search pricing and a search-to-book ratio. Ask Duffel specifically about a search-only application with zero orders, redistribution/retention, airline coverage for these routes, and whether a permitted external handoff can reproduce the quoted itinerary. Obtain an actual account-specific answer before treating public pricing as approval for that business model.

[Duffel Links](https://duffel.com/docs/guides/duffel-links) provides a hosted search-and-book flow that creates orders accessible through the integrating organisation's dashboard/API; its guide also describes sending booking confirmations. It is not an ordinary airline referral link. Adopting that flow would require an explicit product decision about responsibility for the resulting bookings. Do not quietly introduce it as a way to preserve the existing no-booking boundary.

For any provider, distinguish:

| Handoff | What the product may say |
| --- | --- |
| Verified offer-specific link | The user can inspect this particular offer, subject to expiry/repricing. |
| Search link preserving route/dates/party | Repeat this search; price and inventory may differ. |
| Generic provider homepage | Search independently; this link does not preserve the recommendation or quote. |

Keep partner discussions moving while building against realistic synthetic responses. A paid acquisition spike should measure usable itinerary coverage, link fidelity, latency, failures, and cost per completed plan, including retries and revisions. No paid searches or provider outreach were performed during this review.

### 3. Treat browser acquisition as a real supported adapter

Browser use can be part of the public service. Choose one vendor for the first useful adapter; a full Kernel-versus-Browserbase benchmark need not precede product learning. Retain vendor-neutral request/result contracts so changing vendor remains possible.

Select a small set of sources whose intended access is supported. Build typed search tasks, bounded navigation, extraction checks, final-URL/redirect checks, timeouts, and failure categories. Return evidence in the same format as API adapters. Source failure must not silently turn a schedule guess into a recommendation. The existing adapter is only an interface and authorization check; it performs no acquisition.

A generic link remains a valid degraded outcome, but is not itself evidence that a route is feasible. A public launch cannot depend on unstaffed concierge work. Keep concierge as an optional later operating mode rather than implementing its entire workflow before the first public-capable route.

### 4. Reduce model authority and formalize constraints

Implement the plan's evidence and candidate layer before making prompts more elaborate. Code should own route identities, timezone conversion, match buffers, transfers, accommodation dates/occupancy, mandatory user constraints, and monetary arithmetic. Let the model interpret requests, propose bounded searches, select among valid candidates, and explain tradeoffs.

Represent an itinerary as selections from verified candidates. Construct commercial facts and booking references from those candidates instead of allowing the model to write arbitrary prices, operators, times, or URLs into the final render model. Persist the active constraints and current itinerary between turns. Distinguish a question from a revision; a question about kickoff must not replan the trip.

Replace the ambiguous flexibility scalar with explicit per-fixture travel windows and a resolved origin. Include evidence status and missing-cost coverage in totals. Compare the cheapest *validated candidates found*, without claiming a global cheapest trip. Revalidate the fixture and selected time-sensitive offers before freezing the final email; the original workflow snapshot should remain replay-safe, while fresh checks arrive through Activities.

### 5. Keep streaming, but make snapshot recovery independently reliable

The approved plan calls for Workflow Streams. The local stream path works, so there is no evidence yet that Redis is necessary. Repair and test the current transport before replacing it.

Prioritize curated progress and atomic itinerary cards. Token narration is secondary to itinerary quality. Typed planning output is not automatically a source of streamable prose, and the current OpenAI agent has no Q&A output mode. Add a narrow text response path only where it serves a user need.

Use a stable subscription, global offsets, turn/attempt/segment identity, canonical snapshot reconciliation, and bounded terminal delivery. Polling must cover a connected but stalled stream as well as a disconnected one. Initially cap session duration, turns, output size, and subscribers; implement Continue-As-New only when a measured history budget requires it. The plan's elaborate rollover design need not precede bounded short sessions.

### 6. Define the email promise precisely

Keep one requested final itinerary per session. Define what happens when a revision is still running at the inactivity deadline: allow a small bounded completion window, then send the latest valid revision. Define an honest no-result outcome for initial planning failure. A ten-minute inactivity timer cannot provide a useful guarantee while the workflow is indefinitely awaiting a failed model call.

Use a durable delivery record and stable payload. Distinguish preview generated, provider accepted, delivered, bounced, and ambiguous delivery. “Exactly once” should describe the logical finalization and duplicate prevention policy, not promise inbox delivery across arbitrary provider outages. Resend's deduplication window is finite; ambiguous sends outside that window need reconciliation rather than blind resending.

### 7. Separate the development model from the runtime model

Use the frontier model for ongoing implementation as requested. Keep the runtime model configurable and evaluate it on real travel cases once evidence tools exist. Establish a quality baseline with a strong model, then compare the existing Terra/medium choice on factual correctness, constraint preservation, latency, and cost.

The existing `gpt-5.6-terra` identifier and medium effort are supported in the [official OpenAI documentation](https://developers.openai.com/api/docs/models/gpt-5.6-terra). The principal defect is not an invalid model name: it is asking a model to produce travel output without the planned evidence pipeline. Changing only the model would leave the critical defects intact.

## Implementation findings

Severity here reflects readiness for the intended public service. **High** means address before enabling the affected real-user capability; **Medium** means a concrete correctness or operational issue to include in the next relevant increment. Missing production capabilities are explicitly distinguished from reproduced bugs.

### Domain and planner — `domain.py`, `planner/agent.py`, `planner/mock.py`

**High — F01: The OpenAI path cannot yet substantiate its travel output.**

Evidence: [agent.py:47](/Users/atbaker/Projects/atbaker/cpfc-europa-trip/src/cpfc_trip/planner/agent.py:47), [workflow.py:150](/Users/atbaker/Projects/atbaker/cpfc-europa-trip/src/cpfc_trip/temporal/workflow.py:150), [domain.py:134](/Users/atbaker/Projects/atbaker/cpfc-europa-trip/src/cpfc_trip/domain.py:134).

The agent has no travel/research tools and receives no provider candidates. It outputs `Itinerary` directly, which is committed without deterministic post-validation. The models omit the planned evidence/quote separation and price coverage. Most itinerary datetimes are plain `datetime`, unlike the validated fixture timestamps. A local probe successfully validated an itinerary containing naive timestamps, arrival before departure, a “live” price without a check time, and a loopback HTTP booking URL. This demonstrates that schema validity currently establishes shape, not trustworthiness or feasibility. It does not establish that the model has actually generated those values.

Fix: implement candidate-backed construction and deterministic cross-field/request validation. Require allowed URLs, aware timestamps, valid timezones, positive durations, stay/date/party consistency, fixture coverage, cost reconciliation, and provenance/freshness for claims. Reject unsupported commercial facts before they enter workflow history or render output. Preserve synthetic demo behavior separately; the mock currently ignores flexibility and extra instructions and assumes the origin timezone is London.

**High — F02: Model retry duration and cost are not bounded by the advertised session deadline.**

Evidence: [agent.py:61](/Users/atbaker/Projects/atbaker/cpfc-europa-trip/src/cpfc_trip/planner/agent.py:61), [workflow.py:68](/Users/atbaker/Projects/atbaker/cpfc-europa-trip/src/cpfc_trip/temporal/workflow.py:68).

The model Activity has start-to-close and heartbeat timeouts, but no schedule-to-close timeout or bounded retry policy. The installed Pydantic integration adds non-retryable error classifications; for retryable failures it otherwise retains Temporal's default policy. [Temporal documents unlimited default Activity attempts](https://docs.temporal.io/encyclopedia/retry-policies). The main loop checks inactivity only after planning returns. Repeated transient failure can therefore keep the workflow in planning beyond ten minutes. No application-level model token, spend, turn-count, or total-lifetime budget is configured.

Fix: cap total planning-turn time across attempts, configure retryable/non-retryable failure handling and model usage limits, and coordinate cancellation/fallback with finalization. Add per-session and global acquisition budgets before enabling paid integrations.

### Session workflow — `temporal/workflow.py`

**High — F03: A planning failure can prevent the promised final email, even when a valid draft exists.**

Evidence: [workflow.py:67](/Users/atbaker/Projects/atbaker/cpfc-europa-trip/src/cpfc_trip/temporal/workflow.py:67).

Both initial and revision planning exceptions escape the workflow loop. In a real local Temporal run with a controlled non-retryable Activity failure, initial planning ended with Temporal status `FAILED`, snapshot phase `researching`, and `email_status=not_sent`. Failure during revision ended with Temporal status `FAILED`, snapshot phase `revising`, and an existing draft that was never emailed. The declared `FAILED` application phase is not set by these paths.

Fix: handle planning failures explicitly. Keep the previous committed itinerary on revision failure, expose an actionable error, and preserve the inactivity/finalization path. Commit a defined degraded/no-result outcome for initial failure. Cover failures after retries, cancellation, and a deadline occurring during a revision.

**High — F04: Every follow-up is a new plan with no conversation or prior itinerary context.**

Evidence: [workflow.py:131](/Users/atbaker/Projects/atbaker/cpfc-europa-trip/src/cpfc_trip/temporal/workflow.py:131), [domain.py:243](/Users/atbaker/Projects/atbaker/cpfc-europa-trip/src/cpfc_trip/domain.py:243).

`PlanActivityInput` carries the original request and latest message, but not the current itinerary, prior messages, or accumulated constraints. Every message increments the itinerary revision. A local workflow probe sent “Make it cheaper” followed by “What time is kickoff?”: the question produced revision 3 and reverted the cheaper choice to the original value tier. The same absence of context affects the OpenAI path even though its precise output was not tested live.

Fix: persist structured constraints and the current plan, classify question/revision turns, and pass the necessary context to planning. Questions should append a canonical answer without changing the itinerary revision. Revisions should preserve prior constraints unless explicitly changed.

**High — F05: Workflow completion can lose the terminal stream events.**

Evidence: [workflow.py:225](/Users/atbaker/Projects/atbaker/cpfc-europa-trip/src/cpfc_trip/temporal/workflow.py:225).

The workflow publishes final status and `session_closed`, then returns immediately. In the local Temporal probe, the workflow completed as `emailed`, but its attached subscriber received neither the final status nor `session_closed`. This is the completion race described in [Temporal's stream guidance](https://docs.temporal.io/develop/python/workflows/workflow-streams).

Fix: add a bounded subscriber acknowledgement/overlap before completion and account for stream poll handlers. The API/client must also fetch the terminal snapshot when a subscription ends; correctness cannot depend on receiving one last event.

### Email — `emailing.py`, `persistence/repository.py`

**High — F06: Retrying an ambiguous send can change the payload under the same idempotency key.**

Evidence: [emailing.py:20](/Users/atbaker/Projects/atbaker/cpfc-europa-trip/src/cpfc_trip/emailing.py:20), [emailing.py:91](/Users/atbaker/Projects/atbaker/cpfc-europa-trip/src/cpfc_trip/emailing.py:91).

The provider send happens before the delivery row is inserted. Rendering runs again on each attempt and includes the current minute in the HTML. If Resend accepts the request but the response or subsequent database commit fails, a retry in another minute sends different HTML under the same key. A simulated provider-accepted/database-failed attempt reproduced that payload mismatch. [Resend rejects different payloads under an existing key and retains keys for 24 hours](https://resend.com/docs/dashboard/emails/idempotency-keys).

The key and database uniqueness are also scoped to session **and revision**, although the product promise is one final email per session. A restarted workflow that finalizes a different revision can create another logical delivery.

Fix: atomically create a session-unique pending delivery intent, freeze recipient/from/subject/rendered body and its timestamp before sending, retry the exact bytes, and record provider acceptance afterward. Keep the selected revision as data on that intent. Handle ambiguous acceptance and reconciliation explicitly, including after the provider deduplication window. Do not switch to a new key merely to bypass a payload conflict.

**High — F07: The final email omits much of the useful itinerary.**

Evidence: [emailing.py:59](/Users/atbaker/Projects/atbaker/cpfc-europa-trip/src/cpfc_trip/emailing.py:59).

The email renders basic travel/stay/match lines but no booking links, prices, price coverage, totals, item caveats, or full itinerary assumptions. A rendered example contained zero anchors. There is no refresh/access link, offer revalidation, or outbound-link implementation. The provider send has no plain-text body. `sent` means provider acceptance or merely a local preview, while the UI says a copy is in the inbox.

Fix: build a shared policy-filtered presentation model for web/email, with permitted links, relevant conditions, timestamps, booking order, clear degraded outcomes, and a text alternative. Preserve local timezones and dates on both ends of each leg. Add signed refresh/access behavior only where needed. Track provider acceptance separately from delivery/bounce via verified, deduplicated webhooks; label preview mode accurately.

### API and submission — `api.py`, `planner-form.tsx`

**High — F08: Submission idempotency is incomplete across the browser, database, and Temporal.**

Evidence: [planner-form.tsx:86](/Users/atbaker/Projects/atbaker/cpfc-europa-trip/frontend/components/planner-form.tsx:86), [api.py:138](/Users/atbaker/Projects/atbaker/cpfc-europa-trip/src/cpfc_trip/api.py:138), [api.py:174](/Users/atbaker/Projects/atbaker/cpfc-europa-trip/src/cpfc_trip/api.py:174).

- A fresh request ID is created on every submit attempt. Retrying after a lost successful response can create a second session and email.
- An existing request ID accepts a different body/email and issues the existing session's access cookie. The probe returned `202` and an access cookie for a changed email. The request ID effectively becomes a recovery credential; this is not an attack using the public session ID alone.
- Workflow start uses the default reuse policy. Reusing a completed workflow ID created another run in the local Temporal probe. Catching `WorkflowAlreadyStartedError` does not protect closed executions. [Temporal documents this default](https://docs.temporal.io/workflow-execution/workflowid-runid#what-is-a-workflow-id-reuse-policy).
- A database commit followed by a failed/missed workflow start has no durable start intent or reconciliation path if the browser leaves.

Fix: retain a submission ID through transport retries, reject differing normalized payloads for that ID, bind recovery to an appropriate browser/recovery credential, and persist enough creation intent to reconcile a missed start. Explicitly reject duplicate closed workflow IDs and retain database-level business uniqueness beyond Temporal history retention. Reuse message/finalization IDs through ambiguous retries as well.

**Medium — F09: Some invalid requests write data and then return HTTP 500.**

Evidence: [domain.py:116](/Users/atbaker/Projects/atbaker/cpfc-europa-trip/src/cpfc_trip/domain.py:116), [api.py:143](/Users/atbaker/Projects/atbaker/cpfc-europa-trip/src/cpfc_trip/api.py:143).

Child-age and fixture-list constraints exist in inner domain models but not in `SessionCreateBody`. Those models are constructed after the contact/session write. The HTTP probe submitted child age `99`, observed one call to create the database rows, then HTTP `500`. Empty/duplicate fixture lists have the same misplaced validation boundary.

Fix: validate the complete request before any write or workflow start; return structured `422` errors. Generate client types from OpenAPI and render its validation error arrays correctly rather than assuming `detail` is always a string.

**Medium — F10: Creating another plan invalidates access to earlier plans in the same browser.**

Evidence: [api.py:185](/Users/atbaker/Projects/atbaker/cpfc-europa-trip/src/cpfc_trip/api.py:185), [api.py:200](/Users/atbaker/Projects/atbaker/cpfc-europa-trip/src/cpfc_trip/api.py:200).

There is one root-scoped cookie containing exactly one session ID/token. Starting plan B overwrites plan A's credential, so A's requests return `403`; A continues running and can still email. The server does not enforce an access expiry, and there is no implemented recovery link.

Fix: use an anonymous browser identity authorized for multiple sessions, or another bounded multi-session credential scheme. Define server-side expiry/revocation and recovery. Test two tabs and opening an older itinerary after starting a new one.

### Browser state — `plan-experience.tsx`, `itinerary-view.tsx`

**High — F11: Streaming recovery does not consistently converge to canonical state.**

Evidence: [plan-experience.tsx:24](/Users/atbaker/Projects/atbaker/cpfc-europa-trip/frontend/components/plan-experience.tsx:24), [plan-experience.tsx:58](/Users/atbaker/Projects/atbaker/cpfc-europa-trip/frontend/components/plan-experience.tsx:58).

Temporary component probes confirmed both of these behaviors: an open-but-stalled stream produces no recovery snapshot requests over six seconds, and after a lost commit event, successful snapshot polling leaves the old provisional answer visible beside the committed itinerary.

Related source-level defects: changing `pendingTurn` recreates `fetchSnapshot`, which recreates EventSource; newly created subscriptions restart without an application-held cursor. Incoming SSE IDs are ignored, status events are not revision-gated, and `accepted=false` command receipts are ignored when HTTP is `200`. Poll/commit-triggered fetch errors are not consistently caught. A successful POST with a rejected command can leave the UI waiting for a turn that will never exist.

Fix: extract a tested reducer/state controller with a stable connection, offset deduplication, monotonic state revisions, committed-turn reconciliation, stale-stream detection, explicit receipt handling, and terminal cleanup. Every successful snapshot should clear obsolete provisional state. Stop subscriptions/polling on terminal states; surface recoverable failures without losing the user's command.

**Medium — F12: Date-only stay fields display the wrong day in timezones west of UTC.**

Evidence: [itinerary-view.tsx:257](/Users/atbaker/Projects/atbaker/cpfc-europa-trip/frontend/components/itinerary-view.tsx:257).

`formatDateOnly` constructs midnight UTC and formats it in the viewer's timezone. The actual expression rendered 14 October as **13 Oct** under `America/Los_Angeles`.

Fix: format date-only values without viewer-timezone conversion, for example by explicitly formatting the UTC-created date in UTC. Test stay dates in London, Los Angeles, and Istanbul. Keep timezone-aware instant formatting separate from calendar dates.

### Source policy — `planner/providers/policy.py`, `domain.py`

**High — F13: The source-policy registry is not yet enforced at the data boundaries it describes.**

Evidence: [policy.py:180](/Users/atbaker/Projects/atbaker/cpfc-europa-trip/src/cpfc_trip/planner/providers/policy.py:180), [policy.py:208](/Users/atbaker/Projects/atbaker/cpfc-europa-trip/src/cpfc_trip/planner/providers/policy.py:208), [domain.py:235](/Users/atbaker/Projects/atbaker/cpfc-europa-trip/src/cpfc_trip/domain.py:235).

`fields_for` is not wired into acquisition, Activity return values, rendering, email, or tracing. The workflow input lacks the planned launch/source-policy snapshot. Emergency disables are an immutable constructor argument, while the application uses a process-cached registry with no operational update path. Browser execution always raises, and the active planner has no provider ladder. These are missing integration guarantees, not evidence that a live provider is currently leaking data.

Fix: implement the smallest enforceable policy layer around actual adapters. Use typed permitted representations and filter before restricted fields enter Activity results/history, then filter again for each delivery channel. Record source/policy versions and consult an operational kill switch inside acquisition/finalization Activities. Test stored history and rendered email, not just `authorize()` return values.

### Production startup — `config.py`, `observability.py`, `pyproject.toml`, `infra/envs/prod/locals.tf`

**High — F14: The production worker cannot pass its own settings validation.**

Evidence: [config.py:45](/Users/atbaker/Projects/atbaker/cpfc-europa-trip/src/cpfc_trip/config.py:45), [locals.tf:74](/Users/atbaker/Projects/atbaker/cpfc-europa-trip/infra/envs/prod/locals.tf:74).

Every production process requires a non-default `SESSION_SECRET`, but Terraform supplies that secret only to the API. Constructing settings with the worker's environment shape reproduced `SESSION_SECRET must be changed in production` before worker startup.

Fix: validate configuration by runtime role so the worker does not require an API-only credential, or explicitly supply a justified worker configuration. Smoke-test both production environment shapes with placeholder secrets before building releases.

**High — F15: Enabling the configured FastAPI telemetry fails with the locked dependencies.**

Evidence: [observability.py:52](/Users/atbaker/Projects/atbaker/cpfc-europa-trip/src/cpfc_trip/observability.py:52), [pyproject.toml:13](/Users/atbaker/Projects/atbaker/cpfc-europa-trip/pyproject.toml:13), [locals.tf:57](/Users/atbaker/Projects/atbaker/cpfc-europa-trip/infra/envs/prod/locals.tf:57).

Production enables Logfire. The application calls `logfire.instrument_fastapi`, but the dependency is `logfire`, without its FastAPI extra. A local instrumentation call with export disabled raised a missing `opentelemetry-instrumentation-fastapi` error. The mock/default tests leave telemetry disabled and miss it.

Fix: declare the required instrumentation dependency and exercise enabled telemetry with an in-memory/no-export sink in startup tests. Verify free-text and contact redaction on actual captured spans before turning on production export.

### Deployment — `infra/envs/prod/*`, `temporal/worker.py`, `frontend/lib/config.ts`

**High — F16: The load balancer sets an unsupported serverless-backend timeout.**

Evidence: [load_balancer.tf:36](/Users/atbaker/Projects/atbaker/cpfc-europa-trip/infra/envs/prod/load_balancer.tf:36).

The backend service sets `timeout_sec = 3600` while using a serverless NEG. [Google's documentation](https://docs.cloud.google.com/load-balancing/docs/negs/serverless-neg-concepts) says that setting is unsupported for serverless NEG backends; their timeout is fixed. Terraform schema validation passes, so this requires provider/API-aware review. No cloud apply was attempted.

Fix: remove the unsupported backend-service timeout, retain the appropriate Cloud Run service timeout, and test reconnect behavior across connection limits.

**High — F17: The serverless worker release design is not implemented.**

Evidence: [cloud_run.tf:110](/Users/atbaker/Projects/atbaker/cpfc-europa-trip/infra/envs/prod/cloud_run.tf:110), [worker.py:33](/Users/atbaker/Projects/atbaker/cpfc-europa-trip/src/cpfc_trip/temporal/worker.py:33).

Terraform describes one fixed-name, manually scaled pool and ignores subsequent image changes. The worker has no deployment version configuration or pinned behavior; no release controller registers versions, promotes them, or drains old pools. With the pool disabled by default, the stack also has no running worker. This is acknowledged scaffolding, not the immutable per-build WCI release system described in the plan.

Fix: explicitly choose the first deployment approach. A continuously running worker is a reasonable initial option if zero-to-one scaling is not a launch requirement. If Serverless Workers remains required, implement version identity, pinned workflows, immutable pools, registration, canary, promotion, draining, and rollback before deployment. Do not let Terraform ignore image changes until a tested controller owns them.

**Medium — F18: Other production assumptions need an executable release path.**

Evidence: [sql.tf:18](/Users/atbaker/Projects/atbaker/cpfc-europa-trip/infra/envs/prod/sql.tf:18), [api.py:115](/Users/atbaker/Projects/atbaker/cpfc-europa-trip/src/cpfc_trip/api.py:115), [config.ts:1](/Users/atbaker/Projects/atbaker/cpfc-europa-trip/frontend/lib/config.ts:1).

The plan calls for private-IP Cloud SQL/IAM authentication and a migration Job; the implementation enables public IP, creates no database login/IAM database user, and has no migration Job or connector-based IAM login. This does not mean the database permits unauthenticated public access. It means the intended connection model is unfinished and differs from the plan. Readiness checks only Temporal, so a missing/broken database can still appear ready.

The static frontend defaults to `http://localhost:8000`, with no production publisher/build guard. A plain successful build can therefore produce an artifact that calls the visitor's localhost. There is no assets-first publisher/cache metadata/rollback workflow, and `/out` and `/webhooks` are absent from both the API implementation and URL map.

Fix: choose and document the database authentication/network path, automate migrations and database readiness, and prove it with a production-like smoke test. Use same-origin API URLs in production and reject a production build containing a localhost API base. Implement release cache metadata and retained hashed assets, and add dynamic routes when their corresponding features are built.

### Public operation and verification — persistence, API, tests, scripts

**High — F19: Public traffic has no enforced abuse or resource budget.**

Evidence: [api.py:130](/Users/atbaker/Projects/atbaker/cpfc-europa-trip/src/cpfc_trip/api.py:130), [workflow.py:95](/Users/atbaker/Projects/atbaker/cpfc-europa-trip/src/cpfc_trip/temporal/workflow.py:95), [load_balancer.tf:29](/Users/atbaker/Projects/atbaker/cpfc-europa-trip/infra/envs/prod/load_balancer.tf:29).

There are no new-session/email rate limits, active-session quotas, total session/turn caps, or subscriber limits. The workflow's command/dedup/message collections and stream history can grow throughout an indefinitely active session. Cloud Armor from the plan is not attached. Public submissions can initiate paid planning and send mail to arbitrary syntactically valid addresses.

Fix: enforce rate/concurrency/spend limits at the API, workflow, provider, and account levels, with bounded streams and sensible overload responses. Add launch telemetry for cost, failures, delivery outcomes, and throttling. Adaptive challenge is optional; basic budgets are not optional before a paid public endpoint.

**Medium — F20: Retention is a timestamp, not an implemented lifecycle.**

Evidence: [repository.py:36](/Users/atbaker/Projects/atbaker/cpfc-europa-trip/src/cpfc_trip/persistence/repository.py:36), [models.py:15](/Users/atbaker/Projects/atbaker/cpfc-europa-trip/src/cpfc_trip/persistence/models.py:15), [models.py:44](/Users/atbaker/Projects/atbaker/cpfc-europa-trip/src/cpfc_trip/persistence/models.py:44).

Contacts get a fixed 30-day expiry, but no deletion job or authorization check uses it. Email rows retain HTML and restrict contact deletion. Session access has no server-side expiry/revocation. There is no full privacy page or deletion process. Email is an ordinary database string; any desired application-level encryption still needs a threat-model decision, separate from the database service's storage encryption.

Fix: choose explicit retention/access periods, implement and test deletion ordering across delivery/session/contact records, and align workflow-history retention and recovery behavior with the published policy. Keep only necessary data and verify what free-text fields enter telemetry. Resolve this before collecting public user details.

**Medium — F21: Passing checks substantially overstate acceptance-criteria coverage.**

Evidence: [test_api_contract.py:1](/Users/atbaker/Projects/atbaker/cpfc-europa-trip/tests/test_api_contract.py:1), [test_emailing.py:1](/Users/atbaker/Projects/atbaker/cpfc-europa-trip/tests/test_emailing.py:1), [mock_planner.py:76](/Users/atbaker/Projects/atbaker/cpfc-europa-trip/evals/mock_planner.py:76), [scripts/check.sh:1](/Users/atbaker/Projects/atbaker/cpfc-europa-trip/scripts/check.sh:1).

The API “contract” test checks that routes exist. The email test checks a few strings. Evals assert three predetermined mock outputs. There are no checked-in workflow/replay, database integration, API authorization/idempotency, stream recovery, live-adapter contract, or end-to-end tests, and no CI workflow. Frontend types and fixture choices are handwritten copies; they can drift from the backend. The form always selects the first fixture, and the backend accepts catalog entries without checking past/cancelled status or refreshing fixtures before finalization.

Fix: add tests around observed failures and user-visible invariants rather than expanding assertions about mock constants. Generate types and fixture presentation data from one source, choose the next eligible fixture, and recheck changed/cancelled fixtures through Activities. Run the existing checks plus the new reliability suite in CI. Qualify README claims until their acceptance gates have passed.

## Suggested implementation sequence

| Increment | Work | Completion evidence |
| --- | --- | --- |
| 1. Reliable internal session | Fix F03–F06, F08–F12; add production configuration/telemetry smoke tests for F14–F15. Preserve mocks. | Lost HTTP responses, duplicate commands, two tabs, failed revisions, worker restart, stream interruption, manual/timeout races, and ambiguous email sends produce one coherent result. |
| 2. Travel contracts and one complete route | Implement F01/F04/F13: resolved origins/windows/constraints, candidate evidence, deterministic verification, one acquisition adapter, realistic fixture responses, and useful web/email output. Evaluate paid API and browser access in parallel. | A reviewed London–Lyon journey and an Istanbul late-night case have sourced legs, valid stays/transfers, comparable totals/coverage, and a usable handoff. Unsupported cases are honest. |
| 3. Public coverage and budgets | Extend the validated envelope to the four fixtures and supported origin/party combinations; complete F02/F07/F19/F20 and generated contracts/catalog handling. | Human-reviewed golden cases, source failure/expiry tests, per-session costs and latency, verified delivery handling, retention/deletion, and enforceable admission limits. |
| 4. Deployable public service | Resolve F16–F18/F21; implement migrations, frontend publishing, chosen worker release method, CI, operational dashboards, and rollback. | A production-like end-to-end canary covers direct `/plan/` reload, evidence acquisition, revision, finalization, network failure, restart, and rollback. Public traffic starts only inside the tested coverage envelope. |

Do not postpone all reliability testing until the last increment: the first increment protects the foundation on which paid provider work will run. Do not make low-volume serverless optimization, another club, combined multi-fixture travel, or broad browser-vendor benchmarking prerequisites for proving the core journey.

## Verification performed

All verification used local/synthetic data. The isolated Temporal server was shut down after the probes. No real OpenAI/provider requests, transactional emails, cloud plans/applies, or external messages were sent. Application source and the original plan were left unchanged.

| Check | Result and limit |
| --- | --- |
| Locked Python installation | Succeeded with Python 3.13.3. Installed Pydantic AI 2.39.0 and Temporal SDK 1.32.0. The first sandboxed `uv` invocation crashed; rerunning with approved access succeeded. |
| Python checks | Ruff formatting/lint and strict mypy passed; all 16 checked-in pytest tests passed without an OpenAI key. The mock eval dataset is included in those tests. |
| Frontend checks | Under the declared Node 24.15.0 runtime, TypeScript, ESLint, the one checked-in Vitest test, and Next's static build passed. `out/index.html`, `out/plan/index.html`, and hashed static assets exist. |
| Terraform | Formatting and backend-disabled initialization/validation passed for bootstrap and production. This does not prove cloud API acceptance, IAM, connectivity, or deployability. |
| Actual local Temporal execution | CLI 1.8.2 / Server 1.31.2. Exercised initial planning, two follow-ups, manual finalization, inactivity completion, stream subscription, completed-ID reuse, initial failure, and revision failure. Mock planning used the real stream publisher; email was replaced by a safe Activity stub. Reproduced F03–F05 and the completed-ID part of F08. |
| HTTP probes | In-process FastAPI transport with persistence/Temporal mocked. Reproduced HTTP 500 after a persistence call for invalid child age and mismatched-payload replay issuing the original session cookie. Not a PostgreSQL integration test. |
| Email probe | Simulated provider acceptance followed by a database failure; rerendered one minute later and observed changed payload under the same key. This matches documented Resend rejection semantics; no Resend API was called. |
| Temporary frontend probes | Two additional component characterizations reproduced missing polling for stalled SSE and stale provisional text after canonical snapshot recovery. They were kept outside the repository, not added as a permanent test suite. |
| Date formatting | Reproduced the prior-day display under `America/Los_Angeles`. |
| Production startup probes | Reproduced the worker secret-validation failure and missing FastAPI instrumentation dependency, without exporting telemetry. |
| External fact checks | The [official CPFC announcement](https://www.cpfc.co.uk/news/announcement/revealed-our-europa-league-league-phase-opponents/) agrees with the four seeded dates and UK kickoff times; venue confirmation remains separate. Checked official Duffel, Resend, OpenAI, Temporal, and Google documentation for the specific findings above. This was not a comprehensive provider-contract or legal review. |

Not exercised: a full browser–FastAPI–PostgreSQL deployment, real inventory/model quality, real email delivery, cloud provisioning/WCI scaling, production replay compatibility across code changes, load, accessibility, mobile performance, or actual booking-link fidelity. Those remain explicit acceptance work, not assumed passes.

## Decisions still needed

1. Initial public origin/party coverage and target launch date.
2. Acceptable acquisition/model/browser cost per completed plan and daily ceiling.
3. Provider access and permitted handoff for the first live route, including the outcome of a Duffel search-only discussion if pursued.
4. Whether Serverless Workers/zero-to-one scaling is a sponsor requirement for launch or can follow a continuously running worker.
5. Concrete initial-failure and in-flight-revision behavior for the automatic email deadline, plus contact/access/history retention periods.

These decisions can be made alongside increment 1; none prevents fixing the reproduced reliability defects now.
