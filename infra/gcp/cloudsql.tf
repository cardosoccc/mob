resource "google_sql_database_instance" "main" {
  name             = "${local.prefix}-postgres"
  database_version = "POSTGRES_16"
  region           = var.region

  deletion_protection = var.db_deletion_protection

  settings {
    tier              = var.db_tier
    availability_type = var.db_high_availability ? "REGIONAL" : "ZONAL"

    ip_configuration {
      ipv4_enabled                                  = false
      private_network                               = google_compute_network.main.id
      enable_private_path_for_google_cloud_services = true
    }

    backup_configuration {
      enabled                        = var.db_backup_enabled
      point_in_time_recovery_enabled = var.db_backup_enabled
      start_time                     = "03:00"
    }

    disk_size       = 20
    disk_autoresize = true
    disk_type       = "PD_SSD"

    database_flags {
      name  = "max_connections"
      value = "100"
    }

    user_labels = {
      project     = var.project
      environment = var.environment
    }
  }

  depends_on = [google_service_networking_connection.private_vpc]
}

resource "google_sql_database" "main" {
  name     = var.db_name
  instance = google_sql_database_instance.main.name
}

resource "random_password" "db" {
  length  = 32
  special = false
}

resource "google_sql_user" "main" {
  name     = var.db_username
  instance = google_sql_database_instance.main.name
  password = random_password.db.result
}

resource "google_secret_manager_secret" "db_password" {
  secret_id = "${local.prefix}-db-password"

  replication {
    auto {}
  }

  depends_on = [google_project_service.apis]
}

resource "google_secret_manager_secret_version" "db_password" {
  secret      = google_secret_manager_secret.db_password.id
  secret_data = random_password.db.result
}
