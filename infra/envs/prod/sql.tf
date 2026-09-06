resource "google_sql_database_instance" "app" {
  name                = "${local.prefix}-postgres"
  project             = var.project_id
  region              = var.region
  database_version    = "POSTGRES_17"
  deletion_protection = var.deletion_protection

  settings {
    edition                     = "ENTERPRISE"
    tier                        = var.cloud_sql_tier
    availability_type           = "ZONAL"
    disk_type                   = "PD_SSD"
    disk_size                   = 20
    disk_autoresize             = true
    deletion_protection_enabled = var.deletion_protection

    ip_configuration {
      ipv4_enabled = true
    }

    backup_configuration {
      enabled                        = true
      start_time                     = "05:00"
      point_in_time_recovery_enabled = true
      transaction_log_retention_days = 7
    }

    maintenance_window {
      day          = 7
      hour         = 6
      update_track = "stable"
    }
  }

  depends_on = [google_project_service.required]
}

resource "google_sql_database" "app" {
  name      = "cpfc_trip"
  project   = var.project_id
  instance  = google_sql_database_instance.app.name
  charset   = "UTF8"
  collation = "en_US.UTF8"
}
