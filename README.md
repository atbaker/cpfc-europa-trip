# Crystal Palace Away Days

A mobile-first, durable Europa League away-trip planner sponsored by Temporal in partnership
with Crystal Palace Football Club.

The current local build is a working vertical slice. A supporter can choose any of Palace's
four away fixtures, submit a short trip brief, watch durable progress over SSE, receive a
structured itinerary, request a cheaper or more comfortable revision, and finalize exactly one
preview email. The checked-in provider uses clearly labelled illustrative routes and estimates;
it never presents demo data as live inventory.

The approved product and architecture plan is in [planning/mvp-plan.md](planning/mvp-plan.md).

## Architecture

- `frontend/`: Next.js App Router, React, strict TypeScript, and a static `out/` export.
- `src/cpfc_trip/api.py`: FastAPI JSON/SSE API and HttpOnly session-cookie boundary.
- `src/cpfc_trip/temporal/`: one long-lived Entity Workflow per planning session, Workflow
  Streams, Pydantic AI's capability-based Temporal integration, revisions, and inactivity email.
- `src/cpfc_trip/persistence/`: PostgreSQL rows for contact PII, access credentials, and email
  idempotency only. Itinerary process state remains in Temporal.
- `src/cpfc_trip/planner/`: deterministic local planner plus the Terra/medium Pydantic AI path.
- `infra/`: Terraform for the eventual GCP environment. Nothing is applied automatically.

## Local prerequisites

- Python 3.13 and [uv](https://docs.astral.sh/uv/)
- Node 24.15 or newer in the Node 24 LTS line
- Docker with Compose
- [Temporal CLI](https://docs.temporal.io/cli)
- Terraform 1.8 or newer

## First run

Install dependencies:

```bash
make setup
```

Start these in separate terminals:

```bash
make postgres
make temporal
make worker
make api
make frontend
```

Open `http://localhost:3000`. Temporal's local UI is at `http://localhost:8233`.

Local defaults use `PLANNER_MODE=mock` and `EMAIL_MODE=preview`, so no secrets are required.
After finalizing an itinerary, the plan page links to the locally rendered email preview. Copy
`.env.example` to `.env` only when you need to override a setting; copy
`frontend/.env.example` to `frontend/.env.local` to enable the local preview link.

## Real integrations

The Pydantic AI planner is configured as `gpt-5.6-terra` with medium reasoning and
`TemporalDurability`. To exercise it, set `PLANNER_MODE=openai` and `OPENAI_API_KEY`. It is still
fed only fixture/context evidence until live travel adapters are activated.

To send a real transactional email, set `EMAIL_MODE=resend`, `RESEND_API_KEY`, and a verified
`RESEND_FROM_EMAIL`. Preview mode persists the same idempotency record without contacting Resend.

Provider and browser acquisition remain disabled until an exact, reviewed source policy enables
them. The UI and email therefore say when data is illustrative or a generic search link.

Logfire export is off by default. Set `LOGFIRE_ENABLED=true` and `LOGFIRE_TOKEN` to enable
scrubbed FastAPI and Pydantic AI telemetry; model content, request headers, and email values are
not captured. Run the deterministic Pydantic Evals baseline with `make evals`.

## Checks

```bash
make check
```

This runs the Python lock check, Ruff, strict mypy, pytest, strict TypeScript, ESLint, Vitest,
the Next static build, and export-artifact assertions.

## Production status

Production deployment is intentionally deferred. Terraform defines the target GCP topology and
secret containers, but secret values, DNS, provider rights, Temporal Cloud credentials, WCI
registration, and a reviewed plan/apply are explicit later steps.
