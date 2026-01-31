# Autovacuum Configuration Enhancement - Summary

## Problem Identified

The project had autovacuum configuration at the infrastructure level (via Terraform), but individual experiments could not override or configure autovacuum settings dynamically. Most experiment presets had `autovacuum_mode` hardcoded to "disabled", which limited the ability to:

1. Compare autovacuum strategies without infrastructure restarts
2. Test production-like scenarios with proper autovacuum tuning
3. Demonstrate the benefits of aggressive autovacuum in high-churn scenarios

## Changes Implemented

### 1. Dynamic Autovacuum Configuration (`run_experiment.py`)

**Added `_configure_autovacuum()` method:**
- Applies table-level autovacuum settings based on the preset's `autovacuum_mode`
- Supports three modes: `disabled`, `default`, `aggressive`
- Uses `ALTER TABLE` statements to configure per-table settings
- Verifies global autovacuum status and warns about conflicts
- Called automatically before baseline capture in each experiment

**Settings by mode:**

| Mode | Behavior |
|------|----------|
| `disabled` | Disables autovacuum for the target table only |
| `default` | Resets to PostgreSQL defaults (20% scale factor, 50 tuple threshold) |
| `aggressive` | Sets aggressive thresholds (1% scale factor, 25 tuple threshold) |

### 2. New Experiment Presets (`presets.py`)

**Added 4 new presets:**

1. **`hot-updates-no-vacuum`**: HOT-eligible updates without autovacuum
2. **`hot-updates-with-vacuum`**: HOT-eligible updates with aggressive autovacuum
3. **`production-simulation`**: Production-like balanced workload with default autovacuum (600s)
4. **`high-churn-aggressive-vacuum`**: High-update scenario with aggressive autovacuum (600s)

**Updated preset comparison groups:**
- Added `hot_updates` comparison group
- Added `production_scenarios` comparison group

### 3. Documentation

**Created `AUTOVACUUM_GUIDE.md`:**
- Comprehensive guide explaining two-level configuration
- Table showing settings for each autovacuum mode
- Example workflows for common testing scenarios
- Troubleshooting section
- Instructions for creating custom presets

**Updated `README.md`:**
- Added link to autovacuum guide in overview
- Expanded preset table with all available presets
- Added autovacuum configuration examples
- Added note about automatic per-experiment configuration

## Benefits

### For Users

1. **No infrastructure restarts needed**: Switch between autovacuum strategies by running different presets
2. **Easy comparisons**: Run `bloat-demo` followed by `autovacuum-aggressive` to see the difference
3. **Production testing**: Use realistic autovacuum settings with `production-simulation` preset
4. **Flexible experimentation**: Mix and match workloads with different autovacuum behaviors

### For the Project

1. **More comprehensive**: Now demonstrates both problems (bloat) and solutions (autovacuum)
2. **Better defaults**: Infrastructure can start with `AUTOVACUUM=default` and experiments control per-table behavior
3. **Educational value**: Shows how autovacuum tuning affects real workloads
4. **Reproducible**: Each experiment explicitly declares its autovacuum configuration

## Example Usage

### Compare Autovacuum Impact
```bash
# Start infrastructure with default settings
make infra AUTOVACUUM=default

# Run same workload with different autovacuum modes
python scripts/experiments/run_experiment.py bloat-demo              # disabled
python scripts/experiments/run_experiment.py autovacuum-default      # default
python scripts/experiments/run_experiment.py autovacuum-aggressive   # aggressive

# Generate comparison report
python scripts/report/generate_report.py --compare bloat-demo,autovacuum-default,autovacuum-aggressive
```

### HOT Updates Analysis
```bash
# Compare HOT updates with and without autovacuum
python scripts/experiments/run_experiment.py hot-updates-no-vacuum     # accumulates dead tuples
python scripts/experiments/run_experiment.py hot-updates-with-vacuum   # cleans up regularly
```

### Production Simulation
```bash
# Test production-like workload with realistic autovacuum
python scripts/experiments/run_experiment.py production-simulation
```

## Technical Details

### How It Works

1. When `run_experiment.py` starts, it calls `_configure_autovacuum()`
2. This method executes SQL commands to configure the table:
   - `ALTER TABLE {table} SET (autovacuum_enabled = false)` for disabled mode
   - `ALTER TABLE {table} RESET (...)` for default mode
   - `ALTER TABLE {table} SET (autovacuum_vacuum_scale_factor = 0.01, ...)` for aggressive mode
3. Settings persist until changed by another experiment
4. Global autovacuum status is checked and warnings issued if conflicts exist

### Independence from Infrastructure

- Table-level settings take precedence over global settings
- If global autovacuum is OFF, table-level settings have no effect (warning issued)
- Best practice: Start infrastructure with `AUTOVACUUM=default`, let experiments control per-table

## Future Enhancements

Potential additions:
1. Add more granular autovacuum modes (e.g., "moderate", "custom")
2. Allow runtime autovacuum parameter overrides via CLI
3. Add autovacuum activity monitoring to metrics collection
4. Create preset groups specifically for autovacuum comparisons
5. Add autovacuum logs to experiment reports

## Files Changed

- `scripts/experiments/run_experiment.py` - Added autovacuum configuration method
- `scripts/experiments/presets.py` - Added 4 new presets, updated comparison groups
- `README.md` - Updated preset table, added autovacuum examples, linked to guide
- `AUTOVACUUM_GUIDE.md` - New comprehensive configuration guide
- `AUTOVACUUM_SUMMARY.md` - This summary document

## Testing Recommendations

To verify the changes work correctly:

1. **Test disabled mode:**
   ```bash
   python scripts/experiments/run_experiment.py bloat-demo-short
   # Should see "Disabled autovacuum on table documents_jsonb"
   ```

2. **Test aggressive mode:**
   ```bash
   python scripts/experiments/run_experiment.py autovacuum-aggressive --duration 120
   # Should see frequent autovacuum activity in pg_stat_user_tables
   ```

3. **Test mode switching:**
   ```bash
   # Run disabled, then aggressive
   python scripts/experiments/run_experiment.py bloat-demo-short
   python scripts/experiments/run_experiment.py autovacuum-aggressive --duration 60
   # Settings should switch without any errors
   ```

4. **Verify global autovacuum warning:**
   ```bash
   # Start with global autovacuum OFF
   make infra AUTOVACUUM=disabled
   # Try to run aggressive preset
   python scripts/experiments/run_experiment.py autovacuum-aggressive --duration 60
   # Should see warning about global autovacuum being off
   ```
