# London → Lyon live planning slice

Implemented 7 September 2026. This advances the MVP from separate provider checks to a
live local planning experience. Public deployment and the other fixture routes remain later work.
Email styling remains deferred for frontend review.

## What is enabled

- Lyon away on 15 October 2026, with London–LYS direct flights and London–Paris–Lyon rail.
- Adults sharing one room. The form and API reject children and multi-room live requests until
  their pricing contracts have been validated. Other fixtures remain available in recorded mode.
- Flexible dates plus explicit earliest departure/latest return dates in London time, including
  correct daylight-saving offsets. Search considers at most three date pairs inside the window.
- Flight-only, train-only or mixed comparisons; budget/value/comfort ranking; private-room and
  private-bathroom requirements. Budget can include hostel dorm beds. Comfort is a ranking
  preference, not a luxury-hotel promise; privacy checkboxes are hard constraints.
- Dated property details for up to three shortlisted rooms. A private-bathroom filter is obtained
  from the actual Booking response, then each room requires explicit privacy evidence. A bathroom
  count alone does not establish privacy. Dates, adult count and room count must match.
- Alternative journey/stay combinations, transfer guidance, source/review dates and missing costs.
  User revisions select from/research the appropriate constrained shortlist. This is a bounded
  comparison of sampled options, not an exhaustive cheapest-fare search.

## Route evidence and practical limits

