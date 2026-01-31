"""
Metrics snapshot capture for experiment tables.

Captures full point-in-time snapshots of table statistics,
including tuple counts, sizes, and I/O stats.
"""
import argparse
import json
import sys
from datetime import datetime
from dataclasses import dataclass, asdict, field
from typing import Optional, Dict, Any, List

sys.path.insert(0, str(__file__).rsplit("/", 3)[0])
from common import (
    DatabaseConfig,
    get_connection,
    get_cursor,
    TABLE_JSONB,
    TABLE_JSONB_FLAGS,
    TABLE_NORMALIZED,
    ALL_TABLES,
)


@dataclass
class TableSnapshot:
    """Complete snapshot of a table's statistics."""
    table_name: str
    snapshot_type: str
    captured_at: str = field(default_factory=lambda: datetime.now().isoformat())
    elapsed_seconds: Optional[float] = None
    
    # Tuple statistics (pg_stat_user_tables)
    n_live_tup: int = 0
    n_dead_tup: int = 0
    n_tup_ins: int = 0
    n_tup_upd: int = 0
    n_tup_del: int = 0
    n_tup_hot_upd: int = 0
    
    # Size metrics
    table_size_bytes: int = 0
    toast_size_bytes: int = 0
    index_size_bytes: int = 0
    total_size_bytes: int = 0
    
    # Detailed tuple stats (pgstattuple)
    tuple_count: int = 0
    tuple_len: int = 0
    dead_tuple_count: int = 0
    dead_tuple_len: int = 0
    free_space: int = 0
    free_percent: float = 0.0
    
    # I/O statistics (pg_statio_user_tables)
    heap_blks_read: int = 0
    heap_blks_hit: int = 0
    idx_blks_read: int = 0
    idx_blks_hit: int = 0
    toast_blks_read: int = 0
    toast_blks_hit: int = 0
    
    # Vacuum statistics
    last_vacuum: Optional[str] = None
    last_autovacuum: Optional[str] = None
    vacuum_count: int = 0
    autovacuum_count: int = 0
    
    @property
    def dead_tuple_ratio(self) -> float:
        """Ratio of dead tuples to total tuples."""
        total = self.n_live_tup + self.n_dead_tup
        if total == 0:
            return 0.0
        return self.n_dead_tup / total
    
    @property
    def hot_update_ratio(self) -> float:
        """Ratio of HOT updates to total updates."""
        if self.n_tup_upd == 0:
            return 0.0
        return self.n_tup_hot_upd / self.n_tup_upd
    
    @property
    def buffer_hit_ratio(self) -> float:
        """Buffer cache hit ratio for heap."""
        total = self.heap_blks_hit + self.heap_blks_read
        if total == 0:
            return 0.0
        return self.heap_blks_hit / total
    
    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["dead_tuple_ratio"] = self.dead_tuple_ratio
        d["hot_update_ratio"] = self.hot_update_ratio
        d["buffer_hit_ratio"] = self.buffer_hit_ratio
        return d


def capture_table_stats(
    conn,
    table_name: str,
) -> Dict[str, Any]:
    """
    Capture basic table statistics from pg_stat_user_tables.
    
    Note: n_live_tup is an estimate updated by ANALYZE. When stale,
    we calculate it from n_tup_ins - n_tup_del which is accurate.
    """
    with conn.cursor() as cursor:
        cursor.execute("""
            SELECT 
                n_live_tup,
                n_dead_tup,
                n_tup_ins,
                n_tup_upd,
                n_tup_del,
                n_tup_hot_upd,
                last_vacuum,
                last_autovacuum,
                vacuum_count,
                autovacuum_count,
                last_analyze,
                last_autoanalyze
            FROM pg_stat_user_tables
            WHERE relname = %s
        """, (table_name,))
        row = cursor.fetchone()
        
        if row is None:
            return {}
        
        n_live_tup_estimate = row[0] or 0
        n_tup_ins = row[2] or 0
        n_tup_del = row[4] or 0
        
        # Use calculated value when estimate is stale or zero
        # This is more accurate than the stale estimate
        n_live_tup_calculated = max(0, n_tup_ins - n_tup_del)
        
        # Prefer calculated value if estimate is stale or zero
        n_live_tup = n_live_tup_calculated if n_live_tup_estimate == 0 else n_live_tup_estimate
        
        return {
            "n_live_tup": n_live_tup,
            "n_dead_tup": row[1] or 0,
            "n_tup_ins": n_tup_ins,
            "n_tup_upd": row[3] or 0,
            "n_tup_del": n_tup_del,
            "n_tup_hot_upd": row[5] or 0,
            "last_vacuum": row[6].isoformat() if row[6] else None,
            "last_autovacuum": row[7].isoformat() if row[7] else None,
            "vacuum_count": row[8] or 0,
            "autovacuum_count": row[9] or 0,
        }


