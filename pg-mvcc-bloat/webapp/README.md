# PostgreSQL MVCC Visualizer Web App

Real-time visualization of PostgreSQL MVCC bloat behavior, built with React, D3.js, and Flask.

## Features

- **Historical Data View**: Browse past experiment runs and visualize metrics
- **Live Monitoring**: Real-time observation of dead tuple accumulation and storage growth
- **Interactive Charts**: 
  - Storage growth over time (table, TOAST, indexes)
  - Dead tuple accumulation (live vs dead)
  - HOT update ratio tracking
  - Buffer cache hit ratio monitoring
- **Dark Mode UI**: Modern, GitHub-inspired interface

## Architecture

```
┌─────────────────┐
│   React + Vite  │  (Port 3000)
│   Frontend      │
└────────┬────────┘
         │ HTTP API
         │
┌────────▼────────┐
│  Flask Server   │  (Port 5000)
│  API Backend    │
└────────┬────────┘
         │
    ┌────▼─────┬──────────────┐
    │          │              │
┌───▼───┐  ┌──▼───┐  ┌──────▼─────┐
│ CSV   │  │ Live │  │ PostgreSQL │
│ Files │  │ Poll │  │ Database   │
└───────┘  └──────┘  └────────────┘
```

## Quick Start

### Prerequisites

- Node.js 18+ and npm
- Python 3.9+
- Running PostgreSQL instance (from main experiment setup)

### 1. Install Dependencies

```bash
# Backend
cd api
pip install -r requirements.txt

# Frontend
cd webapp
npm install
```

### 2. Start Backend API

```bash
cd api
python server.py
```

The API will start on http://localhost:5000

### 3. Start Frontend Development Server

```bash
cd webapp
npm run dev
```

The app will start on http://localhost:3000

### 4. Run an Experiment

In another terminal, run an experiment to generate data:

```bash
cd ..  # Back to project root
make experiment PRESET=bloat-demo
```

Then refresh the web app to see the new experiment data.

## Usage

### Historical Data View

1. Click "Historical Data" tab
2. Select an experiment from the list
3. View interactive charts showing:
   - Storage growth trajectory
   - Dead tuple accumulation patterns
   - HOT update efficiency
   - Buffer cache performance

### Live Monitoring

1. Ensure PostgreSQL is running with data seeded
2. Click "Live View" tab
3. Start an experiment: `make experiment PRESET=bloat-demo`
4. Watch real-time metrics update every 5 seconds

## API Endpoints

### `GET /api/experiments`
Returns list of all available experiment runs.

**Response:**
```json
[
  {
    "id": "bloat-demo_20260125_143022",
    "preset": "bloat-demo",
    "timestamp": "20260125_143022",
    "samples": 60,
    "duration": 300
  }
]
```

### `GET /api/metrics/<run_id>`
Returns all metrics for a specific experiment run.

**Response:**
```json
[
  {
    "timestamp": "2026-01-25T14:30:22",
    "elapsed_seconds": 0,
    "n_live_tup": 100000,
    "n_dead_tup": 0,
    "n_tup_upd": 0,
    "n_tup_hot_upd": 0,
    "table_size_bytes": 8077312,
    "toast_size_bytes": 411041792,
    "indexes_size_bytes": 223805440,
    "total_size_bytes": 636616704,
    "heap_blks_read": 10234,
    "heap_blks_hit": 28765
  }
]
```

### `GET /api/metrics/live`
Returns current metrics from the database.

**Response:** Same format as individual metric object above.

## Development

### Frontend Structure

```
webapp/
├── src/
│   ├── components/
│   │   ├── ExperimentList.jsx    # Experiment selector
│   │   ├── StorageChart.jsx      # Storage growth chart
│   │   ├── DeadTupleChart.jsx    # Dead tuples visualization
│   │   ├── HOTUpdateChart.jsx    # HOT update ratio
│   │   ├── MetricsChart.jsx      # Buffer cache metrics
│   │   └── LiveView.jsx          # Live monitoring view
│   ├── hooks/
│   │   └── useMetrics.js         # Metrics fetching hook
│   ├── App.jsx                    # Main app component
│   └── main.jsx                   # Entry point
├── package.json
└── vite.config.js
```

### Backend Structure

```
api/
├── server.py           # Flask API server
├── utils.py           # Utility functions
└── requirements.txt   # Python dependencies
```

## Building for Production

### Frontend

```bash
cd webapp
npm run build
```

This creates an optimized production build in `webapp/dist/`.

### Deployment

For production deployment:

1. Build the frontend: `npm run build`
2. Serve the static files with a production server (nginx, Apache)
3. Run the Flask API with a production WSGI server (gunicorn):
   ```bash
   pip install gunicorn
   gunicorn -w 4 -b 0.0.0.0:5000 api.server:app
   ```

## Configuration

### Environment Variables

**Backend (api/server.py):**
- `DB_HOST`: PostgreSQL host (default: localhost)
- `DB_PORT`: PostgreSQL port (default: 5433)
- `DB_NAME`: Database name (default: mvcc_experiment)
- `DB_USER`: Database user (default: postgres)
- `DB_PASSWORD`: Database password (default: postgres)

**Frontend (webapp/vite.config.js):**
- API proxy configured to forward `/api` requests to `http://localhost:5000`

## Customization

### Adding New Charts

1. Create a new component in `webapp/src/components/`
2. Use Recharts or D3.js for visualization
3. Import and add to `App.jsx`

### Adding New Metrics

1. Update the SQL query in `api/server.py` to include new columns
2. Update the CSV parsing to handle new fields
3. Create or update chart components to display new metrics

## Troubleshooting

### "No experiments found"
- Ensure you've run at least one experiment
- Check that CSV files exist in `output/metrics/`
- Verify the API can read from the output directory

### "Connection Error" in Live View
- Ensure PostgreSQL is running
- Verify database connection settings
- Check that the Flask API is running
- Confirm the database has been seeded with data

### Charts not displaying
- Check browser console for errors
- Verify metrics data has numeric values
- Ensure CSV files have the expected column names

## License

MIT
