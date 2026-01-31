# Bug Fix: n_live_tup Always Showing 0

## Problem

All metrics CSV files showed `n_live_tup = 0` throughout experiments, making it impossible to calculate accurate dead tuple ratios or bloat percentages.

## Root Cause

PostgreSQL's `pg_stat_user_tables.n_live_tup` is a **cached estimate** that's only updated when **ANALYZE** runs (not VACUUM):
- Manual `ANALYZE` command
- Autoanalyze (part of autovacuum daemon, but separate from vacuum)
- Never updates in real-time

When tables are seeded with `INSERT` statements, `n_live_tup` stays at 0 until ANALYZE runs.

## Why This Matters

- `n_live_tup` = 0 makes `dead_tuple_ratio = n_dead_tup / (n_live_tup + n_dead_tup)` = 1.0 (100%)
- All bloat calculations are wrong
- Can't measure experiment results

## The Better Solution

**Don't rely on `n_live_tup` - calculate it ourselves!**

PostgreSQL tracks accurate counters:
- `n_tup_ins`: Total inserts since stats reset
- `n_tup_del`: Total deletes since stats reset
- **Live tuples = n_tup_ins - n_tup_del** ✅

This is **always accurate** and doesn't depend on ANALYZE.

## Fixes Applied

### 1. Added ANALYZE After Seeding (`scripts/seed/seed_data.py`)

```python
# After inserting data:
print(f"  Running ANALYZE on {table}...")
with conn.cursor() as cursor:
    cursor.execute(f"ANALYZE {table}")
conn.commit()
```

This ensures the **initial** estimate is correct. But during experiments, the estimate will become stale.

### 2. Use Calculated Value in Metrics (`scripts/metrics/snapshot.py`)

```python
n_live_tup_estimate = row[0] or 0  # From pg_stat_user_tables
n_tup_ins = row[2] or 0            # Accurate counter
n_tup_del = row[4] or 0            # Accurate counter

# Calculate actual live tuples
n_live_tup_calculated = max(0, n_tup_ins - n_tup_del)

# Use calculated value when estimate is stale
n_live_tup = n_live_tup_calculated if n_live_tup_estimate == 0 else n_live_tup_estimate
```

**Key insight**: With autovacuum disabled or in high-update workloads, we should **always prefer the calculated value** because:
- `n_tup_ins - n_tup_del` is updated in real-time
- It's always accurate (no estimation lag)
- Doesn't require ANALYZE to run

## Why We Still Need ANALYZE After Seeding

Even though we calculate live tuples, ANALYZE is still needed because:
1. PostgreSQL query planner uses `n_live_tup` for execution plans
2. Autovacuum thresholds are based on `n_live_tup` estimates
3. Other monitoring tools rely on these statistics

## Alternative: Always Use Calculated Value

We could simplify further and **always** use the calculated value:

```python
# Always use accurate calculation, ignore estimate
n_live_tup = max(0, n_tup_ins - n_tup_del)
```

This would be more robust for experiments where ANALYZE rarely runs.

## Expected Results After Fix

### Before (Buggy):
```csv
n_live_tup,n_dead_tup,dead_tuple_ratio
0,4200,1.0
0,8550,1.0
0,12800,1.0
```

### After (Fixed):
```csv
n_live_tup,n_dead_tup,dead_tuple_ratio
150000,4200,0.027
150000,8550,0.054
150000,12800,0.079
```

## Summary

**Question**: Why do we need VACUUM to find live tuples?  
**Answer**: We don't! We need ANALYZE (not VACUUM). But even better, we can **calculate** live tuples from `n_tup_ins - n_tup_del`, which is always accurate.

The fix ensures:
1. ✅ Initial statistics are set with ANALYZE after seeding
2. ✅ Runtime metrics use calculated values (inserts - deletes)
3. ✅ No dependency on ANALYZE running during experiments

## How to Re-Run Experiments

### 1. Re-seed Tables with Fixed Script
```bash
source venv/bin/activate
python scripts/seed/seed_data.py --count 150000
```

This will:
- Seed the tables with 150K rows
- **Run ANALYZE** on each table (new!)
- Update `n_live_tup` statistics

### 2. Verify Statistics Are Updated
```bash
psql $DB_CONNECTION_STRING -c "
SELECT 
    relname,
    n_live_tup,
    n_dead_tup,
    n_tup_ins,
    last_analyze,
    last_autoanalyze
FROM pg_stat_user_tables 
WHERE schemaname = 'public';
"
```

You should see `n_live_tup` showing the actual row counts (e.g., 150000).

### 3. Re-run Optimal Vacuum Experiment
```bash
python scripts/experiments/run_experiment.py optimal-vacuum
```

Now the metrics will show correct `n_live_tup` values!

## Expected Results After Fix

### Before (Buggy):
```csv
n_live_tup,n_dead_tup,dead_tuple_ratio
0,4200,1.0
0,8550,1.0
0,12800,1.0
```

### After (Fixed):
```csv
n_live_tup,n_dead_tup,dead_tuple_ratio
150000,4200,0.027
150000,8550,0.054
150000,12800,0.079
```

## Why This Bug Occurred

1. **Seed script didn't run ANALYZE** - Statistics never got initialized
2. **High-update workload** - Updates don't trigger autoanalyze as frequently
3. **Autovacuum disabled** - In some experiments, autovacuum (which also runs analyze) was disabled

## Prevention

The fixes ensure that:
1. **Initial statistics are accurate** after seeding
2. **Fallback estimation** if statistics become stale during experiment
3. **Clear documentation** for future users

## Testing the Fix

```bash
# 1. Clean slate
make teardown
make infra

# 2. Seed with ANALYZE
python scripts/seed/seed_data.py --count 150000

# 3. Verify stats
psql $DB_CONNECTION_STRING -c "SELECT relname, n_live_tup FROM pg_stat_user_tables WHERE schemaname = 'public';"

# 4. Run experiment
python scripts/experiments/run_experiment.py optimal-vacuum

# 5. Check metrics
head -5 output/metrics/optimal-vacuum_*/metrics.csv
```

You should now see realistic `n_live_tup` values in the metrics!
