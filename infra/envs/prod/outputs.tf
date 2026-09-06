output "frontend_bucket" {
  description = "Upload frontend/out contents here with immutable cache metadata for hashed assets."
  value       = google_storage_bucket.frontend.name
}

output "frontend_publisher_service_account" {
  description = "Identity used by the release pipeline to publish the static export."
  value       = google_service_account.runtime["frontend-publisher"].email
}

output "edge_ip_address" {
  description = "Create the application's A record at this address."
  value       = google_compute_global_address.edge.address
}

output "certificate_dns_authorization" {
  description = "Create this DNS record before the managed certificate can become active."
  value       = google_certificate_manager_dns_authorization.app.dns_resource_record
}

output "artifact_registry_repository" {
  value = google_artifact_registry_repository.containers.id
}

output "secret_ids_requiring_versions" {
  description = "Secret containers that a release operator must populate outside Terraform."
  value       = { for name, secret in google_secret_manager_secret.app : name => secret.id }
}

output "worker_pool_name" {
  description = "Cloud Run Worker Pool registered with Temporal WCI, when enabled."
  value       = try(google_cloud_run_v2_worker_pool.worker[0].name, null)
}
