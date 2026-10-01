# Engineering handoff and MVP completion map

30 September 2026 handoff review; final checks continued into 1 October. Assessed against the current [approved MVP plan](mvp-plan.md), source,
local checks and new live validation. **The working deliverable is a local London → Lyon
vertical slice. The complete public CPFC MVP is not deployed or launch-ready.**
Historical checkpoints describe earlier versions; this document is the current ownership guide.

## Milestone status

| Original milestone | Status | Completed | Still required |
| --- | --- | --- | --- |
| **0 — provider choice, polling and infrastructure validation** | Partial | SearchAPI accepted for flights/hotels/trains; Gemini selected; typed price snapshots/direct links; London catalog; durable structured output → authenticated Query → browser; pinned dependency locks. | Commercial display/cache/email/link permissions; confirmed fixture venues and match transfers; complete enabled-pattern coverage; Terraform state and initial edge/API topology; deployed minimum-worker/Query resilience proof. |
| **1 — one-fixture vertical slice** | Implemented locally; strict exit evidence incomplete | Live Lyon adult/one-room slice; all three tier logic; flight/rail/stay adapters; durable Gemini; form/cards/chat; polling/reload; finalization/preview outbox; deterministic restart/replay, timeout and idempotency checks; earlier authorized Resend receipt. | Exact acceptance exercise combining worker termination **during** a paid model Activity, API/browser restart and one real email; mobile E2E proof. Today's restart occurs between turns, not during the model call. |
| **2 — complete CPFC MVP** | Partial | Lyon enumeration/ranking, privacy constraints, scoped estimates/missing-cost copy, atomic Q&A/revisions, branded basic UI and email, curated provider-contract tests. | Live Katowice/Beşiktaş/Mainz routes; representative party coverage including children/multiple rooms; confirmed transfer guidance; cross-fixture/tier coverage/cost scenarios; email styling and finalized privacy/brand copy; mobile accessibility/Web Vitals/bundle gates; broader reviewed examples and Logfire traces. |
| **3 — production hardening and launch** | Not implemented as a deployed system | Some application prerequisites exist: session auth/origin checks, bounded sessions/paid calls, immutable-version worker configuration, signed webhook handler and idempotent delivery. | GCP/Temporal Cloud infrastructure, releases and CI; scale/load/reconnect/rollback tests; shared abuse controls; retention/deletion jobs/runbooks; observability and alerts; live webhooks; permissions/privacy/terms/brand launch review. |
| **4 — expansion** | Deferred by design | Product name is reusable beyond Palace. | Other clubs/departure regions/combined trips and additional evaluation or compaction only when justified by measured usage. |

“Implemented” means present and exercised for the stated slice. It does not mean every fixture,
party, provider result or production failure case has been validated. The original acceptance
criteria remain the launch checklist; this report does not remove them.

## Completed capability map

