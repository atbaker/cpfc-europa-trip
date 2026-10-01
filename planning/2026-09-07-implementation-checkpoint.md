# Gemini integration and continued MVP implementation

7 September 2026. **Gemini Flash 3.8 at low reasoning is now the approved and implemented model.**
The [main plan](mvp-plan.md) reflects this decision. This is a development checkpoint;
the public MVP is not complete or deployed.

## Completed in this implementation pass

- Replaced OpenAI model/configuration/dependencies with Pydantic AI's native Google Cloud
  adapter. Fixed model and low reasoning settings are versioned with the agent. Calls have
  a 4,096-token output limit and 40-second SDK / 45-second Activity time limits.
- Added explicit, refreshable local work-profile authentication. The `.env` selects
  `andrew-baker-sandbox`, `temporal-work`, `andrew.baker@temporal.io`, and model location `eu`.
  Production requires ADC with an attached runtime identity. Credentials stay out of logs,
  workflow inputs, and saved artifacts; no global ADC or default gcloud profile was changed.
- Isolated the new worker on task queue `cpfc-trip-v2` and workflow type
  `TravelPlanningSessionWorkflowV2`. Old development histories need their original worker;
  future production releases still require pinned immutable worker deployment versions.
- Added per-attempt model telemetry with token counts, elapsed time, and sanitized status.
  SDK retries are disabled; Temporal permits two model attempts. Permanent HTTP client
  errors are non-retryable. Raw prompts, provider bodies, and answers are not logged.
- Tightened airport output to catalog airport literals and bounded constraint counts.
  Explicitly preserve previous hard constraints. Revision acknowledgement remains code-owned;
  the model's premature “updated” wording cannot announce a successful itinerary commit.
- Search enumeration now considers the requested window, with at most three date pairs per
  route. Each fixture receives an initial candidate before alternatives consume the budget.
- Acquisition runs at most four Activities concurrently, deduplicates hotel searches across
  routes for the same dates/party, and retains bounded candidate results inside the workflow
  for reuse after preference changes and worker restarts. No Postgres polling projection or
  separate price cache was introduced. Original retrieval timestamps are preserved.
- Search adapter Activities now make one attempt, keeping worst-case paid requests within
  their pre-reserved call allowance. Partial failures do not discard other completed batches.
  Unsupported requirements are explained without paying for searches that cannot satisfy them.
- Fixed SearchApi Google Flights localization: live API rejects `hl=en-GB` with HTTP 400;
  `gl=GB`, `hl=en`, and GBP work. Browser links retain UK locale/currency settings.
- Hotel normalization rejects mismatched search/detail dates, handles singular night/adult
  summaries, and treats a dorm bed's capacity separately from a party's requested bed allocation.
  Dorm allocation remains explicitly subject to supplier confirmation.
- Started local Docker/PostgreSQL, aligned the ignored local database URL with Compose,
  and applied the Alembic schema. No cloud resources or billing configuration were changed.

## Validation and evidence

**Live Gemini through Temporal:** `scripts/validate-gemini-workflow.py` ran initial planning,
a price question, and a cheaper-trip revision using real Gemini and synthetic travel evidence.
A new Worker recovered the session before the final revision. Finalization and replay passed;
only three model attempts were logged, so replay did not repeat the calls. Output/history:
`.data/gemini-workflow/`. The delivery Activity was a no-send stub, not an actual email.

**Live SearchApi:** `scripts/validate-searchapi-adapters.py` obtained two complete round-trip
flight options and three dated stays for two adults in Lyon, 14–16 October 2026, in nine
successful adapter calls (plus preceding failed locale-diagnostic requests). Normalized evidence
is saved at `.data/live-adapters.json`. This is provider-adapter validation, not proof of a
complete trip including venue/late-night transfers.

