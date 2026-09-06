resource "google_cloud_run_v2_service" "api" {
  name                = "${local.prefix}-api"
  project             = var.project_id
  location            = var.region
  ingress             = "INGRESS_TRAFFIC_INTERNAL_LOAD_BALANCER"
  deletion_protection = var.deletion_protection

  template {
    service_account                  = google_service_account.runtime["api"].email
    timeout                          = "3600s"
    max_instance_request_concurrency = 40

    scaling {
      min_instance_count = 1
      max_instance_count = var.api_max_instances
    }

    volumes {
      name = "cloudsql"
      cloud_sql_instance {
        instances = [google_sql_database_instance.app.connection_name]
      }
    }

    containers {
      name  = "api"
      image = var.api_image

      ports {
        name           = "http1"
        container_port = 8080
      }

      resources {
        limits = {
          cpu    = "1"
          memory = "512Mi"
        }
        cpu_idle          = true
        startup_cpu_boost = true
      }

      volume_mounts {
        name       = "cloudsql"
        mount_path = "/cloudsql"
      }

      dynamic "env" {
        for_each = local.api_runtime_env
        content {
          name  = env.key
          value = env.value
        }
      }

      dynamic "env" {
        for_each = local.api_secret_env
        content {
          name = env.key
          value_source {
            secret_key_ref {
              secret  = google_secret_manager_secret.app[env.value].secret_id
              version = "latest"
            }
          }
        }
      }

      startup_probe {
        timeout_seconds   = 2
        period_seconds    = 3
        failure_threshold = 20
        http_get {
          path = "/healthz"
          port = 8080
        }
      }

      liveness_probe {
        initial_delay_seconds = 5
        timeout_seconds       = 2
        period_seconds        = 30
        failure_threshold     = 3
        http_get {
          path = "/healthz"
          port = 8080
        }
      }
    }
  }

  lifecycle {
    ignore_changes = [client, client_version]
  }

  depends_on = [
    google_project_iam_member.cloud_sql_client,
    google_secret_manager_secret_iam_member.accessor,
  ]
}

resource "google_cloud_run_v2_service_iam_member" "api_public_invoker" {
  project  = var.project_id
  location = google_cloud_run_v2_service.api.location
  name     = google_cloud_run_v2_service.api.name
  role     = "roles/run.invoker"
  member   = "allUsers"
}

resource "google_cloud_run_v2_worker_pool" "worker" {
  count = var.enable_temporal_serverless_workers ? 1 : 0

  name                = "${local.prefix}-worker"
  project             = var.project_id
  location            = var.region
  description         = "Temporal trip-planning Worker Pool"
  deletion_protection = var.deletion_protection

  scaling {
    scaling_mode          = "MANUAL"
    manual_instance_count = 1
  }

  template {
    service_account = google_service_account.runtime["worker"].email

    volumes {
      name = "cloudsql"
      cloud_sql_instance {
        instances = [google_sql_database_instance.app.connection_name]
      }
    }

    containers {
      name    = "worker"
      image   = var.worker_image
      command = ["cpfc-worker"]

      resources {
        limits = {
          cpu    = "1"
          memory = "1Gi"
        }
      }

      volume_mounts {
        name       = "cloudsql"
        mount_path = "/cloudsql"
      }

      dynamic "env" {
        for_each = local.worker_runtime_env
        content {
          name  = env.key
          value = env.value
        }
      }

      dynamic "env" {
        for_each = local.worker_secret_env
        content {
          name = env.key
          value_source {
            secret_key_ref {
              secret  = google_secret_manager_secret.app[env.value].secret_id
              version = "latest"
            }
          }
        }
      }
    }
  }

  lifecycle {
    ignore_changes = [
      client,
      client_version,
      scaling[0].manual_instance_count,
      template[0].containers[0].image,
    ]
  }

  depends_on = [
    google_project_iam_member.cloud_sql_client,
    google_secret_manager_secret_iam_member.accessor,
    google_service_account_iam_member.temporal_wci_worker_identity_user,
  ]
}
