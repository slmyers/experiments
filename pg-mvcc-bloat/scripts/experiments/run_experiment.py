"""
Main experiment runner.

Orchestrates the complete experiment lifecycle:
1. Capture baseline metrics and plans
2. Start metrics collector
3. Run workload (readers + writers)
4. Capture final metrics and plans
5. Export all data
"""
import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

# Add scripts directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from common import (
    DatabaseConfig,
    get_connection,
    get_cursor,
    OUTPUT_DIR,
    METRICS_DIR,
    PLANS_DIR,
    get_run_id,
    get_poll_interval,
)
from experiments.presets import get_preset, list_presets, ExperimentPreset
from metrics.snapshot import (
    capture_snapshot,
    capture_all_tables_snapshot,
    save_snapshot_to_db,
    reset_stats,
)
from metrics.collector import MetricsCollector
from workload.orchestrator import Orchestrator, WorkloadConfig


class ExperimentRunner:
    """
    Runs a complete experiment from preset configuration.
    """
    
    def __init__(
        self,
        preset: ExperimentPreset,
        db_config: DatabaseConfig,
        run_id: Optional[str] = None,
        poll_interval: Optional[float] = None,
    ):
        self.preset = preset
        self.db_config = db_config
        self.run_id = run_id or get_run_id(preset.name)
        self.poll_interval = poll_interval or get_poll_interval(preset.duration_seconds)
        
        # Setup output directories
        self.output_dir = OUTPUT_DIR / self.run_id
        self.metrics_dir = METRICS_DIR / self.run_id
        self.plans_dir = PLANS_DIR / self.run_id
        
        for d in [self.output_dir, self.metrics_dir, self.plans_dir]:
            d.mkdir(parents=True, exist_ok=True)
        
        self.metrics_collector: Optional[MetricsCollector] = None
        self.orchestrator: Optional[Orchestrator] = None
    
    def _configure_autovacuum(self) -> None:
        """Configure autovacuum settings based on preset."""
        mode = self.preset.autovacuum_mode
        table = self.preset.table
        
        print(f"\n--- Configuring Autovacuum ({mode}) ---")
        
        with get_connection(self.db_config) as conn:
            conn.autocommit = True
            with conn.cursor() as cursor:
                if mode == "disabled":
                    # Disable autovacuum for this specific table
                    cursor.execute(f"""
                        ALTER TABLE {table} SET (autovacuum_enabled = false)
                    """)
                    print(f"  Disabled autovacuum on table {table}")
                    
                elif mode == "aggressive":
                    # Enable with aggressive settings
                    cursor.execute(f"""
                        ALTER TABLE {table} SET (
                            autovacuum_enabled = true,
                            autovacuum_vacuum_scale_factor = 0.01,
                            autovacuum_analyze_scale_factor = 0.005,
                            autovacuum_vacuum_threshold = 25,
                            autovacuum_vacuum_cost_delay = 2
                        )
                    """)
                    print(f"  Configured aggressive autovacuum on table {table}")
                    print(f"    vacuum_scale_factor: 0.01 (triggers at 1% dead tuples)")
                    print(f"    vacuum_threshold: 25 tuples")
                    
                elif mode == "default":
                    # Reset to default PostgreSQL settings
                    cursor.execute(f"""
                        ALTER TABLE {table} RESET (
                            autovacuum_enabled,
                            autovacuum_vacuum_scale_factor,
                            autovacuum_analyze_scale_factor,
                            autovacuum_vacuum_threshold,
                            autovacuum_vacuum_cost_delay
                        )
                    """)
                    print(f"  Reset to default autovacuum settings on table {table}")
                    print(f"    vacuum_scale_factor: 0.2 (triggers at 20% dead tuples)")
                    print(f"    vacuum_threshold: 50 tuples")
                
                # Verify autovacuum is enabled globally
                cursor.execute("SHOW autovacuum")
                global_autovacuum = cursor.fetchone()[0]
                print(f"  Global autovacuum setting: {global_autovacuum}")
                
                if mode != "disabled" and global_autovacuum == "off":
                    print(f"  WARNING: Global autovacuum is OFF. Table-level settings will have no effect!")
                    print(f"  To enable globally, restart infrastructure with: make infra AUTOVACUUM=default")
    
    def _record_experiment_start(self) -> None:
        """Record experiment metadata in database."""
        with get_cursor(self.db_config) as cursor:
            cursor.execute("""
                INSERT INTO experiment_runs (
                    run_id, preset_name, duration_seconds, poll_interval_seconds,
                    autovacuum_mode, read_workers, write_workers, config, status
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'starting')
                ON CONFLICT (run_id) DO UPDATE SET 
                    status = 'starting',
                    started_at = NOW()
            """, (
                self.run_id,
                self.preset.name,
                self.preset.duration_seconds,
                self.poll_interval,
                self.preset.autovacuum_mode,
                self.preset.read_workers,
                self.preset.write_workers,
                json.dumps(self.preset.to_dict()),
            ))
    
    def _update_experiment_status(self, status: str) -> None:
        """Update experiment status."""
        with get_cursor(self.db_config) as cursor:
            cursor.execute("""
                UPDATE experiment_runs 
                SET status = %s, ended_at = CASE WHEN %s IN ('completed', 'failed') THEN NOW() ELSE ended_at END
                WHERE run_id = %s
            """, (status, status, self.run_id))
    
    def _run_vacuum_full(self) -> float:
        """Run VACUUM FULL on target table and return elapsed time."""
        print(f"Running VACUUM FULL on {self.preset.table}...")
        with get_connection(self.db_config) as conn:
            conn.autocommit = True
            start = time.time()
            with conn.cursor() as cursor:
                cursor.execute(f"VACUUM FULL {self.preset.table}")
            elapsed = time.time() - start
        print(f"VACUUM FULL completed in {elapsed:.1f}s")
        return elapsed
    
    def _capture_baseline(self) -> None:
        """Capture baseline metrics and plans."""
        print("\n--- Capturing Baseline ---")
        
        # Reset statistics for clean measurement
        reset_stats(self.db_config)
        
        # Capture baseline snapshots for all tables
        snapshots = capture_all_tables_snapshot(
            config=self.db_config,
            snapshot_type="baseline",
            include_pgstattuple=True,
        )
        
        for snapshot in snapshots:
            save_snapshot_to_db(self.db_config, self.run_id, snapshot)
            print(f"  {snapshot.table_name}: {snapshot.n_live_tup:,} rows, "
                  f"{snapshot.total_size_bytes:,} bytes")
    
    def _capture_final(self) -> None:
        """Capture final metrics and plans."""
        print("\n--- Capturing Final Metrics ---")
        
        snapshots = capture_all_tables_snapshot(
            config=self.db_config,
            snapshot_type="final",
            include_pgstattuple=True,
        )
        
        for snapshot in snapshots:
            save_snapshot_to_db(self.db_config, self.run_id, snapshot)
            print(f"  {snapshot.table_name}: "
                  f"live={snapshot.n_live_tup:,}, "
                  f"dead={snapshot.n_dead_tup:,} ({snapshot.dead_tuple_ratio:.1%}), "
                  f"size={snapshot.total_size_bytes:,}")
    
    def _export_metrics_csv(self) -> Path:
        """Export metrics from database to CSV."""
        import csv
        
        csv_path = self.metrics_dir / "metrics_export.csv"
        
        with get_connection(self.db_config) as conn:
            with conn.cursor() as cursor:
                cursor.execute("""
                    SELECT * FROM metrics_snapshots 
                    WHERE run_id = %s 
                    ORDER BY captured_at
                """, (self.run_id,))
                
                columns = [desc[0] for desc in cursor.description]
                rows = cursor.fetchall()
        
        with open(csv_path, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(columns)
            writer.writerows(rows)
        
        print(f"Exported {len(rows)} metrics rows to {csv_path}")
        return csv_path
    
    def _save_experiment_summary(self) -> Path:
        """Save experiment summary JSON."""
        summary = {
            "run_id": self.run_id,
            "preset": self.preset.to_dict(),
            "poll_interval": self.poll_interval,
            "started_at": datetime.now().isoformat(),
            "output_dir": str(self.output_dir),
            "metrics_dir": str(self.metrics_dir),
            "plans_dir": str(self.plans_dir),
        }
        
        summary_path = self.output_dir / "experiment_summary.json"
        with open(summary_path, 'w') as f:
            json.dump(summary, f, indent=2)
        
        return summary_path
    
    def run(self) -> dict:
        """
        Execute the complete experiment.
        
        Returns:
            Dictionary with experiment results and paths to outputs
        """
        print(f"\n{'='*70}")
        print(f"EXPERIMENT: {self.preset.name}")
        print(f"{'='*70}")
        print(f"Run ID: {self.run_id}")
        print(f"Description: {self.preset.description}")
        print(f"Table: {self.preset.table}")
        print(f"Update pattern: {self.preset.update_pattern}")
        print(f"Workers: {self.preset.read_workers} readers, {self.preset.write_workers} writers")
        print(f"Duration: {self.preset.duration_seconds}s")
        print(f"Poll interval: {self.poll_interval}s")
        print(f"Autovacuum: {self.preset.autovacuum_mode}")
        print(f"{'='*70}\n")
        
        results = {
            "run_id": self.run_id,
            "preset": self.preset.name,
            "success": False,
        }
        
        try:
            self._record_experiment_start()
            self._save_experiment_summary()
            
            # Configure autovacuum based on preset
            self._configure_autovacuum()
            
            # Handle pre-experiment vacuum if requested
            if self.preset.extra_config.get("run_vacuum_full_before"):
                vacuum_time = self._run_vacuum_full()
                results["vacuum_time_seconds"] = vacuum_time
            
            # Capture baseline
            self._capture_baseline()
            self._update_experiment_status("running")
            
            # Start metrics collector
            self.metrics_collector = MetricsCollector(
                config=self.db_config,
                run_id=self.run_id,
                tables=[self.preset.table],
                poll_interval=self.poll_interval,
                save_to_db=True,
            )
            self.metrics_collector.start()
            
            # Run workload if there are workers
            if self.preset.write_workers > 0 or self.preset.read_workers > 0:
                workload_config = WorkloadConfig(
                    table=self.preset.table,
                    update_pattern=self.preset.update_pattern,
                    duration_seconds=self.preset.duration_seconds,
                    read_workers=self.preset.read_workers,
                    write_workers=self.preset.write_workers,
                    batch_size=self.preset.batch_size,
                    rate_limit=self.preset.rate_limit,
                    plan_capture_interval=self.preset.plan_capture_interval,
                )
                
                self.orchestrator = Orchestrator(
                    config=self.db_config,
                    workload_config=workload_config,
                    run_id=self.run_id,
                )
                
                orchestrator_stats = self.orchestrator.run()
                results["total_updates"] = orchestrator_stats.total_updates
                results["total_queries"] = orchestrator_stats.total_queries
            else:
                # Just wait for duration (e.g., for vacuum-recovery read-only tests)
                print(f"Running for {self.preset.duration_seconds}s (no workload)...")
                time.sleep(self.preset.duration_seconds)
            
            # Stop metrics collector
            self.metrics_collector.stop()
            
            # Capture final metrics
            self._capture_final()
            
            # Export data
            results["metrics_csv"] = str(self._export_metrics_csv())
            results["output_dir"] = str(self.output_dir)
            results["success"] = True
            
            self._update_experiment_status("completed")
            
            print(f"\n{'='*70}")
            print(f"EXPERIMENT COMPLETED: {self.run_id}")
            print(f"{'='*70}")
            print(f"Output directory: {self.output_dir}")
            print(f"Metrics CSV: {results['metrics_csv']}")
            print(f"Plans directory: {self.plans_dir}")
            
        except Exception as e:
            print(f"\nEXPERIMENT FAILED: {e}")
            self._update_experiment_status("failed")
            results["error"] = str(e)
            
            if self.metrics_collector and self.metrics_collector.is_running():
                self.metrics_collector.stop()
            
            raise
        
        return results


def main():
    parser = argparse.ArgumentParser(
        description="Run PostgreSQL MVCC bloat experiment",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Available presets:
""" + "\n".join(f"  {name}: {desc}" for name, desc in list_presets().items())
    )
    
    parser.add_argument(
        "preset",
        nargs="?",
        help="Experiment preset name",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List available presets",
    )
    parser.add_argument(
        "--run-id",
        default=None,
        help="Override run ID",
    )
    parser.add_argument(
        "--duration",
        type=int,
        default=None,
        help="Override duration (seconds)",
    )
    parser.add_argument(
        "--poll-interval",
        type=float,
        default=None,
        help="Override poll interval (seconds)",
    )
    
    args = parser.parse_args()
    
    if args.list:
        print("\nAvailable experiment presets:\n")
        for name, desc in list_presets().items():
            print(f"  {name}")
            print(f"    {desc}\n")
        return
    
    if not args.preset:
        parser.print_help()
        return
    
    # Load preset
    preset = get_preset(args.preset)
    
    # Apply overrides
    if args.duration:
        preset.duration_seconds = args.duration
    
    # Setup database config
    db_config = DatabaseConfig.from_env()
    
    # Create and run experiment
    runner = ExperimentRunner(
        preset=preset,
        db_config=db_config,
        run_id=args.run_id,
        poll_interval=args.poll_interval,
    )
    
    runner.run()


if __name__ == "__main__":
    main()
