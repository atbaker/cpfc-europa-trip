# Eagles Away

A London-based travel planner for Crystal Palace supporters, supported by Temporal.
**A local, live London → Lyon vertical slice is implemented. The public MVP is not complete or deployed.**
Start with the [engineering handoff](planning/2026-09-30-engineering-handoff.md) for completed work,
remaining milestones and ownership transfer. The [MVP plan](planning/mvp-plan.md) defines the approved scope.

The app uses Gemini Flash 3.8, SearchAPI flight/hotel/train data, Temporal and PostgreSQL.
The Next.js frontend polls authenticated Temporal snapshots through FastAPI. Users get a
frozen itinerary with direct travel links; the app does not book travel or sell match tickets.
The domain is **eaglesaway.com**; the verified transactional sender uses **notifications.eaglesaway.com**.

## Start locally

Run commands from the repository root. Install these tools first:

| Tool | Development baseline | Purpose |
| --- | --- | --- |
| Python | 3.13.15 (`.python-version`) | API and Temporal worker; `uv` can install it |
| uv | Use a current release; installer validated with 0.12.21 | Locked Python environment |
| Node.js / npm | 22.23.3 / 10.9.9 (`.node-version`) | Frontend; Node 22.13.1+ required |
| Temporal CLI | Validated with 1.8.3 | Local server and workflow-test servers |
| Docker with Compose | Running daemon required | PostgreSQL 17.11 |
| gcloud CLI | Optional for sample mode | Explicit work-profile login for live Gemini |

On macOS, the Temporal CLI can be installed with `brew install temporal`.
Older uv releases may not know the pinned Python patch: update uv using its original
installation method, or install Python with `uvx --from uv uv python install 3.13.15` first.
Use your preferred version manager to select the checked-in Node version (for example,
`nvm install "$(cat .node-version)" && nvm use "$(cat .node-version)"`).

```bash
scripts/dev/setup.sh
scripts/dev/postgres-up.sh
```

Setup installs the locked dependencies, copies both environment examples when absent, and
creates local encryption/access secrets. Rerunning it preserves existing credentials and
custom settings. Obsolete shipped v1/v2 task queues migrate to v3. No cloud profile is activated.

Start each service in its own terminal:

```bash
scripts/dev/temporal-server.sh
scripts/dev/api.sh
scripts/dev/worker.sh
scripts/dev/frontend.sh
```

