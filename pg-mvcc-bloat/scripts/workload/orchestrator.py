"""
Orchestrator for managing concurrent reader and writer workloads.

Coordinates multiple reader and writer processes, manages experiment
lifecycle, and aggregates results.
"""
import argparse
import json
import sys
import time
import threading
from datetime import datetime
from dataclasses import dataclass, field, asdict
from typing import Optional, List, Dict, Any
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

sys.path.insert(0, str(__file__).rsplit("/", 3)[0])
from common import (
    DatabaseConfig,
    get_connection,
    get_cursor,
    TABLE_JSONB,
    TABLE_JSONB_FLAGS,
    TABLE_NORMALIZED,
    OUTPUT_DIR,
    get_run_id,
    get_poll_interval,
)
from workload.writer import Writer, WriterStats
from workload.reader import Reader, ReaderStats


@dataclass
class WorkloadConfig:
    """Configuration for the workload orchestrator."""
    table: str
    update_pattern: str
    duration_seconds: int
    read_workers: int = 1
    write_workers: int = 1
    batch_size: int = 100
    rate_limit: Optional[float] = None
    plan_capture_interval: int = 60
    random_seed: int = 42
    
    @property
    def read_write_ratio(self) -> str:
        return f"{self.read_workers}:{self.write_workers}"


@dataclass
class OrchestratorStats:
    """Aggregated statistics from all workers."""
    run_id: str
    config: Dict[str, Any]
    writer_stats: List[Dict[str, Any]] = field(default_factory=list)
    reader_stats: List[Dict[str, Any]] = field(default_factory=list)
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    total_updates: int = 0
    total_queries: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "run_id": self.run_id,
            "config": self.config,
            "writer_stats": self.writer_stats,
            "reader_stats": self.reader_stats,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "total_updates": self.total_updates,
            "total_queries": self.total_queries,
        }


class Orchestrator:
    """
    Coordinates concurrent reader and writer workloads.
    """
    
    def __init__(
        self,
        config: DatabaseConfig,
        workload_config: WorkloadConfig,
        run_id: str,
    ):
        self.db_config = config
        self.workload_config = workload_config
        self.run_id = run_id
        self.stop_event = threading.Event()
        self.stats = OrchestratorStats(
            run_id=run_id,
            config=asdict(workload_config),
        )
    
    def _run_writer(self, worker_id: int) -> WriterStats:
        """Run a single writer worker."""
        writer = Writer(
            config=self.db_config,
            table=self.workload_config.table,
            update_pattern=self.workload_config.update_pattern,
            batch_size=self.workload_config.batch_size,
            rate_limit=self.workload_config.rate_limit,
            random_seed=self.workload_config.random_seed + worker_id,
        )
        
        print(f"  Writer {worker_id} started")
        stats = writer.run(
            duration_seconds=self.workload_config.duration_seconds,
            stop_event=self.stop_event,
        )
        print(f"  Writer {worker_id} completed: {stats.updates_successful:,} updates")
        return stats
    
    def _run_reader(self, worker_id: int) -> ReaderStats:
        """Run a single reader worker."""
        reader = Reader(
            config=self.db_config,
            table=self.workload_config.table,
            run_id=f"{self.run_id}_reader{worker_id}",
            plan_capture_interval=self.workload_config.plan_capture_interval,
        )
        
        # Only capture baseline/final plans for first reader
        if worker_id == 0:
            print(f"  Reader {worker_id} capturing baseline plans...")
            reader.capture_baseline_plans()
        
        print(f"  Reader {worker_id} started")
        stats = reader.run(
            duration_seconds=self.workload_config.duration_seconds,
            stop_event=self.stop_event,
        )
        
        if worker_id == 0:
            print(f"  Reader {worker_id} capturing final plans...")
            reader.capture_final_plans()
        
        print(f"  Reader {worker_id} completed: {stats.queries_executed:,} queries")
        return stats
    
    def _record_experiment_run(self) -> None:
        """Record experiment run in database."""
        with get_cursor(self.db_config) as cursor:
            cursor.execute("""
                INSERT INTO experiment_runs (
                    run_id, preset_name, duration_seconds, 
                    read_workers, write_workers, config, status
                ) VALUES (%s, %s, %s, %s, %s, %s, 'running')
                ON CONFLICT (run_id) DO UPDATE SET status = 'running'
            """, (
                self.run_id,
                self.workload_config.update_pattern,
                self.workload_config.duration_seconds,
                self.workload_config.read_workers,
                self.workload_config.write_workers,
                json.dumps(asdict(self.workload_config)),
            ))
    
    def _update_experiment_status(self, status: str) -> None:
        """Update experiment run status."""
        with get_cursor(self.db_config) as cursor:
            cursor.execute("""
                UPDATE experiment_runs 
                SET status = %s, ended_at = NOW()
                WHERE run_id = %s
            """, (status, self.run_id))
    
    def run(self) -> OrchestratorStats:
        """
        Run the coordinated workload.
        
        Spawns reader and writer workers in parallel and collects results.
        """
        self.stats.start_time = datetime.now().isoformat()
        self._record_experiment_run()
        
        print(f"\n{'='*60}")
        print(f"Starting workload: {self.run_id}")
        print(f"Table: {self.workload_config.table}")
        print(f"Pattern: {self.workload_config.update_pattern}")
        print(f"Duration: {self.workload_config.duration_seconds}s")
        print(f"Workers: {self.workload_config.read_workers} readers, {self.workload_config.write_workers} writers")
        print(f"{'='*60}\n")
        
        futures = []
        
        with ThreadPoolExecutor(
            max_workers=self.workload_config.read_workers + self.workload_config.write_workers
        ) as executor:
            # Start writers
            for i in range(self.workload_config.write_workers):
                futures.append(("writer", i, executor.submit(self._run_writer, i)))
            
            # Start readers
            for i in range(self.workload_config.read_workers):
                futures.append(("reader", i, executor.submit(self._run_reader, i)))
            
            # Collect results
            for worker_type, worker_id, future in futures:
                try:
                    stats = future.result()
                    if worker_type == "writer":
                        self.stats.writer_stats.append(asdict(stats))
                        self.stats.total_updates += stats.updates_successful
                    else:
                        # Convert reader stats, handling the results list specially
                        reader_dict = {
                            "queries_executed": stats.queries_executed,
                            "total_time_ms": stats.total_time_ms,
                            "avg_time_ms": stats.avg_time_ms,
                            "p50_ms": stats.get_percentile(50),
                            "p95_ms": stats.get_percentile(95),
                            "p99_ms": stats.get_percentile(99),
                            "plans_captured": stats.plans_captured,
                            "start_time": stats.start_time,
                            "end_time": stats.end_time,
                        }
                        self.stats.reader_stats.append(reader_dict)
                        self.stats.total_queries += stats.queries_executed
                except Exception as e:
                    print(f"Worker {worker_type}_{worker_id} failed: {e}")
        
        self.stats.end_time = datetime.now().isoformat()
        self._update_experiment_status("completed")
        
        # Save stats to file
        stats_file = OUTPUT_DIR / f"{self.run_id}_stats.json"
        with open(stats_file, 'w') as f:
            json.dump(self.stats.to_dict(), f, indent=2, default=str)
        
        print(f"\n{'='*60}")
        print(f"Workload completed: {self.run_id}")
        print(f"Total updates: {self.stats.total_updates:,}")
        print(f"Total queries: {self.stats.total_queries:,}")
        print(f"Stats saved to: {stats_file}")
        print(f"{'='*60}\n")
        
        return self.stats
    
    def stop(self) -> None:
        """Signal all workers to stop."""
        self.stop_event.set()


