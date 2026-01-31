# PostgreSQL MVCC Bloat Experiment

A reproducible experiment framework for demonstrating PostgreSQL's MVCC (Multi-Version Concurrency Control) behavior with large JSONB/TOAST tables, showing how dead tuple accumulation leads to table bloat and query degradation.

## Overview

This project provides:

- **Terraform-based infrastructure** for spinning up a Docker PostgreSQL instance with configurable autovacuum settings
- **Flexible autovacuum configuration** at both infrastructure and per-experiment levels (see [AUTOVACUUM_GUIDE.md](AUTOVACUUM_GUIDE.md))
- **Three table schemas** for comparison: pure JSONB, JSONB with scalar flags, and fully normalized
- **Deterministic data seeding** using fixed random seeds for exact reproducibility
- **Concurrent workload generation** with configurable reader/writer ratios
- **Continuous metrics collection** with CSV export
- **Query plan capture and visualization** using Graphviz
- **Automated report generation** with Markdown and embedded charts
- **🆕 Web-based visualization** with React + D3.js for real-time and historical data viewing

## Quick Start

### Prerequisites

- Docker
- Terraform >= 1.0
- Python 3.9+
- Node.js 18+ and npm (for web app)
- Graphviz (for plan visualization)

```bash
# macOS
brew install terraform graphviz node

# Ubuntu/Debian
sudo apt-get install terraform graphviz nodejs npm
```

### Setup

```bash
# Clone and enter directory
cd pg-mvcc-bloat

# Create Python virtual environment
python -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Start PostgreSQL with autovacuum disabled
make infra AUTOVACUUM=disabled

# Run migrations
make migrate

# Seed tables with 1M rows (takes ~10 minutes)
make seed
```

### Run an Experiment

```bash
# List available experiment presets
make list-presets

# Run the bloat demonstration (5 minutes)
make experiment PRESET=bloat-demo

# Or run a quick test (1 minute)
make experiment PRESET=bloat-demo-short

# Generate report
make report RUN=bloat-demo_20260125_143022  # Use your actual run ID
```

## Backup and Restore

The project provides two backup methods to avoid frequent re-seeding:

### Database Backup (pg_dump)

Fast, logical backup suitable for moving between environments:

```bash
# Create a backup
make backup-db

# Create a named backup
make backup-db-named NAME=before-experiment

# List available backups
make list-backups

# Restore from backup
make restore-db BACKUP=backups/database/backup_20260131_120000.dump

# Restore with clean (drops objects first)
make restore-db-clean BACKUP=backups/database/backup_20260131_120000.dump
```

### Volume Snapshot

Binary snapshot of the entire PostgreSQL data directory:

```bash
# Create a volume snapshot
make backup-volume

# Create a named snapshot
make backup-volume-named NAME=seeded-1M-rows

# Restore from snapshot (container must be stopped)
make down
make restore-volume BACKUP=backups/volume/volume_20260131_120000.tar.gz
make infra
```

**Note:** Volume snapshots are larger but faster to restore and preserve the exact database state including statistics and WAL files.

### Clean Up

```bash
# Stop PostgreSQL container
make down

# Full cleanup (removes data volume)
make clean
```

## Web Visualization App

A modern web interface for visualizing MVCC bloat behavior in real-time or from historical data.

### Quick Start

```bash
# Install dependencies
make webapp-install

# Start the web app (both frontend and backend)
make webapp-dev
```

Visit http://localhost:3000 to view the web interface.

### Features

- **Historical Data View**: Browse and visualize past experiment runs
- **Live Monitoring**: Real-time observation of dead tuple accumulation
- **Interactive Charts**:
  - Storage growth over time (table, TOAST, indexes)
  - Dead tuple accumulation (stacked area chart)
  - HOT update ratio tracking
  - Buffer cache hit ratio monitoring
- **Dark Mode UI**: Modern GitHub-inspired interface

See [webapp/README.md](webapp/README.md) for detailed documentation.

## Experiment Presets

