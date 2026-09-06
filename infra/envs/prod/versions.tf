terraform {
  required_version = ">= 1.8.0"

  backend "gcs" {}

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

  default_labels = local.labels
}

data "google_project" "current" {
  project_id = var.project_id
}