[Palace's published fixture announcement](https://www.cpfc.co.uk/news/announcement/revealed-our-europa-league-league-phase-opponents/)
supports the Lyon fixture date and 17:45 UK kickoff. Groupama Stadium remains **provisional**
until fixture-specific venue and away-supporter instructions are verified.

Flight planning accepts Lyon airport arrivals between 06:00 and 21:59 and departures between
08:00 and 22:59 local time. These are conservative application planning windows, not a live
transfer timetable. [Rhônexpress service guidance](https://www.rhonexpress.fr/en_GB/discover-the-service)
and [timetable information](https://www.rhonexpress.fr/en_GB/timetable) support the airport–Part-Dieu
connection. The dated PDF timetable found during review is labelled 2023 and is not represented
as a confirmed October 2026 schedule.

Rail acquisition queries four dated services: London–Paris, Paris–Lyon, Lyon–Paris and
Paris–London. It checks the individual service instruction's stations/times against the result's
outer time window, accepts direct services only, and joins Gare du Nord/Gare de Lyon connections
with **at least three hours** (and at most five) between trains. That is our conservative planning
policy, not a carrier-published minimum. [Eurostar's London–Lyon guidance](https://www.eurostar.com/uk-en/train/london-to-lyon)
describes the cross-Paris journey. Separate tickets do not automatically establish connection protection.

[OL Vallée access guidance](https://www.olvallee.fr/acces/) supports the Part-Dieu/La Soie stadium
shuttle patterns, event transport reservations and return arrangements. Exact Palace-match
shuttle hours/fares remain unconfirmed. Hotel-specific access, late check-in and return transfer
arrangements must still be checked. The app labels these trips as having outstanding checks.

## Price behavior

The existing simple Quote/Money records remain sufficient. Retrieved prices retain their
observation times, scope, party, tax treatment and currency. Round-trip flight prices are counted
once. Verified stay taxes are added where separately supplied. Mixed currencies or unverified
party scope are not silently combined.

Train offers retain the observed single-person indicative fare, but passenger/fare scope is not
proven, so they are excluded from the party subtotal. Local transfer fares are also excluded.
For a train trip, the known subtotal can therefore contain only accommodation. The UI explicitly
shows missing costs and warns against treating that subtotal as a full-trip comparison.

## Live validation

`scripts/validate-lyon-workflow.py` runs real Gemini and SearchApi Activities through a local
Temporal server and PostgreSQL, using preview-only delivery. It successfully exercised:

1. Initial mixed-mode value draft in **35.54 seconds**.
2. A real Gemini Q&A turn that left the itinerary unchanged.
3. Worker restart and recovery via a Temporal Query.
4. A cheaper, train-only revision in **28.42 seconds**, reusing cached train observations while
   acquiring the budget accommodation shortlist.
5. Finalization without additional research, repeated idempotent database-backed preview
   delivery, and complete Temporal history replay without new model/provider calls.

The run used 51 SearchApi requests (39 initial, 12 revision) and three successful model calls.
Local ignored evidence: `.data/lyon-live-workflow/results.json` and `history.json`.

The value draft selected easyJet Luton–Lyon flights and a private apartment for a **£342 known
subtotal**. The budget rail revision selected a hostel dorm; its **£43 known subtotal covered
only the stay**, with four separately shown indicative rail fares excluded from the party total.
These are observations from this validation, not guaranteed bookable prices.

A separate five-request comfort/private-bathroom search found a room explicitly named
“Double Room with Private Bathroom”; anonymous contract excerpts now cover positive privacy
checks and rejection of a mere bathroom count. Budget/value were exercised in the integrated
run. These tiers intentionally produce different shortlists and ranking penalties.

The first browser comfort request encountered incomplete provider responses and could not
produce a matching full trip. That exposed a resilience issue: a later failed detail request
could erase previously checked candidates. The adapter now preserves completed candidates
when another property/flight option fails, logs only sanitized engine/error/status information,
and allows 30 seconds per HTTP request within the existing bounded Activity. No automatic paid
retry was added. The failure page now clearly offers a new trip brief instead of implying a
usable itinerary exists. Provider failure remains a supported outcome.

## Runtime and next work

Local `.env` uses `PLANNER_MODE=live`, `TEMPORAL_TASK_QUEUE=cpfc-trip-v3` and
`EMAIL_MODE=preview`. Workflow type is `TravelPlanningSessionWorkflowV3`. Old development
sessions need their original worker/code; start a new session for this slice. No default gcloud
profile, ADC or production infrastructure was changed.

Next: user review of the frontend, broaden destination/party coverage, then production controls
and deployment. Complete pricing coverage, fixture-specific ground transport, public admission/
quota controls, retention/deletion, Cloud SQL/runtime IAM, Terraform, scaling/release operations,
Resend webhooks and launch-readiness checks remain required by the MVP plan.


## Final verification and account handoff

The full gate passed: **48 Python tests, four frontend tests**, Ruff, mypy, generated OpenAPI
consistency, TypeScript, ESLint and production static export. Chrome verified the dated form,
privacy and transport controls, authenticated session creation, polling and failure-page reload.
At this checkpoint successful itinerary-card/chat/reload browser validation was still pending.
The paid-plan continuation below completes that browser path.

The subsequent browser retest returned HTTP **429** for both hotel and flight engines. A read-only
call to [SearchApi's Account API](https://www.searchapi.io/docs/account-api) confirmed **0 remaining
credits**, **no active subscription**, and only 80 searches against a 200,000 hourly limit. The
blocker is account credits, not the hourly limit. Further live searches were paused until the user
activated a plan, as recorded below. No subscription was purchased or billing changed. The earlier
complete live workflow and private-bathroom validation succeeded before this exhaustion.

Use `uv run python scripts/validate-lyon-workflow.py --replay-only` for a cost-free check of the
saved live history. The new unqualified script invocation performs another paid validation.


## Paid-plan continuation — browser acceptance passed

After the user activated the paid plan, the Account API reported a 10,000-search monthly
allowance and an active subscription. Live searches succeeded. Its separate `remaining_credits`
field still returned zero, so that field alone must not be used to disable searches on a paid
subscription; consider the monthly allowance and usage as well.

Chrome session `03996a3a-9859-4296-ad34-ba7d1aeabf6e` completed the real frontend/API/Temporal flow:

- Submitted a comfort brief requiring both a private room and private bathroom. The resulting
  flight trip had a £338 known subtotal: £280 round-trip flight, £50 room and £8 stay taxes.
- Reloaded the page and recovered the same itinerary with the browser's authorization cookie.
- Asked what the subtotal included. Gemini correctly explained the components without changing
  the saved itinerary.
- Requested trains only and budget accommodation, explicitly releasing both privacy constraints.
  The cards updated to four dated rail services via Paris and a hostel dorm for 14–16 October.
  The £39 known subtotal was accommodation including taxes; indicative rail fares stayed excluded
  from the party total. This differs from the earlier £43 observation, illustrating price changes.
- Expanded two alternative stays, then finalized from the UI. The exact revision 2 itinerary was
  saved to PostgreSQL, one local preview delivery was recorded, and no further search Activity
  was scheduled after finalization. No real email was sent.
- Reopened the completed session and replayed its full Temporal history successfully.

This browser session made **54 SearchApi requests** and three Gemini calls. Evidence is ignored
locally under `.data/lyon-browser-validation/`: `history.json`, `snapshot.json`, and `checks.json`.
The completed preview is available in the same Chrome browser at
`http://localhost:3000/plan/?session=03996a3a-9859-4296-ad34-ba7d1aeabf6e`.

The earlier 48 backend/four frontend tests and production build remain the implementation gate;
this continuation required no application-code changes. The live Lyon milestone is now ready
for the user's frontend review. Wider fixture/party coverage and production readiness remain
as listed above; email styling is still deferred.
