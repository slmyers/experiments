from flask import Flask, jsonify, send_from_directory
from flask_cors import CORS
import psycopg2
import os
import csv
from pathlib import Path
import json

app = Flask(__name__)
CORS(app)

# Database connection
def get_db_connection():
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        port=os.getenv('DB_PORT', '5433'),
        database=os.getenv('DB_NAME', 'mvcc_experiment'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', 'postgres')
    )

# Get list of experiment runs
@app.route('/api/experiments', methods=['GET'])
def get_experiments():
    output_dir = Path(__file__).parent.parent / 'output' / 'metrics'
    
    if not output_dir.exists():
        return jsonify([])
    
    experiments = []
    for csv_file in output_dir.glob('*_metrics.csv'):
        run_id = csv_file.stem.replace('_metrics', '')
        
        # Parse run info from filename
        parts = run_id.split('_')
        preset = '_'.join(parts[:-2]) if len(parts) >= 3 else run_id
        timestamp = '_'.join(parts[-2:]) if len(parts) >= 3 else ''
        
        # Count samples and get duration
        samples = 0
        duration = 0
        try:
            with open(csv_file, 'r') as f:
                reader = csv.DictReader(f)
                rows = list(reader)
                samples = len(rows)
                if rows:
                    # Get duration from last row, handle empty/invalid values
                    last_elapsed = rows[-1].get('elapsed_seconds', '0')
                    if last_elapsed and last_elapsed.strip():
                        duration = int(float(last_elapsed))
        except Exception as e:
            print(f"Error reading {csv_file}: {e}")
            continue
        
        experiments.append({
            'id': run_id,
            'preset': preset,
            'timestamp': timestamp,
            'samples': samples,
            'duration': duration
        })
    
    # Sort by timestamp descending
    experiments.sort(key=lambda x: x['timestamp'], reverse=True)
    
    return jsonify(experiments)

# Get metrics for a specific run
@app.route('/api/metrics/<run_id>', methods=['GET'])
def get_metrics(run_id):
    csv_file = Path(__file__).parent.parent / 'output' / 'metrics' / f'{run_id}_metrics.csv'
    
    if not csv_file.exists():
        return jsonify({'error': 'Run not found'}), 404
    
    metrics = []
    with open(csv_file, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                # Parse elapsed_seconds, default to 0 if empty
                elapsed = row.get('elapsed_seconds', '0')
                elapsed_seconds = float(elapsed) if elapsed and elapsed.strip() else 0
                
                metric = {
                    'timestamp': row.get('captured_at', ''),
                    'elapsed_seconds': elapsed_seconds,
                    'n_live_tup': int(row.get('n_live_tup', 0) or 0),
                    'n_dead_tup': int(row.get('n_dead_tup', 0) or 0),
                    'n_tup_upd': int(row.get('n_tup_upd', 0) or 0),
                    'n_tup_hot_upd': int(row.get('n_tup_hot_upd', 0) or 0),
                    'table_size_bytes': int(row.get('table_size_bytes', 0) or 0),
                    'toast_size_bytes': int(row.get('toast_size_bytes', 0) or 0),
                    'indexes_size_bytes': int(row.get('index_size_bytes', 0) or 0),
                    'total_size_bytes': int(row.get('total_size_bytes', 0) or 0),
                    'heap_blks_read': int(row.get('heap_blks_read', 0) or 0),
                    'heap_blks_hit': int(row.get('heap_blks_hit', 0) or 0),
                }
                metrics.append(metric)
            except Exception as e:
                print(f"Error parsing row: {e}")
                continue
    
    return jsonify(metrics)

# Get live metrics from database
@app.route('/api/metrics/live', methods=['GET'])
def get_live_metrics():
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Query current stats for documents_jsonb table
        query = """
        SELECT 
            NOW() as timestamp,
            0 as elapsed_seconds,
            n_live_tup,
            n_dead_tup,
            n_tup_upd,
            n_tup_hot_upd,
            pg_relation_size(schemaname || '.' || relname) as table_size_bytes,
            COALESCE(pg_relation_size((SELECT reltoastrelid FROM pg_class WHERE relname = stat.relname)), 0) as toast_size_bytes,
            pg_indexes_size(schemaname || '.' || relname) as indexes_size_bytes,
            pg_total_relation_size(schemaname || '.' || relname) as total_size_bytes,
            heap_blks_read,
            heap_blks_hit
        FROM pg_stat_user_tables stat
        JOIN pg_statio_user_tables statio 
            ON stat.schemaname = statio.schemaname 
            AND stat.relname = statio.relname
        WHERE stat.relname = 'documents_jsonb'
        """
        
        cur.execute(query)
        row = cur.fetchone()
        
        if not row:
            return jsonify({'error': 'No data available'}), 404
        
        metric = {
            'timestamp': row[0].isoformat(),
            'elapsed_seconds': row[1],
            'n_live_tup': row[2],
            'n_dead_tup': row[3],
            'n_tup_upd': row[4],
            'n_tup_hot_upd': row[5],
            'table_size_bytes': row[6],
            'toast_size_bytes': row[7],
            'indexes_size_bytes': row[8],
            'total_size_bytes': row[9],
            'heap_blks_read': row[10],
            'heap_blks_hit': row[11],
        }
        
        cur.close()
        conn.close()
        
        return jsonify(metric)
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=True)