| Capability | Implementation and evidence | Boundary |
| --- | --- | --- |
| Request/catalog/domain | `src/cpfc_trip/domain.py`, `catalog.py`, `data/catalog.json`; frozen, bounded Pydantic records; four fixture entries. | Live API advertises only enabled Lyon routes. Venues are provisional; evidence dates must be revisited before launch. |
| Model interpretation | `planner/agent.py`, `google_auth.py`, `metered_google.py`; Gemini `gemini-3.8-flash`, LOW; Pydantic AI Temporal integration; project/profile-specific local refresh and token/attempt telemetry. | Model interprets constraints/Q&A; application code owns itinerary facts, ranking and commits. Team cloud access and production ADC/IAM still need setup. |
| Travel acquisition | `planner/providers/searchapi.py`; constrained Flights/Booking.com/Google train adapters, bounded calls, normalized evidence, dated occupancy, private-room/bathroom checks and safe external links. | Only London–LYS and London–Paris–Lyon reviewed routes. No browser fallback or second provider. Empty/incomplete provider results can still produce a gap or failure. |
| Feasibility and ranking | `planner/planning.py`, `prices.py`, `links.py`; date enumeration, up to three date pairs, match buffers, transfers, budget/value/comfort ranking and cached candidate reuse. | Sampled comparison, not exhaustive cheapest-fare optimization. Dorm/shared-bathroom stays are valid when permitted; private-room/bathroom requirements are hard constraints. |
| Prices and handoffs | Money/Quote records retain retrieval time, currency, tax/party scope and evidence; round-trip prices counted once; normalized observations live with itineraries. | No separate price store/cache required. Unverified rail passenger scope and local transfers are excluded from the subtotal; a rail subtotal can be hotel-only. Google Flights search/itinerary links satisfy the approved handoff. |
| Durable session | `temporal/workflow.py`, `activities.py`, `worker.py`; type `TravelPlanningSessionWorkflowV3`, queue `cpfc-trip-v3`; idempotent Updates and direct Query snapshots. | Local restart/replay proven. Production routing/version lifecycle and minimum one worker are planned, not deployed. Queries require an available worker; `/readyz` alone does not check that. |
| Work budgets | Initial 180s/follow-up 90s, 30-minute interaction lifetime, default 10-minute inactivity, ten follow-ups; reserved SearchAPI/model budgets and bounded Activity attempts. | Per-session safeguards do not replace shared admission controls or real load/latency testing. |
| UI/polling | `frontend/components/`, `frontend/lib/api.ts`; form, cards, alternatives, chat, revision-aware reconciliation; polling slows while idle/pauses hidden/stops terminal. Static `/`, `/plan/`, `/privacy/` export. | Four small frontend unit tests plus manual browser evidence; no automated browser/mobile or deployment/rollback suite. Design/email review is outstanding. |
| Database/session security | `persistence/`, `migrations/`; PostgreSQL sessions, encrypted contact, access-token hash, saved final itinerary, delivery outbox and webhook events; HttpOnly session cookies and origin checks. | No separate Postgres live-progress projection. Current database engine uses a normal connection URL; Cloud SQL IAM connector/pooling configuration still needs implementation. |
| Email/finalization | `emailing.py`, `resend.py`, database-backed delivery Activity; frozen request/hash/sender/session tag and stable provider idempotency; bounded ambiguous-send handling; manual/inactivity/limit/failure paths. | `notifications.eaglesaway.com` delivered one authorized test in September. Today's validation is preview-only. Live signed webhook delivery/status reconciliation, monitoring and polished templates remain TODO. |
| Quality checks | `scripts/check.sh`: Python types/lint/51 tests, provider excerpts, Temporal tests, real Postgres concurrency, generated API drift, TS/lint/four UI tests and export. | Local gate only; no CI configuration or curated 20–30-scenario end-to-end set. Passing contract excerpts does not establish full live travel coverage. |

## Validation performed for this handoff

