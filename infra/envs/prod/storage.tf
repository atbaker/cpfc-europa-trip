resource "google_storage_bucket" "frontend" {
  name                        = "${var.project_id}-${local.prefix}-frontend"
  project                     = var.project_id
  location                    = var.region
  storage_class               = "STANDARD"
  force_destroy               = false
  public_access_prevention    = "inherited"
  uniform_bucket_level_access = true

  website {
    main_page_suffix = "index.html"
    not_found_page   = "404.html"
  }

  versioning {
    enabled = true
  }

  depends_on = [google_project_service.required]
}

resource "google_storage_bucket_iam_member" "frontend_public" {
  bucket = google_storage_bucket.frontend.name
  role   = "roles/storage.objectViewer"
  member = "allUsers"
}
