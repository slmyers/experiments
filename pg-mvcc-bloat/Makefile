# PostgreSQL MVCC Bloat Experiment Makefile

.PHONY: help infra migrate seed experiment report visualize down clean list-presets

# Default values
AUTOVACUUM ?= disabled
PRESET ?= bloat-demo
DURATION ?= 
POLL_INTERVAL ?=
COUNT ?= 1000000
SEED ?= 42
RUN ?=

# Python command (use python3 on macOS)
PYTHON ?= python3

# Database connection
export PGHOST ?= localhost
export PGPORT ?= 5432
export PGUSER ?= experiment
export PGPASSWORD ?= experiment_pass
export PGDATABASE ?= mvcc_experiment

# Paths
TERRAFORM_DIR = terraform
MIGRATIONS_DIR = migrations
SCRIPTS_DIR = scripts

help: ## Show this help message
	@echo "PostgreSQL MVCC Bloat Experiment"
	@echo ""
	@echo "Usage: make [target] [VARIABLE=value]"
	@echo ""
	@echo "Targets:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'
	@echo ""
	@echo "Variables:"
	@echo "  AUTOVACUUM     Autovacuum mode: disabled, aggressive, default (default: disabled)"
	@echo "  PRESET         Experiment preset name (default: bloat-demo)"
	@echo "  DURATION       Override experiment duration in seconds"
	@echo "  POLL_INTERVAL  Override metrics poll interval in seconds"
	@echo "  COUNT          Number of rows to seed (default: 1000000)"
	@echo "  SEED           Random seed for data generation (default: 42)"
	@echo "  RUN            Run ID for report generation"

# Infrastructure targets

infra: ## Start PostgreSQL with Terraform (AUTOVACUUM=disabled|aggressive|default)
	@echo "Starting PostgreSQL with autovacuum=$(AUTOVACUUM)..."
	@mkdir -p $(TERRAFORM_DIR)/generated
	cd $(TERRAFORM_DIR) && terraform init
	cd $(TERRAFORM_DIR) && terraform apply -auto-approve -var="autovacuum_mode=$(AUTOVACUUM)"
	@echo "Waiting for PostgreSQL to be ready..."
	@sleep 5
	@until PGPASSWORD=$(PGPASSWORD) psql -h $(PGHOST) -p $(PGPORT) -U $(PGUSER) -d $(PGDATABASE) -c "SELECT 1" > /dev/null 2>&1; do \
		echo "Waiting for PostgreSQL..."; \
		sleep 2; \
	done
	@echo "PostgreSQL is ready!"

down: ## Stop PostgreSQL container
	cd $(TERRAFORM_DIR) && terraform destroy -auto-approve

# Database targets

