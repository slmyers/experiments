# PostgreSQL MVCC Visualizer - Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           Web Browser                                    │
│                     http://localhost:3000                                │
│                                                                          │
│  ┌──────────────────┐                    ┌──────────────────┐          │
│  │  Historical View │                    │    Live View     │          │
│  │                  │                    │                  │          │
│  │ • Select Run     │                    │ • Current Stats  │          │
│  │ • View Charts    │                    │ • Auto-refresh   │          │
│  │ • Compare Runs   │                    │ • Status Alerts  │          │
│  └──────────────────┘                    └──────────────────┘          │
└─────────────────────────────┬───────────────────────────────────────────┘
                              │
                              │ HTTP Requests
                              │ JSON Responses
                              ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                     React Frontend (Port 3000)                           │
│                           Vite Dev Server                                │
│                                                                          │
│  Components/          Hooks/              Utils/                        │
│  ├─ ExperimentList   ├─ useMetrics       ├─ formatSize                 │
│  ├─ StorageChart     └─ usePolling       └─ parseCSV                   │
│  ├─ DeadTupleChart                                                      │
│  ├─ HOTUpdateChart                                                      │
│  ├─ MetricsChart                                                        │
│  └─ LiveView                                                            │
│                                                                          │
│  Libraries: Recharts (D3.js), Axios, React 18                          │
└─────────────────────────────┬───────────────────────────────────────────┘
                              │
                              │ Proxy: /api/* → localhost:5000
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                    Flask API Backend (Port 5000)                         │
│                                                                          │
│  Endpoints:                                                             │
│  ├─ GET /api/experiments        → List all runs                        │
│  ├─ GET /api/metrics/<run_id>   → Historical metrics                   │
│  └─ GET /api/metrics/live       → Current database stats               │
│                                                                          │
│  Dependencies: Flask, Flask-CORS, psycopg2                             │
└─────────┬─────────────────────────────────────────┬─────────────────────┘
          │                                         │
          │ Read CSV files                         │ SQL Queries
          ▼                                         ▼
┌───────────────────────┐            ┌──────────────────────────────────┐
│   File System         │            │   PostgreSQL Database            │
│   output/metrics/     │            │   localhost:5433                 │
│                       │            │                                  │
│  <run_id>_metrics.csv │            │  Tables:                        │
│  • timestamp          │            │  ├─ documents_jsonb             │
│  • elapsed_seconds    │            │  ├─ documents_jsonb_with_flags  │
│  • n_live_tup         │            │  └─ documents_normalized        │
│  • n_dead_tup         │            │                                  │
│  • table_size_bytes   │            │  System Views:                  │
│  • toast_size_bytes   │            │  ├─ pg_stat_user_tables         │
│  • indexes_size_bytes │            │  └─ pg_statio_user_tables       │
│  • heap_blks_read     │            │                                  │
│  • heap_blks_hit      │            │                                  │
│  • n_tup_hot_upd      │            │                                  │
│  └─ ...               │            │                                  │
└───────────────────────┘            └──────────────────────────────────┘
          ▲                                         ▲
          │                                         │
          │ Write metrics                          │ Write workload
          │                                         │
┌─────────┴─────────────────────────────────────────┴─────────────────────┐
│                     Experiment Orchestrator                              │
│                     (Python Scripts)                                     │
│                                                                          │
│  scripts/                                                               │
│  ├─ experiments/run_experiment.py  → Run preset experiments            │
│  ├─ workload/                                                           │
│  │  ├─ writer.py                   → Update workload                   │
│  │  └─ reader.py                   → Query workload                    │
│  ├─ metrics/                                                            │
│  │  ├─ snapshot.py                 → Take metric snapshots             │
│  │  └─ collector.py                → Continuous collection             │
│  └─ seed/seed_data.py              → Initial data loading              │
│                                                                          │
│  Triggered by: make experiment PRESET=bloat-demo                        │
└──────────────────────────────────────────────────────────────────────────┘

                            Data Flow Legend:
                            ═══════════════
                            User Interaction  →  HTTP Request
                            API Response     ←  JSON Data
                            File I/O         ⇄  CSV Read/Write
                            Database Query   ⇄  SQL Operations
```

## Component Interactions

### Historical Data View Flow
```
1. User selects experiment → ExperimentList component
2. Frontend calls GET /api/experiments
3. Flask reads output/metrics/*.csv files
4. Returns list of experiments with metadata
5. User clicks on experiment
6. Frontend calls GET /api/metrics/<run_id>
7. Flask parses specific CSV file
8. Returns time-series metrics array
9. Charts render with Recharts
```

### Live Monitoring Flow
```
1. User switches to Live View
2. useMetrics hook starts polling
3. Every 5 seconds:
   a. Frontend calls GET /api/metrics/live
   b. Flask queries PostgreSQL:
      - pg_stat_user_tables (tuple counts, updates)
      - pg_statio_user_tables (cache hits/misses)
      - pg_relation_size() (storage sizes)
   c. Returns current snapshot
   d. Frontend appends to time-series
   e. Charts update automatically
4. Meanwhile, experiment runs separately:
   - Writers update documents_jsonb table
   - Readers query the data
   - Metrics collector saves snapshots to CSV
```

## Key Design Decisions

1. **Separation of Concerns**
   - Frontend: Pure presentation and interaction
   - Backend: Data aggregation and database access
   - Experiment: Independent workload generation

2. **Dual Data Sources**
   - CSV files: Historical experiments (fast, no DB dependency)
   - Live queries: Real-time monitoring (current state)

3. **Polling vs WebSocket**
   - Started with HTTP polling (simpler, sufficient for 5s intervals)
   - Can upgrade to WebSocket for sub-second updates

4. **Chart Library Choice**
   - Recharts: Declarative, React-friendly
   - Built on D3.js but easier to use
   - Good performance for time-series data

5. **State Management**
   - React hooks (useState, useEffect)
   - No Redux/Zustand needed for this scope
   - Clean and maintainable