| Preset | Description | Autovacuum | Workload | Duration |
|--------|-------------|------------|----------|----------|
| `bloat-demo` | Worst-case MVCC bloat demonstration | disabled | write-only | 5min |
| `bloat-demo-short` | Quick 60s test | disabled | write-only | 1min |
| `toast-mutation` | JSONB updates creating new TOAST entries | disabled | 1:2 read:write | 5min |
| `toast-reuse` | Scalar-only updates reusing TOAST pointers | disabled | 1:2 read:write | 5min |
| `normalized-stability` | Normalized schema with aggressive vacuum | aggressive | 1:2 read:write | 5min |
| `normalized-no-vacuum` | Normalized schema without vacuum | disabled | 1:2 read:write | 5min |
| `read-heavy` | Query degradation under light writes | disabled | 10:1 read:write | 5min |
| `write-heavy` | Rapid bloat with concurrent reads | disabled | 1:10 read:write | 5min |
| `balanced` | Balanced read/write workload | disabled | 5:5 read:write | 5min |
| `autovacuum-comparison-disabled` | Moderate workload, no vacuum | disabled | 2:1 read:write @ 50/s | 10min |
| `autovacuum-default` | Same workload, default vacuum | default | 2:1 read:write @ 50/s | 10min |
| `autovacuum-aggressive` | Same workload, aggressive vacuum | aggressive | 2:1 read:write @ 50/s | 10min |
| `hot-updates-no-vacuum` | HOT-eligible updates without vacuum | disabled | 2:2 read:write | 5min |
| `hot-updates-with-vacuum` | HOT-eligible updates with vacuum | aggressive | 2:2 read:write | 5min |
| `production-simulation` | Production-like balanced workload | aggressive | 8:2 read:write @ 80/s | 10min |
| `high-churn-aggressive-vacuum` | High-update with aggressive vacuum | aggressive | 2:4 read:write @ 150/s | 10min |
| `vacuum-recovery` | Post-VACUUM FULL recovery measurement | disabled | read-only | 1min |

**Note:** Each experiment automatically configures its autovacuum settings at the table level, independent of the infrastructure-level configuration. This allows running experiments with different autovacuum behaviors without restarting PostgreSQL.

**⚠️ Important:** For autovacuum to be effective with JSONB/TOAST workloads, the update rate must be balanced with vacuum frequency. The `autovacuum-*` presets use controlled workloads (50 updates/sec) to allow vacuum to keep up. High-rate workloads may overwhelm even aggressive autovacuum - see [AUTOVACUUM_GUIDE.md](AUTOVACUUM_GUIDE.md) for details.

## Project Structure

```
pg-mvcc-bloat/
├── terraform/           # Infrastructure as code
│   ├── main.tf
│   ├── variables.tf
│   ├── outputs.tf
│   └── postgres.conf.tpl
├── migrations/          # Database schema
│   ├── 001_create_tables.sql
│   └── 002_create_metrics_tables.sql
├── scripts/
│   ├── common/          # Shared utilities
│   ├── seed/            # Deterministic data generation
│   ├── workload/        # Reader/writer processes
│   ├── metrics/         # Metrics collection
│   ├── experiments/     # Preset configurations
│   ├── visualize/       # Plan visualization
│   └── report/          # Report generation
├── webapp/              # 🆕 Web visualization app
│   ├── src/
│   │   ├── components/  # React components
│   │   ├── hooks/       # Custom hooks
│   │   └── App.jsx      # Main application
│   ├── package.json
│   └── README.md
├── api/                 # 🆕 Flask backend API
│   ├── server.py        # API endpoints
│   └── requirements.txt
├── output/              # Experiment outputs
│   ├── metrics/         # CSV metrics per run
│   ├── plans/           # Query plan JSON and visuals
│   └── reports/         # Generated Markdown reports
├── notebooks/           # Jupyter notebooks for analysis
├── Makefile
├── requirements.txt
└── README.md
```

## Key Concepts Demonstrated

