# Autovacuum Configuration Guide

This project supports flexible autovacuum configuration at both infrastructure and experiment levels, allowing you to test different scenarios without infrastructure restarts.

## Important: Autovacuum vs. Workload Rate

**Critical insight:** Autovacuum effectiveness depends on the balance between workload rate and autovacuum aggressiveness.

### Why Default Autovacuum May Not Help

With **JSONB/TOAST-heavy workloads** that rapidly update rows:
- Each update creates a NEW version of the entire JSONB blob in TOAST
- This generates dead tuples very quickly
- Default autovacuum (triggers at 20% dead tuples) may not run often enough
- By the time autovacuum starts, thousands of dead tuples have accumulated

### Autovacuum Trigger Math

Autovacuum runs when: `dead_tuples > threshold + (scale_factor * live_tuples)`

**Example with 100,000 rows:**
- **Default**: `50 + (0.2 * 100,000) = 20,050` dead tuples needed
- **Aggressive**: `25 + (0.01 * 100,000) = 1,025` dead tuples needed

**The Problem:** Once updates start:
1. Live tuples quickly become dead (they're replaced by new versions)
2. `n_live_tup` drops toward 0
3. Threshold becomes just the base (50 or 25)
4. But if updates are coming in at 200/sec, you accumulate 2,000 dead tuples in 10 seconds
5. Even aggressive autovacuum (5s naptime) might not keep up

### Workload Rate Guidelines

| Autovacuum Mode | Max Update Rate | Reasoning |
|----------------|-----------------|-----------|
| disabled | unlimited | For bloat demonstrations only |
| default | ~50 updates/sec | Gives autovacuum time to run every 60s |
| aggressive | ~150 updates/sec | Runs every 5s, handles moderate churn |

**For truly high-update workloads (200+ updates/sec):**
- Use more aggressive table-level settings (see Custom Tuning below)
- Consider partitioning or normalized schemas
- Or accept some bloat and run VACUUM during maintenance windows

## Two-Level Configuration

1. **Infrastructure Level (Global)**: Set via Terraform when starting PostgreSQL
2. **Experiment Level (Per-Table)**: Set automatically by each experiment preset

This design allows you to:
- Run experiments with different autovacuum behaviors back-to-back
- Compare autovacuum strategies without restarting the database
- Test production-like scenarios with minimal setup changes

## Infrastructure Level (Global)

Controlled via the `AUTOVACUUM` environment variable when starting infrastructure:

```bash
# Disable autovacuum globally
make infra AUTOVACUUM=disabled

# Use PostgreSQL default settings
make infra AUTOVACUUM=default

# Use aggressive settings
make infra AUTOVACUUM=aggressive
```

### Global Settings by Mode

| Setting | disabled | default | aggressive |
|---------|----------|---------|------------|
| `autovacuum` | off | on | on |
| `autovacuum_vacuum_scale_factor` | - | 0.2 (20%) | 0.01 (1%) |
| `autovacuum_analyze_scale_factor` | - | 0.1 (10%) | 0.005 (0.5%) |
| `autovacuum_vacuum_threshold` | - | 50 tuples | 25 tuples |
| `autovacuum_naptime` | - | 60s | 5s |

**When to use:**
- `disabled`: For demonstrations showing worst-case bloat
- `default`: For production-like baseline testing
- `aggressive`: For high-churn tables or when minimizing bloat is critical

## Experiment Level (Per-Table)

Each experiment preset has an `autovacuum_mode` field that configures autovacuum behavior for the target table:

```python
ExperimentPreset(
    name="my-experiment",
    table="documents_jsonb",
    autovacuum_mode="aggressive",  # disabled | default | aggressive
    # ...
)
```

### Table-Level Settings by Mode

**disabled:**
```sql
ALTER TABLE target_table SET (autovacuum_enabled = false);
```
- Completely disables autovacuum for the table
- Dead tuples accumulate indefinitely
- Useful for demonstrating bloat problems

**default:**
```sql
ALTER TABLE target_table RESET (
    autovacuum_enabled,
    autovacuum_vacuum_scale_factor,
    autovacuum_analyze_scale_factor,
    autovacuum_vacuum_threshold,
    autovacuum_vacuum_cost_delay
);
```
- Uses global/default PostgreSQL settings
- Triggers vacuum at ~20% dead tuples
- Balanced between performance and bloat control

**aggressive:**
```sql
ALTER TABLE target_table SET (
    autovacuum_enabled = true,
    autovacuum_vacuum_scale_factor = 0.01,     -- 1% dead tuples
    autovacuum_analyze_scale_factor = 0.005,   -- 0.5% changes
    autovacuum_vacuum_threshold = 25,          -- minimum 25 tuples
    autovacuum_vacuum_cost_delay = 2           -- 2ms
);
```
- Triggers vacuum very frequently
- Minimizes bloat accumulation
- Higher CPU/IO overhead but better query performance

## How It Works

When you run an experiment:

1. **Experiment starts**: `run_experiment.py` loads the preset
2. **Autovacuum configured**: `_configure_autovacuum()` applies table-level settings
3. **Verification**: Checks global autovacuum status and warns if conflicts exist
4. **Experiment runs**: Workload executes with configured autovacuum behavior
5. **Settings persist**: Table-level settings remain until changed by another experiment

### Important Notes

**Table-level settings override global settings:**
- Even if global autovacuum is `off`, you can enable it per-table
- But if global autovacuum is `off`, table-level `aggressive` won't work (you'll get a warning)

