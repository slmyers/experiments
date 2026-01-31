"""
Reader process for executing benchmark queries.

Runs queries in a loop, recording timing and capturing query plans
at configurable intervals.
"""
import argparse
import json
import sys
import time
from datetime import datetime
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from pathlib import Path

sys.path.insert(0, str(__file__).rsplit("/", 3)[0])
from common import (
    DatabaseConfig,
    get_connection,
    TABLE_JSONB,
    TABLE_JSONB_FLAGS,
    TABLE_NORMALIZED,
    PLANS_DIR,
)


@dataclass
class QueryResult:
    """Result of a single query execution."""
    query_name: str
    execution_time_ms: float
    rows_returned: int
    shared_blks_hit: int = 0
    shared_blks_read: int = 0
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass 
class ReaderStats:
    """Statistics tracked by the reader process."""
    queries_executed: int = 0
    total_time_ms: float = 0.0
    results: List[QueryResult] = field(default_factory=list)
    plans_captured: int = 0
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    
    @property
    def avg_time_ms(self) -> float:
        if self.queries_executed == 0:
            return 0.0
        return self.total_time_ms / self.queries_executed
    
    def get_percentile(self, p: float) -> float:
        """Get percentile of query times."""
        if not self.results:
            return 0.0
        times = sorted(r.execution_time_ms for r in self.results)
        idx = int(len(times) * p / 100)
        return times[min(idx, len(times) - 1)]


# Benchmark queries for each table type
QUERIES = {
    TABLE_JSONB: {
        "point_lookup": """
            SELECT * FROM documents_jsonb WHERE id = %s
        """,
        "jsonb_containment": """
            SELECT id, data->>'title' as title
            FROM documents_jsonb 
            WHERE data @> '{"status": "active"}'
            LIMIT 100
        """,
        "jsonb_filter": """
            SELECT id, data->>'title' as title, data->>'status' as status
            FROM documents_jsonb
            WHERE data->>'status' = %s
            ORDER BY (data->>'priority')::int DESC
            LIMIT 100
        """,
        "range_scan": """
            SELECT id, data->>'title' as title
            FROM documents_jsonb
            WHERE id BETWEEN %s AND %s
            ORDER BY id
        """,
        "aggregate": """
            SELECT 
                data->>'status' as status,
                COUNT(*) as count,
                AVG((data->'metrics'->>'view_count')::int) as avg_views
            FROM documents_jsonb
            GROUP BY data->>'status'
        """,
    },
    TABLE_JSONB_FLAGS: {
        "point_lookup": """
            SELECT * FROM documents_jsonb_with_flags WHERE id = %s
        """,
        "status_filter": """
            SELECT id, status, priority, data->>'title' as title
            FROM documents_jsonb_with_flags
            WHERE status = %s
            ORDER BY priority DESC
            LIMIT 100
        """,
        "range_scan": """
            SELECT id, status, data->>'title' as title
            FROM documents_jsonb_with_flags
            WHERE id BETWEEN %s AND %s
            ORDER BY id
        """,
    },
    TABLE_NORMALIZED: {
        "point_lookup": """
            SELECT * FROM documents_normalized WHERE id = %s
        """,
        "status_filter": """
            SELECT id, title, status, priority
            FROM documents_normalized
            WHERE status = %s
            ORDER BY priority DESC
            LIMIT 100
        """,
        "range_scan": """
            SELECT id, title, status
            FROM documents_normalized
            WHERE id BETWEEN %s AND %s
            ORDER BY id
        """,
        "aggregate": """
            SELECT 
                status,
                COUNT(*) as count,
                AVG(view_count) as avg_views
            FROM documents_normalized
            GROUP BY status
        """,
    },
}