migrate: ## Run database migrations
	@echo "Running migrations..."
	@for f in $(MIGRATIONS_DIR)/*.sql; do \
		echo "Running $$f..."; \
		PGPASSWORD=$(PGPASSWORD) psql -h $(PGHOST) -p $(PGPORT) -U $(PGUSER) -d $(PGDATABASE) -f "$$f"; \
	done
	@echo "Migrations complete!"

seed: ## Seed tables with test data (COUNT=1000000, SEED=42)
	@echo "Seeding tables with $(COUNT) rows (seed=$(SEED))..."
	cd $(SCRIPTS_DIR) && $(PYTHON) -m seed.seed_data --count $(COUNT) --seed $(SEED)

seed-quick: ## Quick seed with 100k rows for testing
	@echo "Quick seeding with 100,000 rows..."
	cd $(SCRIPTS_DIR) && $(PYTHON) -m seed.seed_data --count 100000 --seed $(SEED)

# Experiment targets

list-presets: ## List available experiment presets
	cd $(SCRIPTS_DIR) && $(PYTHON) -m experiments.run_experiment --list

experiment: ## Run an experiment (PRESET=name, DURATION=seconds, POLL_INTERVAL=seconds)
	@echo "Running experiment: $(PRESET)"
ifdef DURATION
ifdef POLL_INTERVAL
	cd $(SCRIPTS_DIR) && $(PYTHON) -m experiments.run_experiment $(PRESET) --duration $(DURATION) --poll-interval $(POLL_INTERVAL)
else
	cd $(SCRIPTS_DIR) && $(PYTHON) -m experiments.run_experiment $(PRESET) --duration $(DURATION)
endif
else
	cd $(SCRIPTS_DIR) && $(PYTHON) -m experiments.run_experiment $(PRESET)
endif

# Analysis targets

visualize: ## Generate plan visualizations (RUN=run_id)
ifndef RUN
	$(error RUN is required. Usage: make visualize RUN=<run_id>)
endif
	@echo "Generating plan visualizations for $(RUN)..."
	cd $(SCRIPTS_DIR) && $(PYTHON) -m visualize.plan_visualizer --run-id $(RUN)

report: ## Generate experiment report (RUN=run_id)
ifndef RUN
	$(error RUN is required. Usage: make report RUN=<run_id>)
endif
	@echo "Generating report for $(RUN)..."
	cd $(SCRIPTS_DIR) && $(PYTHON) -m visualize.plan_visualizer --run-id $(RUN) || true
	cd $(SCRIPTS_DIR) && $(PYTHON) -m report.generate_report $(RUN) --load-from-db

# Utility targets

snapshot: ## Take a manual metrics snapshot
	cd $(SCRIPTS_DIR) && $(PYTHON) -m metrics.snapshot --type baseline --run-id manual

vacuum: ## Run VACUUM on all experiment tables
	@echo "Running VACUUM..."
	PGPASSWORD=$(PGPASSWORD) psql -h $(PGHOST) -p $(PGPORT) -U $(PGUSER) -d $(PGDATABASE) -c "VACUUM VERBOSE documents_jsonb; VACUUM VERBOSE documents_jsonb_with_flags; VACUUM VERBOSE documents_normalized;"

vacuum-full: ## Run VACUUM FULL on all experiment tables
	@echo "Running VACUUM FULL (this will lock tables)..."
	PGPASSWORD=$(PGPASSWORD) psql -h $(PGHOST) -p $(PGPORT) -U $(PGUSER) -d $(PGDATABASE) -c "VACUUM FULL VERBOSE documents_jsonb; VACUUM FULL VERBOSE documents_jsonb_with_flags; VACUUM FULL VERBOSE documents_normalized;"

analyze: ## Run ANALYZE on all experiment tables
	@echo "Running ANALYZE..."
	PGPASSWORD=$(PGPASSWORD) psql -h $(PGHOST) -p $(PGPORT) -U $(PGUSER) -d $(PGDATABASE) -c "ANALYZE VERBOSE documents_jsonb; ANALYZE VERBOSE documents_jsonb_with_flags; ANALYZE VERBOSE documents_normalized;"

stats: ## Show current table statistics
	@PGPASSWORD=$(PGPASSWORD) psql -h $(PGHOST) -p $(PGPORT) -U $(PGUSER) -d $(PGDATABASE) -c "\
		SELECT \
			relname as table_name, \
			n_live_tup, \
			n_dead_tup, \
			CASE WHEN n_live_tup + n_dead_tup > 0 \
				THEN round(100.0 * n_dead_tup / (n_live_tup + n_dead_tup), 1) \
				ELSE 0 \
			END as dead_pct, \
			pg_size_pretty(pg_total_relation_size(relid)) as total_size, \
			last_autovacuum \
		FROM pg_stat_user_tables \
		WHERE relname LIKE 'documents%' \
		ORDER BY relname;"

psql: ## Open psql shell
	PGPASSWORD=$(PGPASSWORD) psql -h $(PGHOST) -p $(PGPORT) -U $(PGUSER) -d $(PGDATABASE)

# Backup and Restore targets

backup-db: ## Create a full database backup using pg_dump
	@echo "Creating database backup..."
	cd $(SCRIPTS_DIR) && $(PYTHON) -m backup.backup_db

backup-db-named: ## Create a named database backup (NAME=mybackup)
ifndef NAME
	$(error NAME is required. Usage: make backup-db-named NAME=<backup_name>)
endif
	@echo "Creating database backup: $(NAME)"
	cd $(SCRIPTS_DIR) && $(PYTHON) -m backup.backup_db --name $(NAME)

restore-db: ## Restore database from backup (BACKUP=path/to/backup.dump)
ifndef BACKUP
	$(error BACKUP is required. Usage: make restore-db BACKUP=<backup_file>)
endif
	@echo "Restoring database from: $(BACKUP)"
	cd $(SCRIPTS_DIR) && $(PYTHON) -m backup.restore_db $(BACKUP)

restore-db-clean: ## Restore database with clean (drops objects first) (BACKUP=path/to/backup.dump)
ifndef BACKUP
	$(error BACKUP is required. Usage: make restore-db-clean BACKUP=<backup_file>)
endif
	@echo "Restoring database (with clean) from: $(BACKUP)"
	cd $(SCRIPTS_DIR) && $(PYTHON) -m backup.restore_db $(BACKUP) --clean

backup-volume: ## Create a Docker volume snapshot
	@echo "Creating Docker volume snapshot..."
	cd $(SCRIPTS_DIR) && $(PYTHON) -m backup.backup_volume

backup-volume-named: ## Create a named volume snapshot (NAME=mybackup)
ifndef NAME
	$(error NAME is required. Usage: make backup-volume-named NAME=<backup_name>)
endif
	@echo "Creating volume snapshot: $(NAME)"
	cd $(SCRIPTS_DIR) && $(PYTHON) -m backup.backup_volume --name $(NAME)

restore-volume: ## Restore Docker volume from snapshot (BACKUP=path/to/backup.tar.gz)
ifndef BACKUP
	$(error BACKUP is required. Usage: make restore-volume BACKUP=<backup_file>)
endif
	@echo "Restoring volume from: $(BACKUP)"
	cd $(SCRIPTS_DIR) && $(PYTHON) -m backup.restore_volume $(BACKUP)

list-backups: ## List all available backups
	@echo "=== Database Backups ==="
	@cd $(SCRIPTS_DIR) && $(PYTHON) -m backup.backup_db --list
	@echo ""
	@echo "=== Volume Backups ==="
	@cd $(SCRIPTS_DIR) && $(PYTHON) -m backup.backup_volume --list

# Cleanup targets

clean: ## Full cleanup (stops containers, removes volumes and outputs)
	cd $(TERRAFORM_DIR) && terraform destroy -auto-approve || true
	docker volume rm pg-mvcc-data 2>/dev/null || true
	rm -rf output/*
	rm -rf $(TERRAFORM_DIR)/generated
	@echo "Cleanup complete!"

clean-output: ## Remove output files only
	rm -rf output/*

# Web app targets

webapp-install: ## Install web app dependencies
	@echo "Installing frontend dependencies..."
	cd webapp && npm install
	@echo "Installing API dependencies..."
	cd api && pip install -r requirements.txt

webapp-dev: ## Start web app in development mode
	@echo "Starting web app (frontend + backend)..."
	@echo "Frontend: http://localhost:3000"
	@echo "Backend API: http://localhost:5000"
	@make -j2 webapp-frontend webapp-backend

webapp-frontend: ## Start frontend dev server
	cd webapp && npm run dev

webapp-backend: ## Start backend API server
	cd api && $(PYTHON) server.py

webapp-build: ## Build web app for production
	cd webapp && npm run build
	@echo "Production build created in webapp/dist/"

# Development targets

lint: ## Run linting on Python code
	cd $(SCRIPTS_DIR) && $(PYTHON) -m flake8 .

fmt: ## Format Python code
	cd $(SCRIPTS_DIR) && $(PYTHON) -m black .

# Comparison experiments

compare-toast: ## Run TOAST behavior comparison (toast-mutation vs toast-reuse)
	@echo "Running TOAST comparison experiments..."
	$(MAKE) experiment PRESET=toast-mutation
	$(MAKE) experiment PRESET=toast-reuse

compare-schemas: ## Run schema design comparison (bloat-demo vs normalized-stability)
	@echo "Running schema comparison experiments..."
	$(MAKE) experiment PRESET=bloat-demo
	$(MAKE) infra AUTOVACUUM=aggressive
	$(MAKE) experiment PRESET=normalized-stability

compare-workloads: ## Run workload pattern comparison
	@echo "Running workload comparison experiments..."
	$(MAKE) experiment PRESET=read-heavy
	$(MAKE) experiment PRESET=write-heavy
	$(MAKE) experiment PRESET=balanced
