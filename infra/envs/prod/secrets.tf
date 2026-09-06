# Secret versions are intentionally absent. Add values only through an approved
# release/secret-management path so plaintext never enters Terraform state.
resource "google_secret_manager_secret" "app" {
  for_each = local.secret_roles

  project   = var.project_id
  secret_id = "${local.prefix}-${each.key}"

  replication {
    auto {}
  }

  depends_on = [google_project_service.required]
}

resource "google_secret_manager_secret_iam_member" "accessor" {
  for_each = local.secret_access_bindings

  project   = var.project_id
  secret_id = google_secret_manager_secret.app[each.value.secret_name].secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.runtime[each.value.role].email}"
}
