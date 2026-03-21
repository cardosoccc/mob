resource "google_compute_network" "main" {
  name                    = "${local.prefix}-vpc"
  auto_create_subnetworks = false
  project                 = var.gcp_project_id

  depends_on = [google_project_service.apis]
}

resource "google_compute_subnetwork" "nodes" {
  name          = "${local.prefix}-nodes"
  ip_cidr_range = "10.0.0.0/20"
  region        = var.region
  network       = google_compute_network.main.id

  secondary_ip_range {
    range_name    = "${local.prefix}-pods"
    ip_cidr_range = "10.4.0.0/14"
  }

  secondary_ip_range {
    range_name    = "${local.prefix}-services"
    ip_cidr_range = "10.8.0.0/20"
  }

  private_ip_google_access = true
}

resource "google_compute_router" "main" {
  name    = "${local.prefix}-router"
  region  = var.region
  network = google_compute_network.main.id
}

resource "google_compute_router_nat" "main" {
  name                               = "${local.prefix}-nat"
  router                             = google_compute_router.main.name
  region                             = var.region
  nat_ip_allocate_option             = "AUTO_ONLY"
  source_subnetwork_ip_ranges_to_nat = "ALL_SUBNETWORKS_ALL_IP_RANGES"
}

resource "google_compute_global_address" "private_ip" {
  name          = "${local.prefix}-private-ip"
  purpose       = "VPC_PEERING"
  address_type  = "INTERNAL"
  prefix_length = 16
  network       = google_compute_network.main.id
}

resource "google_service_networking_connection" "private_vpc" {
  network                 = google_compute_network.main.id
  service                 = "servicenetworking.googleapis.com"
  reserved_peering_ranges = [google_compute_global_address.private_ip.name]

  depends_on = [google_project_service.apis]
}