The [official Palace fixture announcement](https://www.cpfc.co.uk/news/announcement/revealed-our-europa-league-league-phase-opponents/)
was rechecked and matches the four away dates/kickoff times in the catalog.

**PostgreSQL:** eight concurrent duplicate submissions returned one session. Four concurrent
delivery attempts produced one preview and one recorded attempt, exercising real row locks.
The tests clean up their own rows; no existing session data was deleted.

**Full gate passed:** 36 Python tests, three frontend tests, lockfile checks, Ruff formatting/lint,
mypy, generated OpenAPI/client drift checks, TypeScript, ESLint, and the production static build.
Two dependency warnings remain (Starlette/AnyIO deprecated alias and a Temporal sandbox
late-import warning); neither failed execution or replay.

**Reviewable email:** `.data/email-previews/lyon-live-review.html` and its companion JSON use
the acquired Lyon flight/hotel observations. The known subtotal is £532 for two adults,
including the observed hotel taxes; local transfers and other explicit gaps remain excluded.
No email was sent, no booking was made, and this does not mean that fare is still available.

## Credential handoff and remaining MVP work

### Eagles Away and Resend continuation, 7 September

**Email integration completed, 7 September 2026:** Chrome confirmed
`notifications.eaglesaway.com` Verified. Updated only the `cpfc-europa-trip` API key
from the obsolete `eaglesaway.com` scope to `notifications.eaglesaway.com`, preserving
Sending access. The local From domain matches and `EMAIL_MODE=preview` remains unchanged.

Ran the authorized `notifications-domain` validation case against the original saved Lyon
observations. Resend accepted receipt `c26ca831-9fce-47bd-84bc-ea278365059b`; repeating the
Delivery Activity returned that same receipt without a second send. Resend's dashboard
confirmed **Delivered** to the authorized test recipient at approximately 21:05 UTC.
The receipt is visible at https://resend.com/emails/c26ca831-9fce-47bd-84bc-ea278365059b.
Old rejected envelopes remain unchanged. No fresh travel/model calls were made.

The background check completed and is being paused. The original failed attempts and
initial approval rejection below are historical; the user subsequently authorized the
background scope correction and one test email, including pay-as-you-go charges.
Live webhook endpoint delivery remains separate deployment work.

- Adopted **Eagles Away** in the frontend wordmark/metadata, API title, email subject,
  README and main plan. **eaglesaway.com** is user-owned. Club expansion remains deferred;
  this changes the product identity without changing session/workflow identifiers.
- Resend key and sender are present, and the sender's domain is **send.eaglesaway.com**.
  The key is sending-only, so the read-only domain API cannot verify its domain configuration.
- Added `scripts/validate-resend.py`: render the saved Lyon observations without research;
  explicit `--send-to` uses the database-backed delivery Activity. Same evidence/recipient
  retries reuse the original submission, saved message and idempotency key.
- Freeze the sender and non-PII session tag with the email before the first send. Sanitize
  transport failures and receipts; distinguish retryable concurrent-key conflicts from
  permanent payload/key errors. Retry tests cover a lost HTTP receipt and changed runtime
  sender configuration while preserving the exact original request.
- Signed webhooks validate their shape, deduplicate events and serialize delivery updates.
  Complaints/bounces take precedence over delayed delivered events. The session tag can
  reconcile an accepted send whose HTTP receipt was lost; recipient/provider bodies are
  not persisted in webhook records.
- The user authorized their personal Gmail address for testing. The real send was rejected
  with HTTP 403: **“This API key is not authorized to send emails from send.eaglesaway.com.”**
  No email was accepted. Repeated diagnostic attempts used the same message/key. The app
  remains in `EMAIL_MODE=preview`; the frozen test delivery can resume after correcting the
  key's sending-domain scope. If `send.eaglesaway.com` is only a custom return-path domain,
  confirm the actual verified From domain before changing the frozen test envelope.
- The branded preview is `.data/email-previews/eagles-away-review.html`. A live webhook
  endpoint/secret is still needed at deployment; local tests use correctly signed synthetic
  events. Inbox delivery and live webhook processing have not been proven.
- Full gate passed after this continuation: **43 Python tests and three frontend tests**,
  including real PostgreSQL concurrency, Temporal restart/replay, email retry/signature/order
  cases, Ruff, mypy, generated API drift, TypeScript, ESLint and the production static export.

The earlier credential handoff below is retained for context; the current blocker is the
Resend key's sender-domain authorization, not a missing key or test-recipient consent.

The next email-integration step needs `RESEND_API_KEY`, a verified `RESEND_FROM_EMAIL`, and an
explicitly authorized test recipient. `RESEND_WEBHOOK_SECRET` is needed when wiring delivery
events. Keep `EMAIL_MODE=preview` until a real test send is authorized.

The local app remains in `PLANNER_MODE=recorded` deliberately: route templates are still
disabled pending complete transfer/venue evidence review. The live scripts demonstrate the
integrations without enabling incomplete route patterns in the user-facing app.

Work still required before public launch includes:

1. Reviewed/enabled fixture route patterns, complete connected rail and gateway transfers,
   operating-hours checks, and broader live party/room/children pricing validation.
2. Broader supported revisions, advanced date controls, accommodation shortlists/ranking,
   useful alternatives, and representative integrated four-fixture sessions.
3. Shared admission/quota controls, scrubbed observability beyond model logs, retention/deletion
   operations, and Cloud SQL IAM connector integration.
4. Terraform, images, frontend publisher, Serverless Worker release/scaling controllers,
   Frankfurt deployment, runtime IAM, and operational checks. The trip production project's
   billing is currently disabled; no deployment was attempted against the authorized spike sandbox.
5. Live email/webhook validation, final mobile/accessibility testing, and the commercial/privacy
   and public-launch checks retained in the main plan.


## Subsequent Lyon implementation

The [live Lyon slice report](2026-09-07-lyon-live-slice.md) supersedes the earlier disabled-route
and v2 runtime status above. Lyon is now enabled for local live planning on v3; email remains
preview-only. The earlier email delivery success and the deferred styling decision still stand.
