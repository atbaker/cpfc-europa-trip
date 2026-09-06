terraform {
  required_version = ">= 1.8.0"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 7.40"
    }
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

variable "project_id" {
  description = "GCP project that will own Terraform state."
  type        = string
}

variable "region" {
  description = "Default GCP region."
  type        = string
  default     = "europe-west2"
}

variable "state_bucket_name" {
  description = "Globally unique GCS bucket name for Terraform state."
  type        = string
}

resource "google_storage_bucket" "terraform_state" {
  name                        = var.state_bucket_name
  project                     = var.project_id
  location                    = var.region
  storage_class               = "STANDARD"
  force_destroy               = false
  public_access_prevention    = "enforced"
  uniform_bucket_level_access = true

  versioning {
    enabled = true
  }
}

output "state_bucket_name" {
  description = "Bucket to put in envs/prod/backend.hcl."
  value       = google_storage_bucket.terraform_state.name
}
