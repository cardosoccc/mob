resource "google_container_cluster" "main" {
  name     = "${local.prefix}-cluster"
  location = var.region

  network    = google_compute_network.main.id
  subnetwork = google_compute_subnetwork.nodes.id

  # Use a separately managed node pool
  remove_default_node_pool = true
  initial_node_count       = 1

  ip_allocation_policy {
    cluster_secondary_range_name  = "${local.prefix}-pods"
    services_secondary_range_name = "${local.prefix}-services"
  }

  private_cluster_config {
    enable_private_nodes    = true
    enable_private_endpoint = false
    master_ipv4_cidr_block  = "172.16.0.0/28"
  }

  workload_identity_config {
    workload_pool = "${var.gcp_project_id}.svc.id.goog"
  }

  release_channel {
    channel = "REGULAR"
  }

  depends_on = [google_project_service.apis]
}

resource "google_container_node_pool" "main" {
  name       = "${local.prefix}-node-pool"
  location   = var.region
  cluster    = google_container_cluster.main.name
  node_count = var.gke_node_count

  autoscaling {
    min_node_count = var.gke_min_node_count
    max_node_count = var.gke_max_node_count
  }

  node_config {
    machine_type = var.gke_machine_type
    disk_size_gb = 50

    oauth_scopes = [
      "https://www.googleapis.com/auth/cloud-platform",
    ]

    workload_metadata_config {
      mode = "GKE_METADATA"
    }

    labels = {
      project     = var.project
      environment = var.environment
    }
  }

  management {
    auto_repair  = true
    auto_upgrade = true
  }
}

resource "google_artifact_registry_repository" "main" {
  location      = var.region
  repository_id = "${local.prefix}-docker"
  format        = "DOCKER"

  depends_on = [google_project_service.apis]
}
