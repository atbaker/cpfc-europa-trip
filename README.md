# Eagles Away

Plan a Crystal Palace away day from a UK city. Eagles Away looks for travel and a place to stay around selected Europa League matches, then puts the options in one easy-to-read plan. Built with Temporal.

**[Plan an away day at eaglesaway.com](https://eaglesaway.com/)**

## What to expect

1. Choose your starting city, match, dates and travel preferences.
2. See the journeys and stays we could verify, with prices where available.
3. Check what is still missing, then open the provider links to confirm details before booking. You can email yourself a completed plan if you choose.

Eagles Away does not make bookings or sell match tickets. Prices and availability can change, and some costs, such as local transfers or match tickets, may be missing. If we cannot verify a complete trip, the page explains what was missing and does not send an email.

## Run it locally

You will need [Python 3.13](.python-version), [uv](https://docs.astral.sh/uv/), [Node.js 22](.node-version), [Docker](https://www.docker.com/) and the [Temporal CLI](https://docs.temporal.io/cli).

From the repository root, set up the project and start PostgreSQL:

```bash
scripts/dev/setup.sh
scripts/dev/postgres-up.sh
```

Then start these four processes in separate terminals:

```bash
scripts/dev/temporal-server.sh
scripts/dev/api.sh
scripts/dev/worker.sh
scripts/dev/frontend.sh
```

Open [localhost:3000](http://localhost:3000). A fresh checkout uses recorded sample trips and preview emails, so you can explore the app without paid travel searches or sending mail. Email previews are saved in `.data/email-previews/`.

To check a change, stop the frontend development server and run `scripts/check.sh`. For the PostgreSQL checks too, use `TEST_DATABASE_URL=postgresql+asyncpg://cpfc:cpfc@localhost:5432/cpfc scripts/check.sh` with the local test database running. Never point tests at a shared or production database.

## How it works

The website uses Next.js. A FastAPI service handles trip requests, Temporal runs the planning workflow, PostgreSQL stores session data, and SearchApi supplies dated travel and hotel results. Google Maps links open fresh local directions. The app shows where a price or route could not be confirmed.

For architecture, deployment and project history, see the [engineering handoff](planning/2026-09-30-engineering-handoff.md), [deployment record](planning/2026-10-06-deployment-readiness.md) and [development notes](blog.md).
