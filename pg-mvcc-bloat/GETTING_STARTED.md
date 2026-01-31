# 🚀 Getting Started with the MVCC Visualizer

A step-by-step guide to run your first experiment and visualize it.

## Prerequisites Check

Before starting, verify you have:
- [ ] Docker installed and running
- [ ] Python 3.9+ installed
- [ ] Node.js 18+ and npm installed
- [ ] Terraform 1.0+ installed
- [ ] At least 10GB free disk space

```bash
# Quick verification
docker --version
python3 --version
node --version
npm --version
terraform --version
```

## 5-Minute Quick Start

### Step 1: Start PostgreSQL (30 seconds)

```bash
cd pg-mvcc-bloat
make infra AUTOVACUUM=disabled
```

Wait for: "PostgreSQL is ready!"

### Step 2: Setup Database (30 seconds)

```bash
# Apply schema
make migrate

# Quick seed with 100k rows
make seed-quick
```

This creates a 1GB database with JSONB documents.

### Step 3: Install Web App (2 minutes)

```bash
# Install all dependencies
make webapp-install
```

This installs both frontend (React) and backend (Flask) dependencies.

### Step 4: Start Web App (10 seconds)

```bash
# Option 1: Use the start script
./start-webapp.sh

# Option 2: Use make
make webapp-dev
```

Visit http://localhost:3000

### Step 5: Run Your First Experiment (1 minute)

In a new terminal:

```bash
make experiment PRESET=bloat-demo-short
```

Watch the experiment run for 60 seconds.

### Step 6: View Results

1. Refresh the web app (http://localhost:3000)
2. Click on the latest experiment in the list
3. Explore the charts:
   - **Storage Growth**: Watch TOAST size explode
   - **Dead Tuples**: See accumulation to 100%
   - **HOT Updates**: Observe 0% due to JSONB changes
   - **Buffer Cache**: Monitor cache hit ratio

## Understanding What You See

### Storage Growth Chart
- **Blue line (Table)**: Main table size grows ~3x
- **Red line (TOAST)**: TOAST table grows ~6x (worst-case)
- **Orange line (Indexes)**: Index size grows ~2x
- **Purple line (Total)**: Overall storage growth

**Why?** Every JSONB update creates a new TOAST entry, even if you change just one field.

### Dead Tuples Chart
- **Green area**: Live tuples (constant at 100k)
- **Red area**: Dead tuples (grows to 595k+)

**Why?** With autovacuum disabled, every update creates a dead tuple that never gets cleaned up.

### HOT Update Ratio
- **Flatline at 0%**

**Why?** JSONB changes prevent Heap-Only Tuple updates. The normalized schema shows higher HOT ratios.

### Buffer Cache Hit Ratio
- **Starts ~70%, rises to ~95%**

**Why?** As the table grows, more data fits in memory cache. But query times still increase due to scanning dead tuples.

## Next Steps

### Try Different Experiments

```bash
# Compare TOAST behavior
make experiment PRESET=toast-mutation
make experiment PRESET=toast-reuse

# Compare workloads
make experiment PRESET=read-heavy
make experiment PRESET=write-heavy

# See vacuum recovery
make vacuum-full
make experiment PRESET=vacuum-recovery
```

### Try Live Monitoring

1. In web app, click "Live View" tab
2. In terminal: `make experiment PRESET=bloat-demo`
3. Watch real-time metrics update every 5 seconds
4. See current stats cards at the top

### Generate a Report

```bash
# Find your run ID
ls output/metrics/

# Generate markdown report
make report RUN=bloat-demo_20260127_203000
```

View the report in `output/reports/<run_id>_report.md`

## Common Issues

### "PostgreSQL container not running"
```bash
# Restart infrastructure
make down
make infra AUTOVACUUM=disabled
```

### "No experiments found" in web app
```bash
# Ensure you've run an experiment
make experiment PRESET=bloat-demo-short

# Check output directory
ls -la output/metrics/
```

### "Connection Error" in Live View
```bash
# Verify PostgreSQL is accessible
make stats

# Check database connection
PGPASSWORD=postgres psql -h localhost -p 5433 -U postgres -d mvcc_experiment -c "SELECT 1"
```

### Web app won't start
```bash
# Reinstall dependencies
cd webapp && rm -rf node_modules && npm install
cd ../api && pip install -r requirements.txt
```

## Tips for Best Experience

1. **Start Small**: Use `bloat-demo-short` (1 min) before `bloat-demo` (5 min)
2. **Clean Between Runs**: Use `make vacuum-full` to reset table state
3. **Use Quick Seed**: 100k rows is sufficient for demonstration
4. **Monitor Live**: Live View is most impressive during active experiments
5. **Compare Presets**: Run multiple presets and compare results

## Architecture Overview

```
Web Browser (localhost:3000)
    │
    ├─ React Frontend (Vite)
    │   └─ Charts (Recharts/D3.js)
    │
    └─ Flask API (localhost:5000)
        │
        ├─ CSV Files (Historical)
        └─ PostgreSQL (Live)
            │
            └─ Experiment Scripts
```

## What's Happening Behind the Scenes?

### During Seed
1. Python generates 100k deterministic JSONB documents (3-4KB each)
2. Documents stored in table (~8MB) and TOAST (~400MB)
3. GIN index created on JSONB fields (~200MB)

### During Experiment
1. Writer processes update random rows
2. Each update creates:
   - New row version (dead tuple)
   - New TOAST entry (6x growth)
   - Index update (2x growth)
3. Metrics collector polls every 5 seconds
4. Results saved to CSV

### In Web App
1. Backend reads CSV or queries PostgreSQL
2. Frontend renders charts with Recharts
3. Live view polls every 5 seconds
4. Charts update smoothly with animations

## Experiment Presets Explained

| Preset | Duration | Goal | Key Insight |
|--------|----------|------|-------------|
| `bloat-demo-short` | 1 min | Quick test | Fast bloat demo |
| `bloat-demo` | 5 min | Worst case | 6x TOAST growth |
| `toast-mutation` | 5 min | JSONB updates | New TOAST entries |
| `toast-reuse` | 5 min | Scalar updates | Reuse TOAST pointers |
| `read-heavy` | 5 min | Query impact | Degradation under bloat |
| `write-heavy` | 5 min | Max bloat | Rapid accumulation |
| `normalized-stability` | 5 min | Good design | HOT updates work |

## Cleanup

When done experimenting:

```bash
# Stop web app (Ctrl+C in terminal)

# Stop PostgreSQL
make down

# Remove all data (optional)
make clean
```

## Learn More

- **Project Documentation**: [README.md](README.md)
- **Web App Guide**: [webapp/README.md](webapp/README.md)
- **Architecture**: [ARCHITECTURE.md](ARCHITECTURE.md)
- **Implementation Details**: [WEBAPP_IMPLEMENTATION.md](WEBAPP_IMPLEMENTATION.md)
- **Full Project Plan**: [PROJECT_PLAN.md](PROJECT_PLAN.md)

## Getting Help

1. Check `make help` for all available commands
2. Review the error message carefully
3. Verify PostgreSQL is running: `docker ps`
4. Check logs: `docker logs postgres_mvcc`
5. Review the PROJECT_PLAN.md for detailed explanations

---

**Ready to explore PostgreSQL MVCC behavior?**

Start with: `./start-webapp.sh` and `make experiment PRESET=bloat-demo-short`

Happy experimenting! 🎉
