-- Migration 001: Create experiment tables
-- PostgreSQL MVCC Bloat Experiment Schema

-- =============================================================================
-- Table 1: documents_jsonb (TOAST-heavy, worst case for bloat)
-- =============================================================================
-- Large JSONB column that will be TOASTed (~1KB per document)
-- Updates to this column create new TOAST entries

CREATE TABLE IF NOT EXISTS documents_jsonb (
    id SERIAL PRIMARY KEY,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    data JSONB NOT NULL
);

-- Index on JSONB for query benchmarks
CREATE INDEX IF NOT EXISTS idx_documents_jsonb_data_gin 
    ON documents_jsonb USING GIN (data);

-- Index for status queries within JSONB
CREATE INDEX IF NOT EXISTS idx_documents_jsonb_status 
    ON documents_jsonb ((data->>'status'));

COMMENT ON TABLE documents_jsonb IS 'TOAST-heavy table for worst-case MVCC bloat demonstration';

-- =============================================================================
-- Table 2: documents_jsonb_with_flags (TOAST reuse pattern)
-- =============================================================================
-- Same JSONB column, but with separate scalar columns for frequent updates
-- Updates to scalar columns can reuse existing TOAST pointers

CREATE TABLE IF NOT EXISTS documents_jsonb_with_flags (
    id SERIAL PRIMARY KEY,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- Scalar columns for frequent updates (no TOAST involved)
    status VARCHAR(50) DEFAULT 'pending',
    priority INTEGER DEFAULT 0,
    process_count INTEGER DEFAULT 0,
    last_processed_at TIMESTAMP WITH TIME ZONE,
    
    -- Large JSONB column (TOASTed, but updated less frequently)
    data JSONB NOT NULL
);

-- Indexes for scalar columns
CREATE INDEX IF NOT EXISTS idx_documents_flags_status 
    ON documents_jsonb_with_flags (status);
CREATE INDEX IF NOT EXISTS idx_documents_flags_priority 
    ON documents_jsonb_with_flags (priority);

-- GIN index on JSONB
CREATE INDEX IF NOT EXISTS idx_documents_flags_data_gin 
    ON documents_jsonb_with_flags USING GIN (data);

COMMENT ON TABLE documents_jsonb_with_flags IS 'Table demonstrating TOAST pointer reuse when updating scalar columns';

-- =============================================================================
-- Table 3: documents_normalized (Optimized schema)
-- =============================================================================
-- JSONB unpacked into typed columns for efficient updates
-- Small, targeted updates with aggressive autovacuum = stable performance

CREATE TABLE IF NOT EXISTS documents_normalized (
    id SERIAL PRIMARY KEY,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- Unpacked fields from JSONB
    title VARCHAR(255) NOT NULL,
    body TEXT,
    status VARCHAR(50) DEFAULT 'pending',
    priority INTEGER DEFAULT 0,
    author_name VARCHAR(255),
    author_email VARCHAR(255),
    category VARCHAR(100),
    tags TEXT[], -- Array instead of JSONB array
    view_count INTEGER DEFAULT 0,
    
    -- Only small metadata as JSONB (won't be TOASTed)
    metadata JSONB DEFAULT '{}'::jsonb
);

-- Indexes for common query patterns
CREATE INDEX IF NOT EXISTS idx_documents_norm_status 
    ON documents_normalized (status);
CREATE INDEX IF NOT EXISTS idx_documents_norm_priority 
    ON documents_normalized (priority);
CREATE INDEX IF NOT EXISTS idx_documents_norm_category 
    ON documents_normalized (category);
CREATE INDEX IF NOT EXISTS idx_documents_norm_tags 
    ON documents_normalized USING GIN (tags);
CREATE INDEX IF NOT EXISTS idx_documents_norm_author_email 
    ON documents_normalized (author_email);

COMMENT ON TABLE documents_normalized IS 'Optimized normalized schema for comparison with JSONB approaches';

-- =============================================================================
-- Experiment tracking tables
-- =============================================================================

CREATE TABLE IF NOT EXISTS experiment_runs (
    id SERIAL PRIMARY KEY,
    run_id VARCHAR(100) UNIQUE NOT NULL,
    preset_name VARCHAR(100) NOT NULL,
    started_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    ended_at TIMESTAMP WITH TIME ZONE,
    duration_seconds INTEGER,
    poll_interval_seconds NUMERIC,
    autovacuum_mode VARCHAR(50),
    read_workers INTEGER,
    write_workers INTEGER,
    config JSONB,
    status VARCHAR(50) DEFAULT 'running'
);

CREATE INDEX IF NOT EXISTS idx_experiment_runs_preset 
    ON experiment_runs (preset_name);
CREATE INDEX IF NOT EXISTS idx_experiment_runs_started 
    ON experiment_runs (started_at);

COMMENT ON TABLE experiment_runs IS 'Metadata for each experiment run';
