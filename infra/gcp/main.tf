provider "google" {
  project = var.gcp_project_id
  region  = var.region
}

locals {
  prefix = "${var.project}-${var.environment}"
}

resource "google_project_service" "apis" {
  for_each = toset([
    "container.googleapis.com",
    "sqladmin.googleapis.com",
    "servicenetworking.googleapis.com",
    "secretmanager.googleapis.com",
    "artifactregistry.googleapis.com",
  ])

  project = var.gcp_project_id
  service = each.value

  disable_on_destroy = false
}
