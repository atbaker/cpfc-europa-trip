# Infrastructure

Terraform defines, but does not automatically apply, the production GCP topology.

1. Apply `bootstrap/` once with local state to create the versioned remote-state bucket.
2. Copy `envs/prod/backend.hcl.example` to `backend.hcl` and fill in the bucket name.
3. Copy `envs/prod/terraform.tfvars.example` to `terraform.tfvars` and review every value.
4. Run `terraform init -backend-config=backend.hcl`, `terraform plan`, and obtain a human review before any apply.

The production stack intentionally creates Secret Manager *containers*, not secret versions. A release operator must add
the six values listed in `envs/prod/secrets.tf` before the API or Worker can start. DNS records, database credentials,
Temporal Cloud namespace setup, and Temporal Worker Controller Identity (WCI) approval are also deliberate operator
steps.

`enable_temporal_serverless_workers` defaults to `false`. Enable it only after Temporal has enabled the prerelease for
the namespace and supplied the impersonator service-account identity. Terraform then creates the Cloud Run Worker Pool
and least-privilege WCI IAM boundary; Temporal owns its release-time capacity and image changes.
