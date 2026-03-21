output "network_name" {
  description = "VPC network name"
  value       = google_compute_network.main.name
}

output "gke_cluster_name" {
  description = "GKE cluster name"
  value       = google_container_cluster.main.name
}

output "gke_cluster_endpoint" {
  description = "GKE cluster API endpoint"
  value       = google_container_cluster.main.endpoint
  sensitive   = true
}

output "cloudsql_instance_name" {
  description = "Cloud SQL instance name"
  value       = google_sql_database_instance.main.name
}

output "cloudsql_connection_name" {
  description = "Cloud SQL instance connection name"
  value       = google_sql_database_instance.main.connection_name
}

output "cloudsql_private_ip" {
  description = "Cloud SQL private IP address"
  value       = google_sql_database_instance.main.private_ip_address
}

output "database_url" {
  description = "Full database connection URL (without password)"
  value       = "postgresql+asyncpg://${var.db_username}@${google_sql_database_instance.main.private_ip_address}/${var.db_name}"
  sensitive   = true
}

output "db_password_secret_id" {
  description = "Secret Manager secret ID for the DB password"
  value       = google_secret_manager_secret.db_password.secret_id
}

output "artifact_registry_url" {
  description = "Artifact Registry repository URL"
  value       = "${var.region}-docker.pkg.dev/${var.gcp_project_id}/${google_artifact_registry_repository.main.repository_id}"
}
