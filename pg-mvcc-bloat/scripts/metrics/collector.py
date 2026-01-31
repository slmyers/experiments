"""
Continuous metrics collector for experiment monitoring.

Runs in background thread, polling table statistics at configurable
intervals and exporting to CSV.
"""
import argparse
import csv
import sys
import time
import threading
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any

sys.path.insert(0, str(__file__).rsplit("/", 3)[0])
from common import (
    DatabaseConfig,
    get_connection,
    TABLE_JSONB,
    TABLE_JSONB_FLAGS,
    TABLE_NORMALIZED,
    ALL_TABLES,
    METRICS_DIR,
    get_poll_interval,
    sizeof_fmt,
)
from metrics.snapshot import (
    capture_snapshot,
    capture_table_stats,
    capture_table_sizes,
    capture_io_stats,
    save_snapshot_to_db,
    TableSnapshot,
)


class MetricsCollector:
    """
    Collects metrics continuously during experiment execution.
    
    Runs in a background thread, capturing lightweight snapshots
    at regular intervals and writing to CSV.
    """
    
    CSV_COLUMNS = [
        "timestamp",
        "elapsed_seconds",
        "table_name",
        "n_live_tup",
        "n_dead_tup",
        "dead_tuple_ratio",
        "n_tup_upd",
        "n_tup_hot_upd",
        "hot_update_ratio",
        "table_size_bytes",
        "toast_size_bytes",
        "index_size_bytes",
        "total_size_bytes",
        "heap_blks_read",
        "heap_blks_hit",
        "buffer_hit_ratio",
        "idx_blks_read",
        "idx_blks_hit",
        "toast_blks_read",
        "toast_blks_hit",
    ]
    
    def __init__(
        self,
        config: DatabaseConfig,
        run_id: str,
        tables: List[str] = None,
        poll_interval: float = 5.0,
        save_to_db: bool = True,
    ):
        self.config = config
        self.run_id = run_id
        self.tables = tables or ALL_TABLES
        self.poll_interval = poll_interval
        self.save_to_db = save_to_db
        
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._start_time: Optional[float] = None
        self._snapshots: List[TableSnapshot] = []
        
        # Setup output directory and CSV file
        self.output_dir = METRICS_DIR / run_id
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.csv_file = self.output_dir / "metrics.csv"
        
        # Initialize CSV with headers
        with open(self.csv_file, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=self.CSV_COLUMNS)
            writer.writeheader()
    
    def _capture_lightweight_snapshot(
        self,
        table_name: str,
        elapsed_seconds: float,
    ) -> Dict[str, Any]:
        """
        Capture lightweight metrics (no pgstattuple).
        
        This is called frequently, so we avoid the expensive full table scan.
        """
        with get_connection(self.config) as conn:
            stats = capture_table_stats(conn, table_name)
            sizes = capture_table_sizes(conn, table_name)
            io_stats = capture_io_stats(conn, table_name)
        
        # Calculate derived metrics
        n_live = stats.get("n_live_tup", 0)
        n_dead = stats.get("n_dead_tup", 0)
        total_tup = n_live + n_dead
        dead_ratio = n_dead / total_tup if total_tup > 0 else 0.0
        
        n_upd = stats.get("n_tup_upd", 0)
        n_hot = stats.get("n_tup_hot_upd", 0)
        hot_ratio = n_hot / n_upd if n_upd > 0 else 0.0
        
        heap_read = io_stats.get("heap_blks_read", 0)
        heap_hit = io_stats.get("heap_blks_hit", 0)
        total_heap = heap_read + heap_hit
        buffer_hit_ratio = heap_hit / total_heap if total_heap > 0 else 0.0
        
        return {
            "timestamp": datetime.now().isoformat(),
            "elapsed_seconds": elapsed_seconds,
            "table_name": table_name,
            "n_live_tup": n_live,
            "n_dead_tup": n_dead,
            "dead_tuple_ratio": dead_ratio,
            "n_tup_upd": n_upd,
            "n_tup_hot_upd": n_hot,
            "hot_update_ratio": hot_ratio,
            "table_size_bytes": sizes.get("table_size_bytes", 0),
            "toast_size_bytes": sizes.get("toast_size_bytes", 0),
            "index_size_bytes": sizes.get("index_size_bytes", 0),
            "total_size_bytes": sizes.get("total_size_bytes", 0),
            "heap_blks_read": heap_read,
            "heap_blks_hit": heap_hit,
            "buffer_hit_ratio": buffer_hit_ratio,
            "idx_blks_read": io_stats.get("idx_blks_read", 0),
            "idx_blks_hit": io_stats.get("idx_blks_hit", 0),
            "toast_blks_read": io_stats.get("toast_blks_read", 0),
            "toast_blks_hit": io_stats.get("toast_blks_hit", 0),
        }
    
    def _write_to_csv(self, records: List[Dict[str, Any]]) -> None:
        """Append records to CSV file."""
        with open(self.csv_file, 'a', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=self.CSV_COLUMNS)
            for record in records:
                writer.writerow(record)
    
    def _collection_loop(self) -> None:
        """Main collection loop running in background thread."""
        iteration = 0
        
        while not self._stop_event.is_set():
            elapsed = time.time() - self._start_time
            records = []
            
            for table in self.tables:
                try:
                    record = self._capture_lightweight_snapshot(table, elapsed)
                    records.append(record)
                    
                    # Also save to DB if enabled
                    if self.save_to_db:
                        snapshot = TableSnapshot(
                            table_name=table,
                            snapshot_type="continuous",
                            elapsed_seconds=elapsed,
                            **{k: v for k, v in record.items() 
                               if k not in ["timestamp", "elapsed_seconds", "table_name", 
                                           "dead_tuple_ratio", "hot_update_ratio", "buffer_hit_ratio"]}
                        )
                        self._snapshots.append(snapshot)
                        save_snapshot_to_db(self.config, self.run_id, snapshot)
                        
                except Exception as e:
                    print(f"Warning: Failed to capture metrics for {table}: {e}")
            
            # Write to CSV
            self._write_to_csv(records)
            
            # Log progress periodically
            iteration += 1
            if iteration % 10 == 0:
                for record in records:
                    print(f"  [{record['table_name']}] Dead: {record['n_dead_tup']:,} "
                          f"({record['dead_tuple_ratio']:.1%}), "
                          f"Size: {sizeof_fmt(record['total_size_bytes'])}")
            
            # Wait for next interval
            self._stop_event.wait(self.poll_interval)
    
    def start(self) -> None:
        """Start the background collection thread."""
        if self._thread is not None and self._thread.is_alive():
            raise RuntimeError("Collector is already running")
        
        self._start_time = time.time()
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._collection_loop, daemon=True)
        self._thread.start()
        print(f"Metrics collector started (interval: {self.poll_interval}s)")
    
    def stop(self) -> None:
        """Stop the background collection thread."""
        if self._thread is None:
            return
        
        self._stop_event.set()
        self._thread.join(timeout=5.0)
        self._thread = None
        print(f"Metrics collector stopped. CSV saved to: {self.csv_file}")
    
    def is_running(self) -> bool:
        """Check if collector is running."""
        return self._thread is not None and self._thread.is_alive()
    
    @property
    def snapshots(self) -> List[TableSnapshot]:
        """Get all captured snapshots."""
        return self._snapshots.copy()


