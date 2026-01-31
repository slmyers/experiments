variable "autovacuum_mode" {
  description = "Autovacuum configuration mode: disabled, aggressive, or default"
  type        = string
  default     = "disabled"

  validation {
    condition     = contains(["disabled", "aggressive", "default"], var.autovacuum_mode)
    error_message = "autovacuum_mode must be one of: disabled, aggressive, default"
  }
}

variable "postgres_port" {
  description = "External port to expose PostgreSQL"
  type        = number
  default     = 5432
}

variable "postgres_user" {
  description = "PostgreSQL username"
  type        = string
  default     = "experiment"
}

variable "postgres_password" {
  description = "PostgreSQL password"
  type        = string
  default     = "experiment_pass"
  sensitive   = true
}

variable "postgres_db" {
  description = "PostgreSQL database name"
  type        = string
  default     = "mvcc_experiment"
}

variable "shared_buffers" {
  description = "PostgreSQL shared_buffers setting"
  type        = string
  default     = "256MB"
}

variable "work_mem" {
  description = "PostgreSQL work_mem setting"
  type        = string
  default     = "64MB"
}

variable "maintenance_work_mem" {
  description = "PostgreSQL maintenance_work_mem setting"
  type        = string
  default     = "128MB"
}
