# Optimal Vacuum Experiment Guide

## Overview
The `optimal-vacuum` experiment preset tests production-like workloads with highly tuned autovacuum settings designed to minimize bloat while maintaining performance.

## Key Settings

### Autovacuum Configuration
```sql
-- Per-table settings in the optimal-vacuum preset:
ALTER TABLE documents_jsonb SET (
    autovacuum_vacuum_scale_factor = 0.02,  -- Trigger at 2% dead tuples (vs 20% default)
    autovacuum_vacuum_threshold = 50,       -- Base threshold
    autovacuum_vacuum_cost_delay = 5,       -- Faster cleanup
    autovacuum_naptime = 10                 -- Check every 10 seconds
);
```

### Workload Profile
- **Read Workers**: 8 (simulates read-heavy production)
- **Write Workers**: 3 (realistic update rate)
- **Batch Size**: 50 updates per transaction
- **Rate Limit**: 100 updates/sec (sustainable high load)
- **Duration**: 900 seconds (15 minutes)

## Running the Experiment

### 1. Prepare Infrastructure
```bash
cd terraform
terraform apply -var="autovacuum_mode=aggressive" -var="experiment_pass=optimal-vacuum"
```

### 2. Activate Virtual Environment
```bash
source venv/bin/activate
```

### 3. Run the Experiment
```bash
python scripts/experiments/run_experiment.py optimal-vacuum
```

### 4. Monitor Progress
The experiment tracks:
- Dead tuple accumulation rate
- Autovacuum frequency and duration
- Buffer cache hit ratio
- Index bloat metrics
- Query performance over time

## Expected Outcomes

### Success Criteria
1. **Dead tuple ratio stays below 5%** throughout the run
2. **Autovacuum triggers every 30-60 seconds** (frequent but not thrashing)
3. **Query performance remains stable** (no degradation over time)
4. **Buffer cache efficiency** maintains high hit ratio

### Comparison Points
Compare against:
- `production-simulation`: Default aggressive settings (5% scale factor)
- `high-churn-aggressive-vacuum`: Higher write load
- `bloat-demo`: No autovacuum (worst case)

## Metrics to Analyze

### 1. Dead Tuple Metrics
```bash
# Check metrics CSV after run
cd output/metrics
cat optimal-vacuum_metrics.csv | csvlook
```

Key columns:
- `n_dead_tup`: Should stay low
- `n_live_tup`: Should grow steadily
- `last_autovacuum`: Frequent timestamps
- `dead_ratio`: Target < 0.05 (5%)

### 2. Index Bloat
```sql
SELECT 
    indexrelname,
    pg_size_pretty(pg_relation_size(indexrelid)) as size,
    idx_scan,
    ROUND(100.0 * idx_tup_read / NULLIF(idx_tup_fetch, 0), 1) as bloat_pct
FROM pg_stat_user_indexes
WHERE schemaname = 'public';
```

### 3. Buffer Cache Impact
```sql
SELECT 
    heap_blks_read,
    heap_blks_hit,
    ROUND(100.0 * heap_blks_hit / NULLIF(heap_blks_hit + heap_blks_read, 0), 2) as cache_hit_ratio
FROM pg_statio_user_tables
WHERE relname = 'documents_jsonb';
```

## Tuning Guidelines

### If Dead Tuples Accumulate Too Fast
```sql
-- Lower the scale factor
ALTER TABLE documents_jsonb SET (
    autovacuum_vacuum_scale_factor = 0.01  -- 1% trigger
);
```

### If Autovacuum Thrashes (Too Frequent)
```sql
-- Increase scale factor slightly
ALTER TABLE documents_jsonb SET (
    autovacuum_vacuum_scale_factor = 0.03,  -- 3% trigger
    autovacuum_vacuum_cost_delay = 10       -- Slower but less I/O impact
);
```

### If VACUUM Takes Too Long
```sql
-- Allocate more resources
ALTER SYSTEM SET maintenance_work_mem = '256MB';
ALTER SYSTEM SET autovacuum_max_workers = 4;
```

## Slideshow Integration

View the slideshow to understand the concepts:
```bash
open slideshow.html
```

Key slides:
- **Slide 3**: MVCC version pointers
- **Slide 5**: Bloat accumulation timeline  
- **Slide 7**: Autovacuum threshold formula
- **Slide 8**: Buffer cache impact
- **Slide 9**: Index bloat
- **Slide 10**: VACUUM vs VACUUM FULL
- **Slide 18**: Tuning recommendations

## Next Steps

1. **Run baseline experiments** for comparison:
   ```bash
   python scripts/experiments/run_experiment.py production-simulation
   ```

2. **Run optimal-vacuum**:
   ```bash
   python scripts/experiments/run_experiment.py optimal-vacuum
   ```

3. **Compare metrics**:
   ```bash
   python scripts/metrics/compare_experiments.py production-simulation optimal-vacuum
   ```

4. **Adjust settings** based on results and re-run

## Notes

- The `extra_config` in the preset is informational; actual per-table settings need to be applied via SQL or Terraform
- Monitor PostgreSQL logs for autovacuum activity: `log_autovacuum_min_duration = 0`
- Consider running during off-peak hours first to validate settings
