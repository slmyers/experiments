output "postgres_connection_string" {
  description = "PostgreSQL connection string"
  value       = "postgresql://${var.postgres_user}:${var.postgres_password}@localhost:${var.postgres_port}/${var.postgres_db}"
  sensitive   = true
}

output "postgres_host" {
  description = "PostgreSQL host"
  value       = "localhost"
}

output "postgres_port" {
  description = "PostgreSQL port"
  value       = var.postgres_port
}

output "postgres_user" {
  description = "PostgreSQL user"
  value       = var.postgres_user
}

output "postgres_db" {
  description = "PostgreSQL database"
  value       = var.postgres_db
}

output "autovacuum_mode" {
  description = "Current autovacuum configuration mode"
  value       = var.autovacuum_mode
}

output "container_id" {
  description = "PostgreSQL container ID"
  value       = docker_container.postgres.id
}
