# Eagles Away deployment readiness — 6 October 2026

This is a dated discovery record for the first cloud deployment. It supplements the [approved MVP architecture](mvp-plan.md#infrastructure-and-deployment) and the [engineering handoff](2026-09-30-engineering-handoff.md). No production resources or DNS records were changed during this review.

## 7 October 2026 — DigitalOcean target replaces the GCP preview

The owner chose DigitalOcean App Platform after the GCP billing block. The `doctl` profile
initially returned HTTP 401; after reauthentication a dedicated project and Frankfurt
PostgreSQL 17 cluster were created. The preview image builds locally, and a container import verified the
static export and API package. `scripts/check.sh` passed after adding a required HTTP Basic
access gate for `APP_ENV=preview` and DigitalOcean PostgreSQL URL/TLS handling. The initial
DB password appeared in CLI creation output and was rotated before deployment. The worker
supports `GOOGLE_AUTH_MODE=api_key`; the provided Gemini key was verified. Keep `EMAIL_MODE=preview` and
`eaglesaway.com` DNS unchanged for this stage. The GCP sequence below records the previous
target and is superseded for the private preview.

## 7 October 2026 — DigitalOcean private preview deployed

The Frankfurt PostgreSQL 17 cluster `eagles-away-preview-pg` is online in the dedicated
`Eagles Away Preview` project. An App Platform deployment is active at
<https://eagles-away-preview-ifemt.ondigitalocean.app/> with a web service, Temporal worker,
and successful predeploy migration job. The app uses a separate preview task queue,
runtime-only encrypted secrets, `APP_ENV=preview`, and `EMAIL_MODE=preview`. No DNS record
for `eaglesaway.com` was changed.

The deployed `/healthz` returned 200, `/` returned 401 without preview credentials, and
authenticated `/`, `/plan/`, and `/api/catalog` returned 200. A hosted London–Lyon live session
reached `draft_ready` with a journey, stay, partial priced total, and explicit outstanding
checks. This is one functional smoke test, not a full route or browser acceptance audit.

A sanitized app spec passed DigitalOcean's account-backed validation. Automatic approval
review rejected an additional validation of the secret-bearing spec because it would have
uploaded API keys unnecessarily. The actual deployment submitted runtime secrets to
DigitalOcean as required. The ignored local spec and preview password are restricted to the
owner's workspace and are not committed.

## 7 October 2026 — live email candidate awaiting review

The existing Resend delivery Activity accepted a local live email using a frozen London–Lyon
plan, and the owner confirmed receipt. A redesigned email matching the website's plan-card
hierarchy was accepted as a separate idempotent test; the owner has not yet confirmed the
revised appearance. A sanitized App Platform candidate with `EMAIL_MODE=resend` and a
runtime-only Resend key and sender passed account-backed validation. The deployed app remains
on `EMAIL_MODE=preview` until the owner approves the email change. Signed delivery-status
webhooks remain unconfigured, so provider acceptance is not a delivery confirmation.

## Verified state

| Area | Evidence on 6 October | Consequence |
| --- | --- | --- |
| Domain | `eaglesaway.com` uses Cloudflare nameservers (`david` and `gina`). The apex A lookup returned `NOERROR` with no answer; `www.eaglesaway.com` returned `NXDOMAIN`. | The public site does not currently resolve to a GCP load balancer. Cloudflare DNS access is needed for cutover. |
| GCP access | The owner refreshed the `eagles-away-work` login and requested Opal access. This account now has `roles/owner` on `cpfc-europa-trip-prod`; billing is still disabled and the Cloud SQL Admin API is disabled. Linking either the initially approved `Billing Account for temporal.io` or the subsequently requested `Navan GCP Card` failed because this account lacks `billing.resourceAssociations.create` on both billing accounts. `andrew-baker-sandbox` has billing enabled but was explicitly declined as a hosting target. | The chosen dedicated project cannot host the preview until an authorized billing administrator links an approved account or grants the required billing-account permission. |
| Infrastructure | This repository has no Terraform roots or CI deployment workflow. A preview image definition builds the static export and API together; `terraform` is not installed locally. An attempt to enable preview APIs failed with `FAILED_PRECONDITION` because billing is disabled. | The approved public production topology has not been provisioned. The preview uses a single protected Cloud Run origin to test the app without a load balancer or DNS cutover. |
| Temporal | The owner confirmed namespace `gcp-shy-projects.a2dd6` at `gcp-shy-projects.a2dd6.tmprl.cloud:7233`. The locally configured API key successfully completed a Cloud health check on 6 October without disclosing the key. The installed CLI has no `temporal cloud` extension. | The preview needs that API key stored in Secret Manager and a continuously running worker pool. |
| Database | Application runtime currently creates an ordinary SQLAlchemy engine from `DATABASE_URL`; Cloud SQL fields in `Settings` are unused. | The planned private-IP, automatic-IAM Cloud SQL connection and migration job are not implemented. |
| Email and privacy | Local mode is `EMAIL_MODE=preview`; a Resend API key is present but webhook secret is absent. `/privacy/` explicitly says the build is not open for public submissions and lacks retention, operator and deletion details. | Public submissions and live email require owner decisions, signed webhook setup and final privacy copy. |
| Traffic controls | Session creation/polling uses process-local limits. The handoff notes missing shared admission and cost controls. | Scaling the API without shared limits could multiply paid model/provider calls. |
| Local gate | After the preview static mount and secure-cookie change, `scripts/check.sh` passed: 78 Python tests, 18 frontend tests, Ruff, mypy, API schema, TypeScript, ESLint and static export. Two PostgreSQL tests skipped because Docker Desktop was stopped at that time. The image subsequently built, and `/`, `/plan/`, `/privacy/`, `/api/catalog` and `/healthz` each returned 200 in a container smoke test. | The container runs its static and unauthenticated routes, but database, Temporal and paid provider operations are untested in the image. |

## Deployment sequence

1. Link the owner's approved billing account to `cpfc-europa-trip-prod`, then enable Cloud Run, Cloud Build, Artifact Registry, Cloud SQL and Secret Manager APIs. Inspect existing resources before creation.
2. For the chosen private preview, publish the combined static export/API image and run it on one Cloud Run origin behind direct IAP. Provision Cloud SQL, migrate it, store secrets, and run the Temporal worker in a worker pool. Keep email in preview mode and do not change `eaglesaway.com` DNS.
3. For the later public topology: static Next export in Cloud Storage/CDN, same-origin FastAPI Cloud Run, Cloud SQL, Temporal Cloud plus versioned workers, Secret Manager, and HTTPS load balancer. Keep `eaglesaway.com` DNS unchanged until health, direct `/plan/` routing, credentials and rollback are verified on a test hostname or load-balancer IP.
4. Exercise a deployed trip through API, Temporal worker, database, provider search, browser reload and email mode appropriate to the release. Test worker replacement, a failed provider request, and a rollback before DNS cutover.
5. Update Cloudflare DNS only after the release is healthy and the domain owner approves the exact record change; verify certificate issuance and both apex and `www` behavior.

## Decisions still needed

- Billing-account permission or administrator action to link an owner-approved account to `cpfc-europa-trip-prod`; its billing is currently disabled. Attempts with both `Billing Account for temporal.io` and `Navan GCP Card` were denied. The owner chose this project for a private preview and declined the sandbox.
- Import the locally configured, health-checked Temporal Cloud API key directly into Secret Manager; the namespace and endpoint are confirmed.
- Cloudflare DNS access and intended `www` behavior.
- For public use: operator identity, retention/deletion contact, Resend webhook secret, commercial permission for search-result display and 24-hour cache, and shared admission/cost limits.
