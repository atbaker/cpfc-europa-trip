locals {
  prefix = "cpfc-away-days"
  labels = {
    application = "cpfc-away-days"
    environment = "production"
    managed-by  = "terraform"
  }

  required_services = toset([
    "artifactregistry.googleapis.com",
    "certificatemanager.googleapis.com",
    "compute.googleapis.com",
    "iam.googleapis.com",
    "iamcredentials.googleapis.com",
    "run.googleapis.com",
    "secretmanager.googleapis.com",
    "sqladmin.googleapis.com",
    "storage.googleapis.com",
  ])

  secret_roles = {
    session-secret         = ["api"]
    database-url           = ["api", "worker"]
    database-migration-url = []
    temporal-api-key       = ["api", "worker"]
    openai-api-key         = ["worker"]
    resend-api-key         = ["worker"]
    logfire-token          = ["api", "worker"]
  }

  secret_access_bindings = {
    for binding in flatten([
      for secret_name, roles in local.secret_roles : [
        for role in roles : {
          key         = "${secret_name}:${role}"
          secret_name = secret_name
          role        = role
        }
      ]
    ]) : binding.key => binding
  }

  common_runtime_env = {
    APP_ENV                    = "production"
    API_BASE_URL               = "https://${var.domain}"
    FRONTEND_ORIGIN            = "https://${var.domain}"
    TEMPORAL_ADDRESS           = var.temporal_address
    TEMPORAL_NAMESPACE         = var.temporal_namespace
    TEMPORAL_TASK_QUEUE        = var.temporal_task_queue
    TEMPORAL_TLS               = "true"
    INACTIVITY_TIMEOUT_SECONDS = "600"
  }

  api_runtime_env = merge(local.common_runtime_env, {
    PLANNER_MODE    = "openai"
    EMAIL_MODE      = "resend"
    LOGFIRE_ENABLED = "true"
  })

  worker_runtime_env = merge(local.common_runtime_env, {
    PLANNER_MODE      = "openai"
    EMAIL_MODE        = "resend"
    RESEND_FROM_EMAIL = var.resend_from_email
    LOGFIRE_ENABLED   = "true"
  })

  api_secret_env = {
    SESSION_SECRET   = "session-secret"
    DATABASE_URL     = "database-url"
    TEMPORAL_API_KEY = "temporal-api-key"
    LOGFIRE_TOKEN    = "logfire-token"
  }

  worker_secret_env = {
    DATABASE_URL     = "database-url"
    TEMPORAL_API_KEY = "temporal-api-key"
    OPENAI_API_KEY   = "openai-api-key"
    RESEND_API_KEY   = "resend-api-key"
    LOGFIRE_TOKEN    = "logfire-token"
  }
}
