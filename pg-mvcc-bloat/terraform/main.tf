terraform {
  required_version = ">= 1.0.0"

  required_providers {
    docker = {
      source  = "kreuzwerker/docker"
      version = "~> 3.0"
    }
  }
}

provider "docker" {}

# Network for PostgreSQL
resource "docker_network" "pg_network" {
  name = "pg-mvcc-experiment"
}

# PostgreSQL configuration file from template
resource "local_file" "postgres_conf" {
  content = templatefile("${path.module}/postgres.conf.tpl", {
    autovacuum_enabled           = var.autovacuum_mode != "disabled"
    autovacuum_vacuum_scale_factor = var.autovacuum_mode == "aggressive" ? 0.01 : (var.autovacuum_mode == "default" ? 0.2 : 0.2)
    autovacuum_analyze_scale_factor = var.autovacuum_mode == "aggressive" ? 0.005 : (var.autovacuum_mode == "default" ? 0.1 : 0.1)
    autovacuum_vacuum_threshold  = var.autovacuum_mode == "aggressive" ? 25 : 50
    autovacuum_naptime           = var.autovacuum_mode == "aggressive" ? "5s" : "60s"
    shared_buffers               = var.shared_buffers
    work_mem                     = var.work_mem
    maintenance_work_mem         = var.maintenance_work_mem
  })
  filename = "${path.module}/generated/postgresql.conf"
}

# PostgreSQL data volume
resource "docker_volume" "pg_data" {
  name = "pg-mvcc-data"
}

# PostgreSQL container
resource "docker_container" "postgres" {
  name  = "pg-mvcc-postgres"
  image = docker_image.postgres.image_id

  networks_advanced {
    name = docker_network.pg_network.name
  }

  ports {
    internal = 5432
    external = var.postgres_port
  }

  env = [
    "POSTGRES_USER=${var.postgres_user}",
    "POSTGRES_PASSWORD=${var.postgres_password}",
    "POSTGRES_DB=${var.postgres_db}"
  ]

  volumes {
    volume_name    = docker_volume.pg_data.name
    container_path = "/var/lib/postgresql/data"
  }

  upload {
    content = local_file.postgres_conf.content
    file    = "/etc/postgresql/postgresql.conf"
  }

  command = [
    "postgres",
    "-c", "config_file=/etc/postgresql/postgresql.conf"
  ]

  healthcheck {
    test     = ["CMD-SHELL", "pg_isready -U ${var.postgres_user} -d ${var.postgres_db}"]
    interval = "5s"
    timeout  = "5s"
    retries  = 5
  }

  restart = "unless-stopped"

  depends_on = [local_file.postgres_conf]
}

# PostgreSQL image
resource "docker_image" "postgres" {
  name         = "postgres:16"
  keep_locally = true
}

# Wait for PostgreSQL to be ready and create extensions
resource "null_resource" "setup_extensions" {
  depends_on = [docker_container.postgres]

  provisioner "local-exec" {
    command = <<-EOT
      echo "Waiting for PostgreSQL to be ready..."
      sleep 10
      
      PGPASSWORD=${var.postgres_password} psql -h localhost -p ${var.postgres_port} -U ${var.postgres_user} -d ${var.postgres_db} <<EOF
        CREATE EXTENSION IF NOT EXISTS pgstattuple;
        CREATE EXTENSION IF NOT EXISTS pg_stat_statements;
      EOF
      
      echo "Extensions created successfully"
    EOT
  }

  triggers = {
    container_id = docker_container.postgres.id
  }
}