class Reader:
    """
    Executes benchmark queries against experiment tables.
    """
    
    def __init__(
        self,
        config: DatabaseConfig,
        table: str,
        run_id: str,
        plan_capture_interval: int = 60,  # Capture plans every N seconds
    ):
        self.config = config
        self.table = table
        self.run_id = run_id
        self.plan_capture_interval = plan_capture_interval
        self.stats = ReaderStats()
        self.queries = QUERIES.get(table, {})
        self.last_plan_capture = 0
        self.plan_sequence = 0
        
        # Get row count for random ID generation
        with get_connection(config) as conn:
            with conn.cursor() as cursor:
                cursor.execute(f"SELECT COUNT(*) FROM {table}")
                self.row_count = cursor.fetchone()[0]
        
        # Setup plans directory
        self.plans_dir = PLANS_DIR / run_id
        self.plans_dir.mkdir(parents=True, exist_ok=True)
    
    def _get_query_params(self, query_name: str) -> tuple:
        """Generate parameters for query based on name."""
        import random
        
        if "point_lookup" in query_name:
            return (random.randint(1, self.row_count),)
        elif "filter" in query_name or "containment" in query_name:
            return (random.choice(["pending", "active", "completed"]),)
        elif "range_scan" in query_name:
            start = random.randint(1, max(1, self.row_count - 1000))
            return (start, start + 1000)
        else:
            return ()
    
    def _execute_query(self, query_name: str, query_sql: str) -> QueryResult:
        """Execute a single query and return results."""
        params = self._get_query_params(query_name)
        
        with get_connection(self.config) as conn:
            with conn.cursor() as cursor:
                start = time.perf_counter()
                cursor.execute(query_sql, params)
                rows = cursor.fetchall()
                elapsed_ms = (time.perf_counter() - start) * 1000
                
                return QueryResult(
                    query_name=query_name,
                    execution_time_ms=elapsed_ms,
                    rows_returned=len(rows),
                )
    
    def _capture_plan(self, query_name: str, query_sql: str, snapshot_type: str = "during") -> Dict[str, Any]:
        """Capture query execution plan with EXPLAIN ANALYZE."""
        params = self._get_query_params(query_name)
        
        # Build EXPLAIN query
        explain_sql = f"EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) {query_sql}"
        
        with get_connection(self.config) as conn:
            with conn.cursor() as cursor:
                cursor.execute(explain_sql, params)
                plan_result = cursor.fetchone()[0]
                
                plan_data = {
                    "run_id": self.run_id,
                    "query_name": query_name,
                    "query_sql": query_sql,
                    "params": params,
                    "snapshot_type": snapshot_type,
                    "captured_at": datetime.now().isoformat(),
                    "sequence": self.plan_sequence,
                    "plan": plan_result,
                }
                
                # Extract key metrics from plan
                if plan_result and len(plan_result) > 0:
                    plan = plan_result[0].get("Plan", {})
                    plan_data["execution_time_ms"] = plan_result[0].get("Execution Time", 0)
                    plan_data["planning_time_ms"] = plan_result[0].get("Planning Time", 0)
                    plan_data["shared_blks_hit"] = plan.get("Shared Hit Blocks", 0)
                    plan_data["shared_blks_read"] = plan.get("Shared Read Blocks", 0)
                    plan_data["node_type"] = plan.get("Node Type", "Unknown")
                    plan_data["total_cost"] = plan.get("Total Cost", 0)
                    plan_data["actual_rows"] = plan.get("Actual Rows", 0)
                    plan_data["plan_rows"] = plan.get("Plan Rows", 0)
                
                # Save to file
                plan_file = self.plans_dir / f"{query_name}_{self.plan_sequence:04d}.json"
                with open(plan_file, 'w') as f:
                    json.dump(plan_data, f, indent=2, default=str)
                
                self.plan_sequence += 1
                self.stats.plans_captured += 1
                
                return plan_data
    
    def capture_baseline_plans(self) -> List[Dict[str, Any]]:
        """Capture plans for all queries at baseline."""
        plans = []
        for query_name, query_sql in self.queries.items():
            plan = self._capture_plan(query_name, query_sql, "baseline")
            plans.append(plan)
        return plans
    
    def capture_final_plans(self) -> List[Dict[str, Any]]:
        """Capture plans for all queries at end of experiment."""
        plans = []
        for query_name, query_sql in self.queries.items():
            plan = self._capture_plan(query_name, query_sql, "final")
            plans.append(plan)
        return plans
    
    def run(self, duration_seconds: float, stop_event=None) -> ReaderStats:
        """
        Run query workload for specified duration.
        
        Args:
            duration_seconds: How long to run
            stop_event: Optional threading.Event to signal early stop
        
        Returns:
            ReaderStats with execution statistics
        """
        self.stats = ReaderStats()
        self.stats.start_time = datetime.now().isoformat()
        
        start_time = time.time()
        end_time = start_time + duration_seconds
        self.last_plan_capture = start_time
        
        query_names = list(self.queries.keys())
        query_idx = 0
        
        while time.time() < end_time:
            if stop_event and stop_event.is_set():
                break
            
            # Execute next query in round-robin
            query_name = query_names[query_idx % len(query_names)]
            query_sql = self.queries[query_name]
            
            try:
                result = self._execute_query(query_name, query_sql)
                self.stats.results.append(result)
                self.stats.queries_executed += 1
                self.stats.total_time_ms += result.execution_time_ms
            except Exception as e:
                print(f"Query failed: {query_name}: {e}")
            
            query_idx += 1
            
            # Periodic plan capture
            current_time = time.time()
            if current_time - self.last_plan_capture >= self.plan_capture_interval:
                for qn, qs in self.queries.items():
                    self._capture_plan(qn, qs, "during")
                self.last_plan_capture = current_time
            
            # Small sleep to avoid overwhelming the database
            time.sleep(0.01)
        
        self.stats.end_time = datetime.now().isoformat()
        return self.stats


def main():
    parser = argparse.ArgumentParser(description="Execute read workload")
    parser.add_argument(
        "--table",
        choices=[TABLE_JSONB, TABLE_JSONB_FLAGS, TABLE_NORMALIZED],
        required=True,
        help="Target table",
    )
    parser.add_argument(
        "--run-id",
        required=True,
        help="Experiment run ID",
    )
    parser.add_argument(
        "--duration",
        type=int,
        default=60,
        help="Duration in seconds (default: 60)",
    )
    parser.add_argument(
        "--plan-interval",
        type=int,
        default=60,
        help="Seconds between plan captures (default: 60)",
    )
    
    args = parser.parse_args()
    config = DatabaseConfig.from_env()
    
    reader = Reader(
        config=config,
        table=args.table,
        run_id=args.run_id,
        plan_capture_interval=args.plan_interval,
    )
    
    print(f"Starting reader: table={args.table}, run_id={args.run_id}")
    print(f"Duration: {args.duration}s, Plan capture interval: {args.plan_interval}s")
    
    # Capture baseline plans
    print("Capturing baseline plans...")
    reader.capture_baseline_plans()
    
    # Run workload
    stats = reader.run(args.duration)
    
    # Capture final plans
    print("Capturing final plans...")
    reader.capture_final_plans()
    
    print("\n--- Reader Statistics ---")
    print(f"Queries executed: {stats.queries_executed:,}")
    print(f"Total time: {stats.total_time_ms:.0f}ms")
    print(f"Avg time: {stats.avg_time_ms:.2f}ms")
    print(f"P50: {stats.get_percentile(50):.2f}ms")
    print(f"P95: {stats.get_percentile(95):.2f}ms")
    print(f"P99: {stats.get_percentile(99):.2f}ms")
    print(f"Plans captured: {stats.plans_captured}")


if __name__ == "__main__":
    main()