def main():
    parser = argparse.ArgumentParser(description="Collect metrics continuously")
    parser.add_argument(
        "--run-id",
        required=True,
        help="Experiment run ID",
    )
    parser.add_argument(
        "--tables",
        nargs="+",
        choices=ALL_TABLES,
        default=ALL_TABLES,
        help="Tables to monitor",
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=5.0,
        help="Poll interval in seconds (default: 5)",
    )
    parser.add_argument(
        "--duration",
        type=int,
        default=60,
        help="Duration in seconds (default: 60)",
    )
    parser.add_argument(
        "--no-db",
        action="store_true",
        help="Don't save to database, only CSV",
    )
    
    args = parser.parse_args()
    config = DatabaseConfig.from_env()
    
    collector = MetricsCollector(
        config=config,
        run_id=args.run_id,
        tables=args.tables,
        poll_interval=args.interval,
        save_to_db=not args.no_db,
    )
    
    print(f"Starting metrics collection for {args.duration}s")
    print(f"Tables: {', '.join(args.tables)}")
    print(f"Interval: {args.interval}s")
    print(f"Output: {collector.csv_file}")
    
    collector.start()
    
    try:
        time.sleep(args.duration)
    except KeyboardInterrupt:
        print("\nStopping...")
    finally:
        collector.stop()
    
    print(f"\nCollected {len(collector.snapshots)} snapshots")


if __name__ == "__main__":
    main()