def capture_table_sizes(
    conn,
    table_name: str,
) -> Dict[str, Any]:
    """Capture table size metrics."""
    with conn.cursor() as cursor:
        cursor.execute("""
            SELECT 
                pg_relation_size(%s::regclass) as table_size,
                COALESCE(
                    pg_relation_size(
                        (SELECT reltoastrelid FROM pg_class WHERE relname = %s)
                    ), 0
                ) as toast_size,
                pg_indexes_size(%s::regclass) as index_size,
                pg_total_relation_size(%s::regclass) as total_size
        """, (table_name, table_name, table_name, table_name))
        row = cursor.fetchone()
        
        return {
            "table_size_bytes": row[0] or 0,
            "toast_size_bytes": row[1] or 0,
            "index_size_bytes": row[2] or 0,
            "total_size_bytes": row[3] or 0,
        }


def capture_io_stats(
    conn,
    table_name: str,
) -> Dict[str, Any]:
    """Capture I/O statistics from pg_statio_user_tables."""
    with conn.cursor() as cursor:
        cursor.execute("""
            SELECT 
                heap_blks_read,
                heap_blks_hit,
                idx_blks_read,
                idx_blks_hit,
                toast_blks_read,
                toast_blks_hit
            FROM pg_statio_user_tables
            WHERE relname = %s
        """, (table_name,))
        row = cursor.fetchone()
        
        if row is None:
            return {}
        
        return {
            "heap_blks_read": row[0] or 0,
            "heap_blks_hit": row[1] or 0,
            "idx_blks_read": row[2] or 0,
            "idx_blks_hit": row[3] or 0,
            "toast_blks_read": row[4] or 0,
            "toast_blks_hit": row[5] or 0,
        }


def capture_pgstattuple(
    conn,
    table_name: str,
) -> Dict[str, Any]:
    """
    Capture detailed tuple statistics using pgstattuple extension.
    
    NOTE: pgstattuple performs a full table scan, so this is expensive
    and should only be used for baseline/final snapshots, not continuous.
    """
    try:
        with conn.cursor() as cursor:
            cursor.execute(f"SELECT * FROM pgstattuple('{table_name}')")
            row = cursor.fetchone()
            
            if row is None:
                return {}
            
            # pgstattuple returns: table_len, tuple_count, tuple_len, tuple_percent,
            # dead_tuple_count, dead_tuple_len, dead_tuple_percent, free_space, free_percent
            return {
                "tuple_count": row[1] or 0,
                "tuple_len": row[2] or 0,
                "dead_tuple_count": row[4] or 0,
                "dead_tuple_len": row[5] or 0,
                "free_space": row[7] or 0,
                "free_percent": float(row[8]) if row[8] else 0.0,
            }
    except Exception as e:
        print(f"Warning: pgstattuple failed for {table_name}: {e}")
        return {}


def capture_snapshot(
    config: DatabaseConfig,
    table_name: str,
    snapshot_type: str,
    elapsed_seconds: Optional[float] = None,
    include_pgstattuple: bool = True,
) -> TableSnapshot:
    """
    Capture a complete snapshot of table statistics.
    
    Args:
        config: Database configuration
        table_name: Name of the table to capture
        snapshot_type: Type of snapshot (baseline, continuous, final)
        elapsed_seconds: Time since experiment start
        include_pgstattuple: Whether to include expensive pgstattuple stats
    
    Returns:
        TableSnapshot with all captured metrics
    """
    snapshot = TableSnapshot(
        table_name=table_name,
        snapshot_type=snapshot_type,
        elapsed_seconds=elapsed_seconds,
    )
    
    with get_connection(config) as conn:
        # Basic stats
        stats = capture_table_stats(conn, table_name)
        for key, value in stats.items():
            setattr(snapshot, key, value)
        
        # Sizes
        sizes = capture_table_sizes(conn, table_name)
        for key, value in sizes.items():
            setattr(snapshot, key, value)
        
        # I/O stats
        io_stats = capture_io_stats(conn, table_name)
        for key, value in io_stats.items():
            setattr(snapshot, key, value)
        
        # pgstattuple (expensive, skip for continuous)
        if include_pgstattuple and snapshot_type != "continuous":
            pgtuple_stats = capture_pgstattuple(conn, table_name)
            for key, value in pgtuple_stats.items():
                setattr(snapshot, key, value)
    
    return snapshot


def capture_all_tables_snapshot(
    config: DatabaseConfig,
    snapshot_type: str,
    elapsed_seconds: Optional[float] = None,
    include_pgstattuple: bool = True,
) -> List[TableSnapshot]:
    """Capture snapshots for all experiment tables."""
    snapshots = []
    for table in ALL_TABLES:
        snapshot = capture_snapshot(
            config=config,
            table_name=table,
            snapshot_type=snapshot_type,
            elapsed_seconds=elapsed_seconds,
            include_pgstattuple=include_pgstattuple,
        )
        snapshots.append(snapshot)
    return snapshots