### 1. MVCC Version Copying

PostgreSQL copies entire rows on every UPDATE, regardless of which columns change. This experiment shows how this leads to rapid storage growth with large JSONB columns.

### 2. TOAST Behavior

Large JSONB values are stored in TOAST (The Oversized-Attribute Storage Technique) tables. The experiment compares:
- **JSONB mutations**: Create new TOAST entries on every update
- **Scalar-only updates**: Can reuse existing TOAST pointers

### 3. Dead Tuple Accumulation

Without autovacuum (or with insufficient vacuum frequency), dead tuples accumulate:
- Interleaved with live tuples in data pages
- Loaded into memory during scans
- Waste buffer cache space
- Cause query plan changes

### 4. HOT Updates

Heap-Only Tuple updates avoid index modifications when:
- No indexed columns are modified
- New tuple fits on same page as old

The normalized schema preset demonstrates higher HOT ratios.

## Customization

### Autovacuum Configuration

Autovacuum behavior can be controlled at two levels:

**1. Infrastructure Level (Global):**
```bash
# Start with aggressive autovacuum globally
make infra AUTOVACUUM=aggressive

# Default autovacuum settings
make infra AUTOVACUUM=default

# Disabled globally (experiments can still enable per-table)
make infra AUTOVACUUM=disabled
```

**2. Experiment Level (Per-Table):**

Each experiment preset specifies its own `autovacuum_mode` which is automatically applied to the target table before the experiment runs. This allows mixing experiments with different autovacuum behaviors without infrastructure restarts.

```python
# Example: Run experiments with different autovacuum configs
python scripts/experiments/run_experiment.py bloat-demo          # autovacuum disabled on table
python scripts/experiments/run_experiment.py autovacuum-default  # default settings on table
python scripts/experiments/run_experiment.py autovacuum-aggressive # aggressive on table
```

**Comparison:**
```bash
# Compare autovacuum impact on the same workload
python scripts/experiments/run_experiment.py bloat-demo             # disabled
python scripts/experiments/run_experiment.py autovacuum-aggressive  # aggressive
python scripts/report/generate_report.py --compare bloat-demo,autovacuum-aggressive
```

### Custom Experiment Duration

```bash
make experiment PRESET=bloat-demo DURATION=600  # 10 minutes
```

### Custom Seed Data

```bash
# Different row count
make seed COUNT=500000

# Different random seed
make seed SEED=12345
```

## Metrics Collected

| Metric | Source | Description |
|--------|--------|-------------|
| `n_live_tup` | pg_stat_user_tables | Live tuple count |
| `n_dead_tup` | pg_stat_user_tables | Dead tuple count |
| `n_tup_hot_upd` | pg_stat_user_tables | HOT updates count |
| `table_size_bytes` | pg_relation_size | Main table size |
| `toast_size_bytes` | pg_relation_size | TOAST table size |
| `heap_blks_read/hit` | pg_statio_user_tables | Buffer cache efficiency |
| Query plans | EXPLAIN ANALYZE | Execution plan evolution |

## Blog-Ready Output

Reports are generated in Markdown format with embedded PNG images, compatible with:
- Notion (copy-paste Markdown)
- GitHub/GitLab
- Jekyll/Hugo static sites
- Any Markdown-compatible blog platform

## Further Reading

- [Autovacuum Configuration Guide](AUTOVACUUM_GUIDE.md) - Detailed guide on configuring autovacuum at infrastructure and experiment levels
- [The Part of PostgreSQL We Hate the Most](https://www.cs.cmu.edu/~pavlo/blog/2023/04/the-part-of-postgresql-we-hate-the-most.html) - Andy Pavlo's blog post that inspired this experiment
- [PostgreSQL MVCC Documentation](https://www.postgresql.org/docs/current/mvcc.html)
- [TOAST Documentation](https://www.postgresql.org/docs/current/storage-toast.html)
- [Autovacuum Tuning](https://www.postgresql.org/docs/current/routine-vacuuming.html)

## License

MIT
