# Rebuild checkpoint — 6 September 2026

Follow-up: see the [7 September implementation checkpoint](2026-09-07-implementation-checkpoint.md)
for the adopted Gemini provider, completed live model validation, and PostgreSQL checks.
The OpenAI credential handoff below is historical and no longer applies.

Status: local development slice implemented; paused at the credential handoff before live
model/provider integration. **The public MVP is not complete.** The [approved plan](mvp-plan.md)
continues to define the intended final behavior. This checkpoint records implementation
coverage and remaining work; it does not reduce the approved scope.

## Implemented

- Python 3.13 / uv project with locked dependencies; Pydantic AI 2.40.0, Temporal SDK 1.32.0.
- Capability-based `TemporalDurability`, `PydanticAIWorkflow`, and `PydanticAIPlugin`.
  One structured interpretation run executes durably inside the workflow. Model requests
  are Activities, SDK retries are disabled, and Temporal permits at most two attempts.
- Bounded session workflow with short acceptance Updates, read-only snapshot Queries,
  atomic commits, duplicate message receipts, last-valid-plan preservation, inactivity/manual/
  hard-limit finalization, and a separate bounded email retry policy.
- Server-owned fixture and route snapshots, small date enumeration, initial deterministic
  schedule/room/airport gates and ranking. All candidate route templates remain disabled
  until reviewed. Synthetic development mode exercises the same session/UI contracts.
- Three SearchApi adapters with bounded response sizes/calls, no browser fallbacks, no
  raw provider records in workflow results, explicit missing evidence, and direct links.
- Flight discovery → return token → booking token normalization; complete selected directions,
  UK/GBP Google Flights URL parameters; direct flights only until connecting-airport handling
  is implemented. Hotel room identity matching and dates/occupancy in Booking links. Rail date,
  endpoint and aware-time validation; single-person observations are not multiplied into group fares.
- Durable normalized price snapshots, deduplicated round-trip costs, separate excluded taxes,
  and explicit unknown party/currency coverage. No separate price cache.
- FastAPI session creation, authorization, direct Query polling, message/finalize Updates,
  basic per-process throttling, origin checks, no-store responses, signed/deduplicated Resend
  webhook handling, and health/readiness endpoints.
- SQLAlchemy records and Alembic initial migration for encrypted contact data, access hashes,
  saved itineraries, and durable unique email deliveries. No separate active polling projection.
- Escaped text/HTML email from the frozen itinerary; stable session-level Resend key,
  payload consistency checks, and refusal to resend ambiguous outcomes after 23 hours.
  Local preview mode writes HTML without sending mail.
- Static Next.js/React frontend, generated OpenAPI schema types, London brief, typed trip cards,
  completed-message chat, pending-message reconciliation, backoff/visibility-aware polling,
  direct `/plan/?session=…` reload, and clear sample/freshness/coverage labels.

The initial planner is deliberately constrained: its structured output interprets supported
preferences and questions, while code performs travel acquisition and selection. Unsupported
hard requirements fail closed. Broader revision handling, richer synthesis, alternatives, and
selective re-search still need implementation and live evaluation.

## Validation completed

- Recorded September 6 spike excerpts verify the easyJet two-adult round trip, £59 hotel plus
  £9 taxes and exact Twin Room identity, and a £58 one-person Eurostar observation with
  different London/Paris offsets. Mismatched dates and unsafe outbound domains are rejected.
- Local Temporal execution verifies duplicate commands, unchanged Query responses, inactivity
  preservation, fresh-worker recovery, replay, manual/automatic finalization, failure notices,
  and bounded public payloads. A mocked OpenAI Responses call also verifies that the Pydantic
  model runs as a durable Activity, remains Query-responsive, and is not repeated on replay.
- Database/email tests verify encrypted contact storage, no contact email in workflow inputs,
  idempotent submission/access, one frozen delivery record, changed-payload rejection, and
  expiration of ambiguous email attempts. Database tests currently use isolated SQLite.
- 27 Python tests and 3 frontend tests pass, along with lint/type checks, generated OpenAPI drift checks and the static build.
- Chrome smoke test: submit a London–Lyon sample, render trip cards, submit a follow-up,
  reload the fixed plan route and recover the same conversation, finalize to an email preview.
  A schema edit during the running preview required an API/worker restart; the session then recovered to its terminal preview state. Query failures now return a sanitized retryable error.
  No paid provider/model calls or real email sends were made during this rebuild checkpoint.

Docker was not running, so PostgreSQL migration/locking behavior is **not yet validated**.
The local browser preview used `.data/browser-preview.db` and a separate local Temporal database.
No cloud resources were created or deployed.

## Next credential handoff

Add `OPENAI_API_KEY` to the ignored root `.env`. SearchApi is already configured.
For delivery integration, also supply `RESEND_API_KEY` and a verified `RESEND_FROM_EMAIL`;
otherwise retain local previews. No actual email test should run until its recipient/send is
explicitly authorized. Cloud credentials can wait for the infrastructure milestone.

## Remaining work before claiming Milestones 0–2 complete

1. Review official fixture/venue data and local/late-night transfers; validate SearchApi on
   actual fixture dates and enable only evidenced route patterns. Implement connected rail
   through Paris, Warsaw and Munich, and prove complete destination/return feasibility.
2. Run live model tests. Expand supported instructions, correct date-window search enumeration,
   selective revisions, accommodation/party cases, useful alternatives and ranking quality.
   Validate supplier parameter contracts for children, infants, occupancy, fees and connections.
3. Improve failure diagnostics without logging sensitive prompts/provider payloads. Add Logfire
   with explicit scrubbing, per-session actual paid-attempt/cost metrics, shared admission/quota
   limits and dynamic engine disable controls. The current throttle is local-process only.
4. Validate PostgreSQL migrations, concurrent submissions and ambiguous-send locking. Complete
   Cloud SQL IAM connector wiring, retention/deletion administration, and agreed privacy copy.
5. Implement Terraform bootstrap/Frankfurt topology, private Cloud SQL, runtime identity/secrets,
   immutable images, static publisher and Serverless Worker release/scaler controllers. Validate
   WCI scaling and one warm instance for each version serving pinned sessions. No infrastructure
   milestone is claimed by the local worker's versioning configuration alone.
6. Expand timer/race/cancellation/time-skipping tests, provider partial-failure tests, maximum
   four-fixture/ten-turn history/load tests, mobile accessibility/performance checks, and the
   curated scenario suite. Confirm email delivery/webhooks with authorized live tests.
7. Public-launch commercial/privacy/security review and operational runbooks remain as planned.
