-- Migration 002: Create metrics snapshot table and helper functions

-- =============================================================================
-- Metrics snapshots table
-- =============================================================================

CREATE TABLE IF NOT EXISTS metrics_snapshots (
    id SERIAL PRIMARY KEY,
    run_id VARCHAR(100) NOT NULL REFERENCES experiment_runs(run_id),
    snapshot_type VARCHAR(50) NOT NULL, -- 'baseline', 'continuous', 'final'
    captured_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    elapsed_seconds NUMERIC,
    
    -- Target table being measured
    table_name VARCHAR(100) NOT NULL,
    
    -- Tuple statistics (from pg_stat_user_tables)
    n_live_tup BIGINT,
    n_dead_tup BIGINT,
    n_tup_ins BIGINT,
    n_tup_upd BIGINT,
    n_tup_del BIGINT,
    n_tup_hot_upd BIGINT,
    
    -- Size metrics
    table_size_bytes BIGINT,
    toast_size_bytes BIGINT,
    index_size_bytes BIGINT,
    total_size_bytes BIGINT,
    
    -- Detailed tuple stats (from pgstattuple)
    tuple_count BIGINT,
    tuple_len BIGINT,
    dead_tuple_count BIGINT,
    dead_tuple_len BIGINT,
    free_space BIGINT,
    free_percent NUMERIC,
    
    -- I/O statistics (from pg_statio_user_tables)
    heap_blks_read BIGINT,
    heap_blks_hit BIGINT,
    idx_blks_read BIGINT,
    idx_blks_hit BIGINT,
    toast_blks_read BIGINT,
    toast_blks_hit BIGINT,
    
    -- Vacuum statistics
    last_vacuum TIMESTAMP WITH TIME ZONE,
    last_autovacuum TIMESTAMP WITH TIME ZONE,
    vacuum_count BIGINT,
    autovacuum_count BIGINT,
    
    -- Query performance (aggregated from reader process)
    avg_query_time_ms NUMERIC,
    p50_query_time_ms NUMERIC,
    p95_query_time_ms NUMERIC,
    p99_query_time_ms NUMERIC,
    queries_executed INTEGER
);

CREATE INDEX IF NOT EXISTS idx_metrics_run_id 
    ON metrics_snapshots (run_id);
CREATE INDEX IF NOT EXISTS idx_metrics_table_name 
    ON metrics_snapshots (table_name);
CREATE INDEX IF NOT EXISTS idx_metrics_captured_at 
    ON metrics_snapshots (captured_at);
CREATE INDEX IF NOT EXISTS idx_metrics_snapshot_type 
    ON metrics_snapshots (snapshot_type);

COMMENT ON TABLE metrics_snapshots IS 'Time-series metrics captured during experiments';

-- =============================================================================
-- Query plan snapshots table
-- =============================================================================

CREATE TABLE IF NOT EXISTS query_plan_snapshots (
    id SERIAL PRIMARY KEY,
    run_id VARCHAR(100) NOT NULL REFERENCES experiment_runs(run_id),
    captured_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    elapsed_seconds NUMERIC,
    snapshot_type VARCHAR(50) NOT NULL, -- 'baseline', 'during', 'final'
    
    -- Query identification
    query_name VARCHAR(100) NOT NULL,
    query_text TEXT NOT NULL,
    
    -- Execution stats
    execution_time_ms NUMERIC,
    rows_returned BIGINT,
    
    -- Buffer stats from EXPLAIN
    shared_blks_hit BIGINT,
    shared_blks_read BIGINT,
    shared_blks_dirtied BIGINT,
    shared_blks_written BIGINT,
    
    -- Plan details
    plan_json JSONB NOT NULL,
    plan_summary TEXT, -- Top-level node type and key metrics
    
    -- Comparison flags
    plan_changed BOOLEAN DEFAULT FALSE,
    previous_plan_id INTEGER REFERENCES query_plan_snapshots(id)
);

CREATE INDEX IF NOT EXISTS idx_plans_run_id 
    ON query_plan_snapshots (run_id);
CREATE INDEX IF NOT EXISTS idx_plans_query_name 
    ON query_plan_snapshots (query_name);
CREATE INDEX IF NOT EXISTS idx_plans_snapshot_type 
    ON query_plan_snapshots (snapshot_type);

COMMENT ON TABLE query_plan_snapshots IS 'Query execution plans captured for plan evolution analysis';

-- =============================================================================
-- Helper function to get table statistics
-- =============================================================================

CREATE OR REPLACE FUNCTION get_table_stats(p_table_name TEXT)
RETURNS TABLE (
    n_live_tup BIGINT,
    n_dead_tup BIGINT,
    n_tup_ins BIGINT,
    n_tup_upd BIGINT,
    n_tup_del BIGINT,
    n_tup_hot_upd BIGINT,
    last_vacuum TIMESTAMP WITH TIME ZONE,
    last_autovacuum TIMESTAMP WITH TIME ZONE,
    vacuum_count BIGINT,
    autovacuum_count BIGINT,
    table_size_bytes BIGINT,
    toast_size_bytes BIGINT,
    index_size_bytes BIGINT,
    total_size_bytes BIGINT
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        s.n_live_tup,
        s.n_dead_tup,
        s.n_tup_ins,
        s.n_tup_upd,
        s.n_tup_del,
        s.n_tup_hot_upd,
        s.last_vacuum,
        s.last_autovacuum,
        s.vacuum_count,
        s.autovacuum_count,
        pg_relation_size(p_table_name::regclass) AS table_size_bytes,
        COALESCE(pg_relation_size(p_table_name::regclass, 'toast'), 0) AS toast_size_bytes,
        pg_indexes_size(p_table_name::regclass) AS index_size_bytes,
        pg_total_relation_size(p_table_name::regclass) AS total_size_bytes
    FROM pg_stat_user_tables s
    WHERE s.relname = p_table_name;
END;
$$ LANGUAGE plpgsql;

-- =============================================================================
-- Helper function to get I/O statistics
-- =============================================================================

CREATE OR REPLACE FUNCTION get_table_io_stats(p_table_name TEXT)
RETURNS TABLE (
    heap_blks_read BIGINT,
    heap_blks_hit BIGINT,
    idx_blks_read BIGINT,
    idx_blks_hit BIGINT,
    toast_blks_read BIGINT,
    toast_blks_hit BIGINT
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        s.heap_blks_read,
        s.heap_blks_hit,
        s.idx_blks_read,
        s.idx_blks_hit,
        s.toast_blks_read,
        s.toast_blks_hit
    FROM pg_statio_user_tables s
    WHERE s.relname = p_table_name;
END;
$$ LANGUAGE plpgsql;

-- =============================================================================
-- Helper function to reset statistics for a clean experiment
-- =============================================================================

CREATE OR REPLACE FUNCTION reset_experiment_stats()
RETURNS VOID AS $$
BEGIN
    -- Reset pg_stat_statements
    PERFORM pg_stat_statements_reset();
    
    -- Reset table statistics
    PERFORM pg_stat_reset();
    
    RAISE NOTICE 'Experiment statistics reset';
END;
$$ LANGUAGE plpgsql;