| Service | Address |
| --- | --- |
| App | [localhost:3000](http://localhost:3000) |
| API / API documentation | [localhost:8000/docs](http://localhost:8000/docs) |
| API readiness | [localhost:8000/readyz](http://localhost:8000/readyz) |
| Temporal UI | [localhost:8233](http://localhost:8233) |
| Temporal service | `localhost:7233` |
| PostgreSQL | `localhost:5432` (local-only `cpfc` database/user/password) |

A fresh checkout uses **`PLANNER_MODE=recorded` and `EMAIL_MODE=preview`**. Synthetic trips and
prices are labeled; no paid APIs or real emails are used. Preview HTML is written to
`.data/email-previews/`. The existing developer's ignored `.env` currently selects live
planning with preview email; those settings do not transfer to a new checkout.

Stop the four processes with Ctrl+C in their terminals, then `docker compose stop postgres`.
Local Temporal history persists in `.data/temporal.db`; PostgreSQL persists in its Docker volume.
Do not use `docker compose down --volumes` unless you intend to delete the local database.

### Without Docker

SQLite is available for sample UI development. It does not validate PostgreSQL migrations,
row locking or the production database design. Start the Temporal server and frontend as above,
then use these commands in separate terminals:

```bash
scripts/dev/preview.sh migrate
scripts/dev/preview.sh api
scripts/dev/preview.sh worker
```

These commands override planning/email modes only for their own processes. Do not run the
normal API/worker alongside them on the same ports/task queue.

## Enable live planning

Only the reviewed Lyon routes are enabled: London–LYS flights and London–Paris–Lyon rail,
adults sharing one room. Children, multiple rooms and the other three fixture destinations
remain unsupported in live mode. Venue and match-specific transfers still have outstanding
checks. Quotes are retrieved planning estimates with missing costs explicitly disclosed.

Put secrets in the ignored root `.env`, never in frontend `NEXT_PUBLIC_*` variables.
Configure your own team account/project rather than depending on the previous engineer's login:

```bash
# Create a named profile only if it does not already exist.
gcloud config configurations create eagles-away-work --no-activate
gcloud auth login YOUR_WORK_EMAIL --configuration=eagles-away-work --no-activate
```

Set these values in `.env`:

```dotenv
PLANNER_MODE=live
SEARCHAPI_API_KEY=YOUR_SEARCHAPI_KEY
GOOGLE_AUTH_MODE=gcloud
GOOGLE_CLOUD_PROJECT=YOUR_APPROVED_PROJECT
GOOGLE_CLOUD_LOCATION=eu
GOOGLE_GCLOUD_CONFIGURATION=eagles-away-work
GOOGLE_GCLOUD_ACCOUNT=YOUR_WORK_EMAIL
EMAIL_MODE=preview
```

The account needs access to the configured project's Gemini model and enabled billing/API.
The application fixes the model to `gemini-3.8-flash` with LOW thinking; authentication alone
does not prove model access. The local adapter refreshes the explicit account without changing
the default gcloud profile or Application Default Credentials. The current developer uses
`temporal-work`, `andrew.baker@temporal.io`, and `andrew-baker-sandbox`; these are historical
local settings, not required team identifiers. Production uses ADC and an attached service account.

```bash
# Presence/configuration only; prints no secrets.
uv run --locked python scripts/check-credentials.py
# Refresh Google credentials and check SearchAPI quota; no paid searches/model calls or email.
uv run --locked python scripts/check-credentials.py --check-live
```

Restart both API and worker after changing planning mode; restart the worker for provider changes.
SearchAPI's separate `remaining_credits` can be zero on a paid subscription: check monthly
allowance minus usage too. Account verification does not prove every search engine works.

### Email

Keep `EMAIL_MODE=preview` for routine development. `EMAIL_MODE=resend` performs actual delivery
and needs `RESEND_API_KEY` and a verified `RESEND_FROM_EMAIL`. A sending-only key must be scoped
to the actual From domain. `RESEND_WEBHOOK_SECRET` is needed for signed delivery-status webhooks;
its live setup is still TODO. Email styling remains deferred for frontend review.

The frozen itinerary is persisted and rendered without another research pass. The outbox
freezes the sender/content/idempotency key before sending; ambiguous sends are never retried
under a new identity after the safe retry window. Existing real delivery was validated in
September; a fresh engineer should use previews unless an actual send has been authorized.

## Validate changes

Stop the frontend dev server before the full gate: `next dev` and `next build` share `.next`.
With PostgreSQL running and migrated:

```bash
TEST_DATABASE_URL=postgresql+asyncpg://cpfc:cpfc@localhost:5432/cpfc scripts/check.sh
```

The gate checks the Python lockfile, Ruff, mypy, domain/provider contracts, Temporal execution,
restart/replay, API authorization, email idempotency, generated OpenAPI client drift, TypeScript,
ESLint, frontend tests and production static export. Tests use synthetic travel/mock model data.
**Omitting `TEST_DATABASE_URL` skips the two PostgreSQL concurrency/locking checks.** Do not
point tests at a shared/production database. Workflow tests need the Temporal CLI but start their
own servers; they do not need the main local server or API/worker.

The frontend exports `/`, `/plan/` and `/privacy/`. Production requires
`NEXT_PUBLIC_API_ORIGIN=` at build time for same-origin API calls; local `.env.local` points
to port 8000. No production Node server is part of the plan.

For a deliberate paid integration run:

```bash
# Live Gemini and travel searches; isolated Temporal server, configured PostgreSQL, preview only.
# Budget for up to 128 SearchAPI requests and bounded model retries; normally ~50 searches/3 turns.
uv run --locked python scripts/validate-lyon-workflow.py
# Live Gemini with synthetic travel data; no real email.
uv run --locked python scripts/validate-gemini-workflow.py
# At most ten live SearchAPI requests; no model/email calls.
uv run --locked python scripts/validate-searchapi-adapters.py
```

Local output is ignored under `.data/`. `validate-lyon-workflow.py --replay-only` needs history
from an earlier successful run. `validate-resend.py` also needs saved observations from
`validate-searchapi-adapters.py`; it is an optional integration tool, not a fresh-checkout prerequisite.
Its `--send-to` flag makes a real send. Repeating the same case/evidence/recipient resumes the
original delivery; never change `--case` to work around an uncertain delivery outcome.

Python dependencies are pinned in `uv.lock`; frontend dependencies in `frontend/package-lock.json`.
Use locked setup for normal development. Update dependencies deliberately and rerun the gate
and relevant saved-history replay, especially for Temporal/Pydantic AI upgrades. SDK major
versions are bounded in `pyproject.toml`. There is no CI workflow yet; adding this gate to CI is
part of the handoff TODOs.

## Troubleshooting

- **Google authentication failed:** refresh the selected work account with
  `gcloud auth login YOUR_WORK_EMAIL --configuration=YOUR_PROFILE --no-activate --force`,
  rerun `check-credentials.py --check-live`, and start a new planning session. A successful login
  still needs project/model permissions. No default-profile or global ADC change is necessary.
- **Draft stays pending / Query unavailable:** check the worker is running and the API/worker use
  the same queue. Current type is `TravelPlanningSessionWorkflowV3`, queue `cpfc-trip-v3`.
  Existing v1/v2 sessions require their original code/worker; use a new session for current code.
- **SearchAPI 401/429 or partial results:** check key, subscription/quota and worker's sanitized
  engine/status logs. Unsupported fares/rooms and missing provider evidence remain explicit gaps.
- **Page cannot load catalog:** check ports 8000/3000, `FRONTEND_ORIGIN`, and
  `frontend/.env.local`; restart the frontend after changing build-time environment values.
- **Session URL says not found:** use the same browser and hostname that created it. The URL ID
  is public; the authorization cookie is separate. Copying a URL alone does not transfer access.
- **Port already in use:** stop this project's previous processes before restarting. Adjusting
  `POSTGRES_PORT` also requires matching `DATABASE_URL` and `TEST_DATABASE_URL`.

`/readyz` checks database and Temporal service connectivity, not worker availability or paid
provider readiness. Use a real planning flow to verify the complete stack.

## Code and planning map

| Area | Location |
| --- | --- |
| API, configuration, typed domain | `src/cpfc_trip/{api,config,domain}.py` |
| Fixture/route catalog | `src/cpfc_trip/data/catalog.json` and `catalog.py` |
| Gemini interpretation, ranking, provider normalization | `src/cpfc_trip/planner/` |
| Workflow, Activities, worker | `src/cpfc_trip/temporal/` |
| Database/outbox, migrations, email | `src/cpfc_trip/persistence/`, `migrations/`, `emailing.py`, `resend.py` |
| Form, polling/chat, itinerary UI and generated client | `frontend/` |
| Tests and local/integration tools | `tests/`, `scripts/` |

Useful history: [provider spike](planning/2026-09-06-searchapi-spike.md),
[Gemini spike](planning/2026-09-07-gemini-spike.md),
[live Lyon slice](planning/2026-09-07-lyon-live-slice.md),
and [approved simplifications](planning/2026-09-06-mvp-simplifications.md).
These are dated evidence, not guarantees about current fares or provider behavior.
The older standalone `gemini_spike.py` and `searchapi_spike.py` default to dry runs; their
`--live` flags consume paid usage (the Gemini spike makes 40 calls).

Entire is enabled with manual commits. Trust hooks only after reviewing their local configuration;
it is not required to run the app. This handoff includes the rebuilt implementation and
deliberate deletions of the obsolete implementation/infra. Ignored `.env`, `.data/`, local credentials and database volumes are
not part of a clone. Transfer needed secrets through the team's approved secret-management process.
