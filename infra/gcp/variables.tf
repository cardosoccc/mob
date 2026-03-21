variable "project" {
  description = "Project name"
  type        = string
  default     = "mob"
}

variable "environment" {
  description = "Deployment environment (dev, staging, production)"
  type        = string
}

variable "gcp_project_id" {
  description = "GCP project ID"
  type        = string
}

variable "region" {
  description = "GCP region"
  type        = string
  default     = "us-central1"
}

variable "db_tier" {
  description = "Cloud SQL instance tier"
  type        = string
  default     = "db-custom-2-4096"
}

variable "db_name" {
  description = "Database name"
  type        = string
  default     = "mob"
}

variable "db_username" {
  description = "Database username"
  type        = string
  default     = "mob_admin"
}

variable "db_high_availability" {
  description = "Enable high availability for Cloud SQL"
  type        = bool
  default     = false
}

variable "db_backup_enabled" {
  description = "Enable automated backups for Cloud SQL"
  type        = bool
  default     = true
}

variable "db_deletion_protection" {
  description = "Enable deletion protection for Cloud SQL"
  type        = bool
  default     = true
}

variable "gke_machine_type" {
  description = "GKE node machine type"
  type        = string
  default     = "e2-medium"
}

variable "gke_node_count" {
  description = "Number of GKE nodes per zone"
  type        = number
  default     = 1
}

variable "gke_min_node_count" {
  description = "Minimum number of GKE nodes per zone"
  type        = number
  default     = 1
}

variable "gke_max_node_count" {
  description = "Maximum number of GKE nodes per zone"
  type        = number
  default     = 3
}

variable "api_replicas" {
  description = "Number of API replicas"
  type        = number
  default     = 2
}