**Best Practice:**
- Start infrastructure with `AUTOVACUUM=default` for most testing
- Let experiments control per-table behavior
- Use `AUTOVACUUM=disabled` only for pure bloat demonstrations

## Example Workflows

### Compare Autovacuum Impact

Run the same workload with different autovacuum settings:

```bash
# Infrastructure with global autovacuum enabled
make infra AUTOVACUUM=default

# Run experiments with different table-level settings
python scripts/experiments/run_experiment.py bloat-demo              # disabled
python scripts/experiments/run_experiment.py autovacuum-default      # default
python scripts/experiments/run_experiment.py autovacuum-aggressive   # aggressive

# Compare results
python scripts/report/generate_report.py --compare bloat-demo,autovacuum-default,autovacuum-aggressive
```

### Production Simulation

Test production-like workload with various autovacuum strategies:

```bash
make infra AUTOVACUUM=default

# Simulate production with default autovacuum
python scripts/experiments/run_experiment.py production-simulation

# Try aggressive autovacuum for high-churn scenario
python scripts/experiments/run_experiment.py high-churn-aggressive-vacuum
```

### HOT Updates Comparison

Compare HOT update behavior with and without autovacuum:

```bash
make infra AUTOVACUUM=default

# Without autovacuum (dead tuples accumulate but HOT still works)
python scripts/experiments/run_experiment.py hot-updates-no-vacuum

# With aggressive autovacuum (dead tuples cleaned up frequently)
python scripts/experiments/run_experiment.py hot-updates-with-vacuum
```

## Monitoring Autovacuum Activity

View autovacuum activity during experiments:

```sql
-- Check table-level autovacuum settings
SELECT relname, reloptions 
FROM pg_class 
WHERE relname LIKE 'documents%';

-- Monitor autovacuum runs
SELECT schemaname, relname, last_vacuum, last_autovacuum, 
       n_tup_ins, n_tup_upd, n_tup_del, n_live_tup, n_dead_tup
FROM pg_stat_user_tables 
WHERE relname LIKE 'documents%';

-- View active autovacuum processes
SELECT pid, query_start, state, query 
FROM pg_stat_activity 
WHERE query LIKE '%autovacuum%';
```

## Troubleshooting

### Table-level settings not working

**Problem:** Set `autovacuum_mode="aggressive"` but no autovacuum runs

**Solution:** Check global autovacuum:
```bash
psql -h localhost -U postgres -d bloat_demo -c "SHOW autovacuum;"
```

If it's `off`, restart infrastructure with autovacuum enabled:
```bash
make infra-down
make infra AUTOVACUUM=default
```

### Too much autovacuum activity

**Problem:** Aggressive autovacuum causing performance issues

**Solution:** Use less aggressive settings:
```python
# In presets.py, change:
autovacuum_mode="default"  # instead of "aggressive"
```

### Autovacuum not cleaning up fast enough

**Problem:** Default settings allow too much bloat, even with autovacuum enabled

**Root Cause:** Workload update rate exceeds autovacuum's ability to keep up

**Solution:** 
1. **Use aggressive preset for the experiment**
2. **Reduce write rate** in the preset (lower `rate_limit`, fewer `write_workers`)
3. **Or tune per-table** to be even more aggressive:
```sql
ALTER TABLE documents_jsonb SET (
    autovacuum_vacuum_scale_factor = 0.005,  -- 0.5% threshold (very aggressive)
    autovacuum_vacuum_threshold = 25,
    autovacuum_naptime = '3s'  -- Check every 3 seconds
);
```

**Verification:**
```sql
-- Check if autovacuum is actually running
SELECT schemaname, relname, last_autovacuum, autovacuum_count
FROM pg_stat_user_tables 
WHERE relname = 'documents_jsonb';

-- Monitor dead tuple ratio during experiment
SELECT n_live_tup, n_dead_tup, 
       CASE WHEN n_live_tup > 0 
            THEN ROUND(n_dead_tup::numeric / n_live_tup::numeric, 2)
            ELSE NULL END as dead_to_live_ratio
FROM pg_stat_user_tables 
WHERE relname = 'documents_jsonb';
```

## Creating Custom Presets

Add your own experiment presets with specific autovacuum behavior:

```python
# In scripts/experiments/presets.py

register_preset(ExperimentPreset(
    name="my-custom-test",
    description="Custom workload with moderate autovacuum",
    table="documents_jsonb",
    update_pattern="jsonb_mutation",
    read_workers=5,
    write_workers=3,
    batch_size=100,
    rate_limit=150,
    duration_seconds=300,
    autovacuum_mode="default",  # Choose: disabled, default, or aggressive
))
```

Then run it:
```bash
python scripts/experiments/run_experiment.py my-custom-test
```

## References

- [PostgreSQL Autovacuum Tuning](https://www.postgresql.org/docs/current/routine-vacuuming.html#AUTOVACUUM)
- [Understanding Autovacuum](https://www.postgresql.org/docs/current/runtime-config-autovacuum.html)
- [Monitoring Autovacuum](https://wiki.postgresql.org/wiki/Monitoring_autovacuum)
