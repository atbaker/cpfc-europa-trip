variable "project_id" {
  description = "GCP project ID."
  type        = string
}

variable "region" {
  description = "Primary GCP region. London keeps the API near the launch audience."
  type        = string
  default     = "europe-west2"
}

variable "domain" {
  description = "Public application hostname, without scheme."
  type        = string

  validation {
    condition     = length(trimspace(var.domain)) > 3 && !startswith(var.domain, "http")
    error_message = "domain must be a hostname without a scheme."
  }
}

variable "api_image" {
  description = "Immutable API image reference, preferably pinned by digest."
  type        = string

  validation {
    condition     = strcontains(var.api_image, "@sha256:")
    error_message = "api_image must be immutable and pinned with @sha256:."
  }
}

variable "worker_image" {
  description = "Immutable Worker image reference, preferably pinned by digest."
  type        = string

  validation {
    condition     = strcontains(var.worker_image, "@sha256:")
    error_message = "worker_image must be immutable and pinned with @sha256:."
  }
}

variable "temporal_address" {
  description = "Temporal Cloud namespace gRPC endpoint."
  type        = string
}

variable "temporal_namespace" {
  description = "Temporal Cloud namespace in namespace.account format."
  type        = string
}

variable "temporal_task_queue" {
  description = "Task Queue polled by the trip-planning Worker."
  type        = string
  default     = "cpfc-trip-planner"
}

variable "resend_from_email" {
  description = "Verified Resend sender."
  type        = string
}

variable "enable_temporal_serverless_workers" {
  description = "Create the prerelease Cloud Run Worker Pool and its WCI IAM boundary."
  type        = bool
  default     = false
}

variable "temporal_serverless_impersonator_service_account_emails" {
  description = "Exact Temporal-provided WCI impersonator identities; required when the Worker Pool is enabled."
  type        = set(string)
  default     = []

  validation {
    condition = (
      !var.enable_temporal_serverless_workers ||
      length(var.temporal_serverless_impersonator_service_account_emails) > 0
    )
    error_message = "At least one reviewed Temporal WCI impersonator identity is required when serverless Workers are enabled."
  }
}

variable "deletion_protection" {
  description = "Protect stateful and runtime resources from accidental deletion."
  type        = bool
  default     = true
}

variable "cloud_sql_tier" {
  description = "Cloud SQL machine tier."
  type        = string
  default     = "db-custom-1-3840"
}

variable "api_max_instances" {
  description = "Cloud Run API maximum instance count."
  type        = number
  default     = 5

  validation {
    condition     = var.api_max_instances >= 1 && var.api_max_instances <= 20
    error_message = "api_max_instances must be between 1 and 20."
  }
}
