# Data Cleanup Workflow

## Summary

**Tables are cleaned automatically** by the seed script using `TRUNCATE`. You don't need to manually clean before seeding.

## The Workflow

### 1. Infrastructure Setup (First Time)
```bash
make infra AUTOVACUUM=aggressive
```
- Starts PostgreSQL container
- Creates database
- **Does NOT** create tables yet

### 2. Run Migrations (First Time)
```bash
make migrate
```
- Creates tables with `CREATE TABLE IF NOT EXISTS`
- Creates indexes
- Creates metrics tracking tables
- **Tables start empty**

### 3. Seed Data (Every Time You Want Fresh Data)
```bash
make seed COUNT=150000
# or
python scripts/seed/seed_data.py --count 150000
```

**This automatically cleans the tables!**

Line 218 in `seed_data.py`:
```python
cursor.execute(f"TRUNCATE {table} RESTART IDENTITY CASCADE")
```

What TRUNCATE does:
- ✅ Removes all rows from the table
- ✅ Resets SERIAL sequences (RESTART IDENTITY)
- ✅ Cascades to dependent tables
- ✅ Faster than DELETE
- ✅ Reclaims disk space immediately

### 4. Run Experiment
```bash
make experiment PRESET=optimal-vacuum
```
- Uses the seeded data
- Updates rows (creating dead tuples)
- Collects metrics

### 5. Seed Again (If Needed)
```bash
make seed COUNT=150000
```
- **Automatically truncates** old data
- Seeds fresh data
- Ready for next experiment

## When Tables Are Cleaned

| Action | What Happens |
|--------|--------------|
| `make seed` | **TRUNCATE** - All data removed, fresh start |
| `make experiment` | **No cleanup** - Works with existing data |
| `make clean` | **Full teardown** - Destroys entire database |
| `make migrate` | **No cleanup** - Creates tables if missing |

## The `make clean` Nuclear Option

```bash
make clean
```

This does a **full teardown**:
- Destroys Terraform infrastructure
- Removes Docker volumes
- Deletes output files
- **You must run `make infra` and `make migrate` again after this**

## Typical Experiment Workflow

```bash
# Setup (once)
make infra AUTOVACUUM=aggressive
make migrate

# Run experiments (repeat as needed)
make seed COUNT=150000          # Clean + seed
make experiment PRESET=optimal-vacuum

make seed COUNT=150000          # Clean + seed again
make experiment PRESET=production-simulation

# Compare results...
```

## Why TRUNCATE in Seed Script?

The seed script **always truncates first** to ensure:
1. ✅ Clean baseline - No leftover data from previous runs
2. ✅ Consistent results - Same starting point every time
3. ✅ Reset sequences - IDs start from 1
4. ✅ No bloat - Table is compact before experiment

## What If I Want to Keep Existing Data?

Currently, the seed script **always** truncates. If you want to add data without cleaning:

```python
# You'd need to modify seed_data.py to skip truncate
# Or use direct SQL:
psql $DB_CONNECTION_STRING -c "INSERT INTO documents_jsonb ..."
```

But for experiments, you **want** the clean state!

## Bottom Line

**You don't need to manually clean before seeding.** The seed script does it automatically with `TRUNCATE TABLE`. Just run:

```bash
make seed COUNT=150000
```

And you'll get a fresh, clean table ready for experiments!
