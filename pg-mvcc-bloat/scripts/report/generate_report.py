"""
Report generator for experiment results.

Creates Markdown reports with embedded charts showing:
- Dead tuple growth over time
- Table size bloat
- Query latency degradation
- Buffer hit ratio changes
- Plan comparison visualizations
"""
import argparse
import csv
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import pandas as pd
import numpy as np

sys.path.insert(0, str(__file__).rsplit("/", 3)[0])
from common import (
    DatabaseConfig,
    get_connection,
    OUTPUT_DIR,
    METRICS_DIR,
    PLANS_DIR,
    REPORTS_DIR,
    sizeof_fmt,
)


# Configure matplotlib for better looking plots
plt.style.use('seaborn-v0_8-whitegrid')
plt.rcParams['figure.figsize'] = (12, 6)
plt.rcParams['font.size'] = 11
plt.rcParams['axes.titlesize'] = 14
plt.rcParams['axes.labelsize'] = 12


class ReportGenerator:
    """
    Generates Markdown reports with visualizations from experiment data.
    """
    
    def __init__(
        self,
        run_id: str,
        output_dir: Optional[Path] = None,
    ):
        self.run_id = run_id
        self.metrics_dir = METRICS_DIR / run_id
        self.plans_dir = PLANS_DIR / run_id
        self.output_dir = output_dir or (REPORTS_DIR / run_id)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        self.images_dir = self.output_dir / "images"
        self.images_dir.mkdir(exist_ok=True)
        
        # Load data
        self.metrics_df = self._load_metrics()
        self.experiment_config = self._load_experiment_config()
        self.baseline_snapshot = None
        self.final_snapshot = None
    
    def _load_metrics(self) -> pd.DataFrame:
        """Load metrics CSV into DataFrame."""
        csv_path = self.metrics_dir / "metrics.csv"
        if not csv_path.exists():
            # Try export file
            csv_path = self.metrics_dir / "metrics_export.csv"
        
        if not csv_path.exists():
            print(f"Warning: No metrics CSV found at {csv_path}")
            return pd.DataFrame()
        
        df = pd.read_csv(csv_path)
        
        # Parse timestamp if present
        if 'timestamp' in df.columns:
            df['timestamp'] = pd.to_datetime(df['timestamp'])
        if 'captured_at' in df.columns:
            df['timestamp'] = pd.to_datetime(df['captured_at'])
        
        return df
    
    def _load_experiment_config(self) -> Dict[str, Any]:
        """Load experiment configuration."""
        config_path = OUTPUT_DIR / self.run_id / "experiment_summary.json"
        if config_path.exists():
            with open(config_path, 'r') as f:
                return json.load(f)
        
        # Try stats file
        stats_path = OUTPUT_DIR / f"{self.run_id}_stats.json"
        if stats_path.exists():
            with open(stats_path, 'r') as f:
                return json.load(f)
        
        return {}
    
    def _load_snapshots_from_db(self, config: DatabaseConfig) -> None:
        """Load baseline and final snapshots from database."""
        with get_connection(config) as conn:
            with conn.cursor() as cursor:
                # Get baseline
                cursor.execute("""
                    SELECT * FROM metrics_snapshots 
                    WHERE run_id = %s AND snapshot_type = 'baseline'
                    ORDER BY captured_at
                    LIMIT 1
                """, (self.run_id,))
                row = cursor.fetchone()
                if row:
                    columns = [desc[0] for desc in cursor.description]
                    self.baseline_snapshot = dict(zip(columns, row))
                
                # Get final
                cursor.execute("""
                    SELECT * FROM metrics_snapshots 
                    WHERE run_id = %s AND snapshot_type = 'final'
                    ORDER BY captured_at DESC
                    LIMIT 1
                """, (self.run_id,))
                row = cursor.fetchone()
                if row:
                    columns = [desc[0] for desc in cursor.description]
                    self.final_snapshot = dict(zip(columns, row))
    
    def _plot_dead_tuple_growth(self) -> Path:
        """Generate dead tuple growth chart."""
        if self.metrics_df.empty:
            return None
        
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5))
        
        for table_name, group in self.metrics_df.groupby('table_name'):
            # Absolute dead tuples
            ax1.plot(
                group['elapsed_seconds'],
                group['n_dead_tup'],
                label=table_name,
                marker='o',
                markersize=3,
            )
            
            # Dead tuple ratio
            ax2.plot(
                group['elapsed_seconds'],
                group['dead_tuple_ratio'] * 100,
                label=table_name,
                marker='o',
                markersize=3,
            )
        
        ax1.set_xlabel('Time (seconds)')
        ax1.set_ylabel('Dead Tuples')
        ax1.set_title('Dead Tuple Count Over Time')
        ax1.legend()
        ax1.ticklabel_format(style='scientific', axis='y', scilimits=(0, 0))
        
        ax2.set_xlabel('Time (seconds)')
        ax2.set_ylabel('Dead Tuple Ratio (%)')
        ax2.set_title('Dead Tuple Ratio Over Time')
        ax2.legend()
        ax2.set_ylim(0, 100)
        
        plt.tight_layout()
        
        output_path = self.images_dir / "dead_tuple_growth.png"
        plt.savefig(output_path, dpi=150, bbox_inches='tight')
        plt.close()
        
        return output_path
    
    def _plot_table_size_growth(self) -> Path:
        """Generate table size growth chart."""
        if self.metrics_df.empty:
            return None
        
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5))
        
        for table_name, group in self.metrics_df.groupby('table_name'):
            # Convert to MB
            total_mb = group['total_size_bytes'] / (1024 * 1024)
            toast_mb = group['toast_size_bytes'] / (1024 * 1024)
            
            ax1.plot(
                group['elapsed_seconds'],
                total_mb,
                label=f"{table_name} (total)",
                marker='o',
                markersize=3,
            )
            
            ax2.plot(
                group['elapsed_seconds'],
                toast_mb,
                label=f"{table_name}",
                marker='s',
                markersize=3,
            )
        
        ax1.set_xlabel('Time (seconds)')
        ax1.set_ylabel('Size (MB)')
        ax1.set_title('Total Table Size Over Time')
        ax1.legend()
        
        ax2.set_xlabel('Time (seconds)')
        ax2.set_ylabel('Size (MB)')
        ax2.set_title('TOAST Size Over Time')
        ax2.legend()
        
        plt.tight_layout()
        
        output_path = self.images_dir / "table_size_growth.png"
        plt.savefig(output_path, dpi=150, bbox_inches='tight')
        plt.close()
        
        return output_path
    
    def _plot_buffer_hit_ratio(self) -> Path:
        """Generate buffer hit ratio chart."""
        if self.metrics_df.empty or 'buffer_hit_ratio' not in self.metrics_df.columns:
            return None
        
        fig, ax = plt.subplots(figsize=(12, 5))
        
        for table_name, group in self.metrics_df.groupby('table_name'):
            ax.plot(
                group['elapsed_seconds'],
                group['buffer_hit_ratio'] * 100,
                label=table_name,
                marker='o',
                markersize=3,
            )
        
        ax.set_xlabel('Time (seconds)')
        ax.set_ylabel('Buffer Hit Ratio (%)')
        ax.set_title('Buffer Cache Hit Ratio Over Time')
        ax.legend()
        ax.set_ylim(0, 105)
        ax.axhline(y=90, color='g', linestyle='--', alpha=0.5, label='90% target')
        
        plt.tight_layout()
        
        output_path = self.images_dir / "buffer_hit_ratio.png"
        plt.savefig(output_path, dpi=150, bbox_inches='tight')
        plt.close()
        
        return output_path
    
    def _plot_hot_update_ratio(self) -> Path:
        """Generate HOT update ratio chart."""
        if self.metrics_df.empty or 'hot_update_ratio' not in self.metrics_df.columns:
            return None
        
        fig, ax = plt.subplots(figsize=(12, 5))
        
        for table_name, group in self.metrics_df.groupby('table_name'):
            ax.plot(
                group['elapsed_seconds'],
                group['hot_update_ratio'] * 100,
                label=table_name,
                marker='o',
                markersize=3,
            )
        
        ax.set_xlabel('Time (seconds)')
        ax.set_ylabel('HOT Update Ratio (%)')
        ax.set_title('HOT (Heap-Only Tuple) Update Ratio Over Time')
        ax.legend()
        ax.set_ylim(0, 105)
        
        plt.tight_layout()
        
        output_path = self.images_dir / "hot_update_ratio.png"
        plt.savefig(output_path, dpi=150, bbox_inches='tight')
        plt.close()
        
        return output_path
    
    def _plot_updates_over_time(self) -> Path:
        """Generate cumulative updates chart."""
        if self.metrics_df.empty or 'n_tup_upd' not in self.metrics_df.columns:
            return None
        
        fig, ax = plt.subplots(figsize=(12, 5))
        
        for table_name, group in self.metrics_df.groupby('table_name'):
            ax.plot(
                group['elapsed_seconds'],
                group['n_tup_upd'],
                label=table_name,
                marker='o',
                markersize=3,
            )
        
        ax.set_xlabel('Time (seconds)')
        ax.set_ylabel('Cumulative Updates')
        ax.set_title('Total Updates Over Time')
        ax.legend()
        ax.ticklabel_format(style='scientific', axis='y', scilimits=(0, 0))
        
        plt.tight_layout()
        
        output_path = self.images_dir / "updates_over_time.png"
        plt.savefig(output_path, dpi=150, bbox_inches='tight')
        plt.close()
        
        return output_path
    
    def _generate_baseline_vs_final_table(self) -> str:
        """Generate Markdown table comparing baseline and final metrics."""
        if not self.baseline_snapshot or not self.final_snapshot:
            return "*Snapshot data not available*"
        
        b = self.baseline_snapshot
        f = self.final_snapshot
        
        def pct_change(old, new):
            if old == 0:
                return "N/A"
            change = ((new - old) / old) * 100
            sign = "+" if change > 0 else ""
            return f"{sign}{change:.1f}%"
        
        rows = [
            ("Live Tuples", f"{b.get('n_live_tup', 0):,}", f"{f.get('n_live_tup', 0):,}", 
             pct_change(b.get('n_live_tup', 0), f.get('n_live_tup', 0))),
            ("Dead Tuples", f"{b.get('n_dead_tup', 0):,}", f"{f.get('n_dead_tup', 0):,}",
             pct_change(max(1, b.get('n_dead_tup', 0)), f.get('n_dead_tup', 0))),
            ("Total Updates", f"{b.get('n_tup_upd', 0):,}", f"{f.get('n_tup_upd', 0):,}",
             pct_change(max(1, b.get('n_tup_upd', 0)), f.get('n_tup_upd', 0))),
            ("HOT Updates", f"{b.get('n_tup_hot_upd', 0):,}", f"{f.get('n_tup_hot_upd', 0):,}",
             pct_change(max(1, b.get('n_tup_hot_upd', 0)), f.get('n_tup_hot_upd', 0))),
            ("Table Size", sizeof_fmt(b.get('table_size_bytes', 0)), sizeof_fmt(f.get('table_size_bytes', 0)),
             pct_change(b.get('table_size_bytes', 0), f.get('table_size_bytes', 0))),
            ("TOAST Size", sizeof_fmt(b.get('toast_size_bytes', 0)), sizeof_fmt(f.get('toast_size_bytes', 0)),
             pct_change(max(1, b.get('toast_size_bytes', 0)), f.get('toast_size_bytes', 0))),
            ("Total Size", sizeof_fmt(b.get('total_size_bytes', 0)), sizeof_fmt(f.get('total_size_bytes', 0)),
             pct_change(b.get('total_size_bytes', 0), f.get('total_size_bytes', 0))),
        ]
        
        table = "| Metric | Baseline | Final | Change |\n"
        table += "|--------|----------|-------|--------|\n"
        for row in rows:
            table += f"| {row[0]} | {row[1]} | {row[2]} | {row[3]} |\n"
        
        return table
    
    def _get_plan_images(self) -> List[Tuple[str, Path]]:
        """Get list of plan visualization images."""
        visuals_dir = self.plans_dir / "visuals"
        if not visuals_dir.exists():
            return []
        
        images = []
        for img_path in sorted(visuals_dir.glob("*_comparison.png")):
            query_name = img_path.stem.replace("_comparison", "")
            images.append((query_name, img_path))
        
        return images
    
    def generate_report(self, db_config: Optional[DatabaseConfig] = None) -> Path:
        """
        Generate the complete Markdown report.
        
        Returns:
            Path to the generated report file
        """
        # Load snapshots from DB if config provided
        if db_config:
            self._load_snapshots_from_db(db_config)
        
        # Generate all charts
        print("Generating charts...")
        dead_tuple_img = self._plot_dead_tuple_growth()
        table_size_img = self._plot_table_size_growth()
        buffer_hit_img = self._plot_buffer_hit_ratio()
        hot_update_img = self._plot_hot_update_ratio()
        updates_img = self._plot_updates_over_time()
        
        # Get plan images
        plan_images = self._get_plan_images()
        
        # Build report
        print("Generating report...")
        
        preset = self.experiment_config.get('preset', {})
        if isinstance(preset, str):
            preset = {'name': preset}
        
        report = f"""# PostgreSQL MVCC Bloat Experiment Report

**Run ID:** `{self.run_id}`  
**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## Experiment Configuration

| Setting | Value |
|---------|-------|
| Preset | {preset.get('name', 'N/A')} |
| Description | {preset.get('description', 'N/A')} |
| Table | {preset.get('table', 'N/A')} |
| Update Pattern | {preset.get('update_pattern', 'N/A')} |
| Duration | {preset.get('duration_seconds', 'N/A')} seconds |
| Read Workers | {preset.get('read_workers', 'N/A')} |
| Write Workers | {preset.get('write_workers', 'N/A')} |
| Autovacuum | {preset.get('autovacuum_mode', 'N/A')} |

## Summary: Baseline vs Final

{self._generate_baseline_vs_final_table()}

## Dead Tuple Accumulation

Dead tuples are created by PostgreSQL's MVCC system when rows are updated or deleted.
They remain in the table until VACUUM removes them, consuming disk space and
degrading query performance.

"""
        
        if dead_tuple_img:
            rel_path = dead_tuple_img.relative_to(self.output_dir)
            report += f"![Dead Tuple Growth]({rel_path})\n\n"
        
        report += """## Table Size Bloat

As dead tuples accumulate, the table size grows beyond what's needed for live data.
This bloat increases I/O costs and memory pressure.

"""
        
        if table_size_img:
            rel_path = table_size_img.relative_to(self.output_dir)
            report += f"![Table Size Growth]({rel_path})\n\n"
        
        report += """## Buffer Cache Efficiency

The buffer hit ratio shows how often requested pages are found in shared_buffers
vs. requiring disk I/O. Table bloat can pollute the cache with dead tuple pages.

"""
        
        if buffer_hit_img:
            rel_path = buffer_hit_img.relative_to(self.output_dir)
            report += f"![Buffer Hit Ratio]({rel_path})\n\n"
        
        report += """## HOT Update Performance

HOT (Heap-Only Tuple) updates are an optimization where PostgreSQL can update
a tuple without modifying indexes, if the new version fits on the same page.
Higher HOT ratios indicate more efficient updates.

"""
        
        if hot_update_img:
            rel_path = hot_update_img.relative_to(self.output_dir)
            report += f"![HOT Update Ratio]({rel_path})\n\n"
        
        report += """## Update Throughput

"""
        
        if updates_img:
            rel_path = updates_img.relative_to(self.output_dir)
            report += f"![Updates Over Time]({rel_path})\n\n"
        
        # Add plan comparisons
        if plan_images:
            report += """## Query Plan Evolution

These visualizations show how query execution plans changed as table bloat increased.
Changes from Index Scan to Seq Scan, or significant cost increases, indicate
performance degradation.

"""
            for query_name, img_path in plan_images:
                # Copy image to report images dir
                import shutil
                dest_path = self.images_dir / img_path.name
                shutil.copy(img_path, dest_path)
                rel_path = dest_path.relative_to(self.output_dir)
                
                report += f"### {query_name}\n\n"
                report += f"![{query_name} Plan Comparison]({rel_path})\n\n"
        
        report += """## Key Findings

Based on the experiment data:

1. **Dead Tuple Growth**: [Analysis of dead tuple accumulation rate]

2. **Table Bloat**: [Analysis of size increase vs. useful data]

3. **Query Performance**: [Analysis of any query plan changes or slowdowns]

4. **Buffer Efficiency**: [Analysis of cache hit ratio trends]

## Recommendations

1. **Autovacuum Tuning**: Consider adjusting `autovacuum_vacuum_scale_factor` for high-update tables.

2. **Schema Design**: For frequently-updated JSONB columns, consider:
   - Separating frequently-changed fields into scalar columns
   - Using normalized tables for high-velocity updates

3. **Monitoring**: Track `n_dead_tup` and table size in production monitoring.

---

*Report generated by pg-mvcc-bloat experiment framework*
"""
        
        # Write report
        report_path = self.output_dir / "report.md"
        with open(report_path, 'w') as f:
            f.write(report)
        
        print(f"Report generated: {report_path}")
        return report_path


def main():
    parser = argparse.ArgumentParser(description="Generate experiment report")
    parser.add_argument(
        "run_id",
        help="Experiment run ID",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Output directory for report",
    )
    parser.add_argument(
        "--load-from-db",
        action="store_true",
        help="Load snapshot data from database",
    )
    
    args = parser.parse_args()
    
    db_config = None
    if args.load_from_db:
        db_config = DatabaseConfig.from_env()
    
    generator = ReportGenerator(
        run_id=args.run_id,
        output_dir=args.output_dir,
    )
    
    report_path = generator.generate_report(db_config)
    print(f"\nReport saved to: {report_path}")


if __name__ == "__main__":
    main()
