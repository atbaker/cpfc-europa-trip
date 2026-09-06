resource "google_service_account" "runtime" {
  for_each = toset(["api", "worker", "frontend-publisher"])

  project      = var.project_id
  account_id   = substr("${local.prefix}-${each.value}", 0, 30)
  display_name = "CPFC Away Days ${each.value}"

  depends_on = [google_project_service.required]
}

resource "google_project_iam_member" "cloud_sql_client" {
  for_each = toset(["api", "worker"])

  project = var.project_id
  role    = "roles/cloudsql.client"
  member  = "serviceAccount:${google_service_account.runtime[each.value].email}"
}

resource "google_storage_bucket_iam_member" "frontend_publisher" {
  bucket = google_storage_bucket.frontend.name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${google_service_account.runtime["frontend-publisher"].email}"
}

resource "google_service_account" "temporal_wci_invoker" {
  count = var.enable_temporal_serverless_workers ? 1 : 0

  project      = var.project_id
  account_id   = substr("${local.prefix}-wci-invoker", 0, 30)
  display_name = "Temporal WCI Worker Pool invoker"
}

resource "google_project_iam_custom_role" "temporal_worker_pool_scaler" {
  count = var.enable_temporal_serverless_workers ? 1 : 0

  project     = var.project_id
  role_id     = "cpfc_away_days_worker_scaler"
  title       = "CPFC Away Days Worker Pool scaler"
  description = "Allow Temporal WCI to read and scale only the release-managed Worker Pool."
  stage       = "GA"
  permissions = [
    "run.workerpools.get",
    "run.workerpools.update",
  ]
}

resource "google_project_iam_member" "temporal_worker_pool_scaler" {
  count = var.enable_temporal_serverless_workers ? 1 : 0

  project = var.project_id
  role    = google_project_iam_custom_role.temporal_worker_pool_scaler[0].name
  member  = "serviceAccount:${google_service_account.temporal_wci_invoker[0].email}"
}

resource "google_service_account_iam_member" "temporal_wci_impersonator" {
  for_each = var.enable_temporal_serverless_workers ? var.temporal_serverless_impersonator_service_account_emails : toset([])

  service_account_id = google_service_account.temporal_wci_invoker[0].name
  role               = "roles/iam.serviceAccountTokenCreator"
  member             = "serviceAccount:${each.value}"
}

resource "google_service_account_iam_member" "temporal_wci_worker_identity_user" {
  count = var.enable_temporal_serverless_workers ? 1 : 0

  service_account_id = google_service_account.runtime["worker"].name
  role               = "roles/iam.serviceAccountUser"
  member             = "serviceAccount:${google_service_account.temporal_wci_invoker[0].email}"
}