- Updated runtime pins within their existing families: Python **3.13.3 → 3.13.15** and
  Node.js **22.13.1 → 22.23.3** (npm 10.9.9). Installed alongside existing runtimes without
  changing the user's default Node alias or cloud profile. Official releases:
  [Python 3.13.15](https://www.python.org/downloads/release/python-31315/) and
  [Node 22.23.3](https://nodejs.org/en/blog/release/v22.23.3). The older installed uv could not
  download this Python release, so a temporary uv **0.12.21** installer was used.
- Reinstalled from both lockfiles with `scripts/dev/setup.sh`. Added three setup regression tests:
  new-clone defaults/idempotence, preservation of credentials/custom settings, and migration of
  obsolete defaults. Setup creates the frontend environment file only when absent.
- Updated local PostgreSQL **17.6 → 17.11**, retaining the Docker data volume; migration passed.
  This stays within the existing PostgreSQL major version. See the
  [official 17.11 release notes](https://www.postgresql.org/docs/17/release-17-11.html).
- Updated Next.js/its lint config to **16.3.8**, React/React DOM to **19.3.0**, Vitest to
  **4.1.11**, and compatible frontend transitive dependencies. Changed Vitest config to `.mts`
  and explicit test discovery. Updated vulnerable Python `urllib3` **2.7.0 → 2.8.0**.
  Kept validated Temporal **1.32.0** and Pydantic AI **2.40.0**, adding major-version bounds.
- Full local gate passed: **51 Python tests (including both Postgres concurrency tests),
  four frontend tests, formatting/lint/type checks, generated API drift and static export**.
  The full Python gate was rerun on Python 3.13.15; frontend types/lint/tests/build
  were separately rerun on Node 22.23.3 after the final dependency/config changes.
  Real Gemini initial/Q&A/revision, restart and replay also passed on Python 3.13.15
  with synthetic travel evidence and no actual email send.
- `npm audit` and `pip-audit` on the final locked dependency sets reported **zero known
  vulnerabilities**. Ignored audit files are `.data/*audit-final-2026-09-30.json`.
  These point-in-time advisory checks are not a general application security audit.
- Google work-profile credential refresh passed after the user renewed login. SearchAPI
  Account API reported **76/10,000 monthly requests used** before validation, with the separate
  credits field zero. Paid searches succeeded. Neither the default profile nor ADC was changed.
- `validate-lyon-workflow.py` passed using real Gemini/SearchAPI, actual PostgreSQL and an
  isolated local Temporal server. Initial draft **64.84s**, question without itinerary changes,
  worker replacement between turns, budget train-only revision **30.42s**, finalization,
  repeated idempotent preview delivery and history replay. Three successful model attempts.
  A separate `--replay-only` also passed without paid calls. Local evidence:
  `.data/lyon-live-workflow/{results,history}.json` (128 history events, about 626KB JSON).
- The new flight draft had a **£341 known subtotal**. Its train revision had a **£39 known
  subtotal**, covering accommodation while rail/transfer gaps remained disclosed. These are
  observations from this run, not current guaranteed offers. This test does not validate all tiers.
- Started the main Temporal server/UI, PostgreSQL, API, live worker and frontend. API `/readyz`
  passed and catalog exposed only Lyon. Browser acceptance evidence is recorded below.

### Dependency maintenance exceptions

ESLint **9.39.5** remains deprecated upstream. The current Next.js lint configuration bundles
React/import/accessibility plugins whose peer ranges exclude ESLint 10; an attempted upgrade
produced invalid peers and was reverted. `npm ci`, lint and audit pass with 9.39.5. Revisit when
those plugins support 10; do not hide the mismatch with `--force`/`--legacy-peer-deps`.
`whatwg-encoding` also emits a transitive deprecation warning through the current jsdom stack.
Python checks retain the existing Starlette/AnyIO alias and Temporal sandbox late-import warnings;
execution and replay pass. Unrelated major tool/runtime upgrades were not forced during handoff.

### Browser acceptance for this pass

The in-app browser submitted a live, value-tier flight-only Lyon brief using a synthetic test
address. It displayed dated easyJet round-trip flights, a two-night stay/taxes, £341 known
subtotal and outstanding transfer/venue checks. Reload restored the same session and cards.
Gemini explained the subtotal components and missing costs without changing the itinerary.
Manual finalization reached “Development email preview saved locally. No email was sent.”
Session: `19d36c12-a57d-46c6-b87a-cc80f6715606`; the URL alone does not grant access.
Chrome automation was initially unavailable, so the complete flow used the in-app browser.
After runtime updates, native Chrome confirmed the running home page, loaded Lyon catalog
and enabled form. The in-app browser reported a connection error after the deliberate restart
while direct HTTP and native Chrome succeeded; final restart recovery in that browser was not proven.
The initial catalog request showed a transient unavailable state; a reload recovered, and the
subsequent complete flow succeeded. Broader automatic initial-load recovery is not proven.
Screenshot: `.data/handoff-browser-2026-09-30.png`. Additional history/database evidence is
kept locally under `.data/handoff-browser/`; the final itinerary matched its saved PostgreSQL
record, one preview delivery attempt was recorded, and browser history replay passed on
Python 3.13.15. None of this ignored evidence is a clone prerequisite.

## Remaining work, in recommended order

1. **Take ownership of the committed rebuild and services.** The handoff commit brings the
   rebuilt app and historical planning additions into version control, including deliberate
   deletions of obsolete implementation/infra. The review began with this work uncommitted on
   `main`; those original commits did not contain the current app. Conclusions here come from
   current code, tests and dated reports, rather than historical checkpoint coverage of the
   rebuild. Entire is enabled; review its local hooks/trust on the new machine.
2. **Refresh and complete travel coverage.** Confirm official fixtures/venues and match-specific
   stadium/late-night/check-in/transfer guidance. Lyon is only two weeks away at this handoff date.
   Enable Katowice, Beşiktaş and Mainz only after adapter/route evidence is adequate; validate
   each tier, dates and representative party shapes. Children/multi-room support must prove
   occupied hotel and fare scope first. Measure costs and latency, direct-link longevity,
   price/tax/baggage drift and missing widgets. Keep unsupported patterns disabled.
3. **Finish product acceptance.** Review frontend with the owner, then revisit email styling.
   Complete privacy/operator/retention/contact and sponsor/brand/terms copy; `/privacy/` is
   currently a development placeholder. Run reviewed multi-scenario checks, accessibility,
   keyboard/mobile reload and performance budgets. Prove last-valid-state recovery across
   worker death during an Activity and API/browser interruption. One preview and a historic
   real send do not substitute for the complete launch acceptance exercise.
4. **Build the production platform and CI.** Reimplement Terraform for regional resources in
   **GCP `europe-west3`**, Temporal Cloud **`gcp-europe-west3`**, Cloud SQL IAM, Secret Manager,
   Cloud Run API and Serverless Worker pool with minimum one worker, and global static
   Storage/CDN/HTTPS routing. Add separate frontend publisher and worker release controller,
   immutable versions, replay/canary/rollback gates, database migrations and connection budgets.
   Add the existing check script to CI and infra validation once infra exists. Gemini model
   location `eu` is distinct from the regional GCP infrastructure setting.
5. **Finish operational and launch controls.** Implement shared admission/IP/email/cost limits,
   edge protection and provider kill-switch operations; local in-process rate limits are
   insufficient across instances. Add Logfire instrumentation (library installed, full traces
   not wired), metrics/alerts, source/billing monitoring, retention/deletion cleanup and key
   rotation/reconciliation runbooks. Configure signed live Resend webhooks; secret is currently
   absent. Exercise load, scale-out, Query latency, cold CDN, deploy/open-tab/rollback and outages.
   Confirm SearchAPI commercial rights and security/privacy/brand readiness before public launch.

The approved simplifications still apply: polling directly through Temporal, ordinary stored
price snapshots, no human concierge, no browser tooling/fallback, direct outbound links, short
bounded sessions and no extra research at finalization. These are decisions, not missing features.
Broader clubs/combined trips/origins and conversation compaction remain post-MVP scope.

## Ownership and operational handover

Use [README.md](../README.md) for fresh local setup, ports, profile login, checks and shutdown.
A new clone needs no private `.data` artifacts or API keys for recorded/preview mode. SQLite
preview is optional; use PostgreSQL for the full verification gate.

Transfer through the team's secret-management process: SearchAPI account/key/plan owner,
GCP project IAM/billing/model entitlement, Resend key/sender/webhook management,
`eaglesaway.com` registrar/DNS access and renewal responsibility. Decide ownership for the
production Temporal Cloud namespace and GCP deployment identity; this pass did not provision
or verify a production environment. Preserve encryption keys when retaining existing encrypted
contact records; replacing the local key would make those records unreadable. Production secret
rotation needs a deliberate migration policy.

Ignored `.env`, `frontend/.env.local`, `.data/`, gcloud tokens and Docker volumes are not committed
handoff assets. Saved-history/live-provider scripts require their documented local evidence;
regenerate it deliberately or transfer scrubbed evidence as appropriate. Tests contain small
credential-free excerpts. Do not commit raw provider payloads, browser access tokens or previews
containing real addresses. Routine validation should remain preview-only.

The September 7 [implementation checkpoint](2026-09-07-implementation-checkpoint.md) and
[Lyon live-slice report](2026-09-07-lyon-live-slice.md) retain historical provider/Chrome/Resend
proof. Older v1/v2 type/queue/sender references in those reports are historical, not current setup
instructions. Active old workflows need their original workers; a new engineer should start
fresh v3 development sessions. Production version retention/decommissioning is still TODO.