def main():
    parser = argparse.ArgumentParser(description="Orchestrate concurrent workload")
    parser.add_argument(
        "--table",
        choices=[TABLE_JSONB, TABLE_JSONB_FLAGS, TABLE_NORMALIZED],
        required=True,
        help="Target table",
    )
    parser.add_argument(
        "--pattern",
        choices=["jsonb_mutation", "flag_only", "normalized"],
        required=True,
        help="Update pattern",
    )
    parser.add_argument(
        "--duration",
        type=int,
        default=60,
        help="Duration in seconds (default: 60)",
    )
    parser.add_argument(
        "--read-workers",
        type=int,
        default=1,
        help="Number of reader workers (default: 1)",
    )
    parser.add_argument(
        "--write-workers",
        type=int,
        default=1,
        help="Number of writer workers (default: 1)",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=100,
        help="Updates per batch (default: 100)",
    )
    parser.add_argument(
        "--rate-limit",
        type=float,
        default=None,
        help="Max updates per second per writer (default: unlimited)",
    )
    parser.add_argument(
        "--plan-interval",
        type=int,
        default=60,
        help="Seconds between plan captures (default: 60)",
    )
    parser.add_argument(
        "--run-id",
        default=None,
        help="Override run ID (default: auto-generated)",
    )
    
    args = parser.parse_args()
    db_config = DatabaseConfig.from_env()
    
    workload_config = WorkloadConfig(
        table=args.table,
        update_pattern=args.pattern,
        duration_seconds=args.duration,
        read_workers=args.read_workers,
        write_workers=args.write_workers,
        batch_size=args.batch_size,
        rate_limit=args.rate_limit,
        plan_capture_interval=args.plan_interval,
    )
    
    run_id = args.run_id or get_run_id(args.pattern)
    
    orchestrator = Orchestrator(
        config=db_config,
        workload_config=workload_config,
        run_id=run_id,
    )
    
    try:
        orchestrator.run()
    except KeyboardInterrupt:
        print("\nStopping workload...")
        orchestrator.stop()


if __name__ == "__main__":
    main()