def save_snapshot_to_db(
    config: DatabaseConfig,
    run_id: str,
    snapshot: TableSnapshot,
) -> None:
    """Save a snapshot to the metrics_snapshots table."""
    with get_cursor(config) as cursor:
        cursor.execute("""
            INSERT INTO metrics_snapshots (
                run_id, snapshot_type, table_name, elapsed_seconds,
                n_live_tup, n_dead_tup, n_tup_ins, n_tup_upd, n_tup_del, n_tup_hot_upd,
                table_size_bytes, toast_size_bytes, index_size_bytes, total_size_bytes,
                tuple_count, tuple_len, dead_tuple_count, dead_tuple_len, free_space, free_percent,
                heap_blks_read, heap_blks_hit, idx_blks_read, idx_blks_hit, toast_blks_read, toast_blks_hit,
                last_vacuum, last_autovacuum, vacuum_count, autovacuum_count
            ) VALUES (
                %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s
            )
        """, (
            run_id, snapshot.snapshot_type, snapshot.table_name, snapshot.elapsed_seconds,
            snapshot.n_live_tup, snapshot.n_dead_tup, snapshot.n_tup_ins, snapshot.n_tup_upd,
            snapshot.n_tup_del, snapshot.n_tup_hot_upd,
            snapshot.table_size_bytes, snapshot.toast_size_bytes, snapshot.index_size_bytes,
            snapshot.total_size_bytes,
            snapshot.tuple_count, snapshot.tuple_len, snapshot.dead_tuple_count,
            snapshot.dead_tuple_len, snapshot.free_space, snapshot.free_percent,
            snapshot.heap_blks_read, snapshot.heap_blks_hit, snapshot.idx_blks_read,
            snapshot.idx_blks_hit, snapshot.toast_blks_read, snapshot.toast_blks_hit,
            snapshot.last_vacuum, snapshot.last_autovacuum, snapshot.vacuum_count,
            snapshot.autovacuum_count,
        ))


def reset_stats(config: DatabaseConfig) -> None:
    """Reset PostgreSQL statistics for clean experiment."""
    with get_connection(config) as conn:
        with conn.cursor() as cursor:
            try:
                cursor.execute("SELECT pg_stat_statements_reset()")
            except Exception:
                pass  # Extension may not be available
            cursor.execute("SELECT pg_stat_reset()")
        conn.commit()
    print("Statistics reset")


def main():
    parser = argparse.ArgumentParser(description="Capture table statistics snapshot")
    parser.add_argument(
        "--table",
        choices=ALL_TABLES + ["all"],
        default="all",
        help="Table to capture (default: all)",
    )
    parser.add_argument(
        "--type",
        choices=["baseline", "continuous", "final"],
        default="baseline",
        help="Snapshot type (default: baseline)",
    )
    parser.add_argument(
        "--run-id",
        default="manual",
        help="Experiment run ID",
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Reset statistics before capture",
    )
    
    args = parser.parse_args()
    config = DatabaseConfig.from_env()
    
    if args.reset:
        reset_stats(config)
    
    if args.table == "all":
        snapshots = capture_all_tables_snapshot(
            config=config,
            snapshot_type=args.type,
            include_pgstattuple=args.type != "continuous",
        )
    else:
        snapshots = [capture_snapshot(
            config=config,
            table_name=args.table,
            snapshot_type=args.type,
            include_pgstattuple=args.type != "continuous",
        )]
    
    for snapshot in snapshots:
        print(f"\n=== {snapshot.table_name} ({snapshot.snapshot_type}) ===")
        print(f"Live tuples: {snapshot.n_live_tup:,}")
        print(f"Dead tuples: {snapshot.n_dead_tup:,} ({snapshot.dead_tuple_ratio:.1%})")
        print(f"Total updates: {snapshot.n_tup_upd:,}")
        print(f"HOT updates: {snapshot.n_tup_hot_upd:,} ({snapshot.hot_update_ratio:.1%})")
        print(f"Table size: {snapshot.table_size_bytes:,} bytes")
        print(f"TOAST size: {snapshot.toast_size_bytes:,} bytes")
        print(f"Total size: {snapshot.total_size_bytes:,} bytes")
        print(f"Buffer hit ratio: {snapshot.buffer_hit_ratio:.1%}")
        
        # Save to database
        save_snapshot_to_db(config, args.run_id, snapshot)
    
    print(f"\nSnapshots saved to database with run_id: {args.run_id}")


if __name__ == "__main__":
    main()
