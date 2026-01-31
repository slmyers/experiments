"""
Writer process for generating update workload.

Supports different update patterns:
- jsonb_mutation: Updates JSONB column (creates new TOAST entries)
- flag_only: Updates only scalar columns (reuses TOAST pointers)
- normalized: Updates scalar columns in normalized table
"""
import argparse
import json
import random
import sys
import time
from datetime import datetime
from typing import Optional
from dataclasses import dataclass, asdict

from faker import Faker

sys.path.insert(0, str(__file__).rsplit("/", 3)[0])
from common import (
    DatabaseConfig,
    get_connection,
    TABLE_JSONB,
    TABLE_JSONB_FLAGS,
    TABLE_NORMALIZED,
    DEFAULT_BATCH_SIZE,
)


@dataclass
class WriterStats:
    """Statistics tracked by the writer process."""
    updates_attempted: int = 0
    updates_successful: int = 0
    updates_failed: int = 0
    total_time_ms: float = 0.0
    start_time: Optional[str] = None
    end_time: Optional[str] = None


class Writer:
    """
    Executes update workload against experiment tables.
    """
    
    def __init__(
        self,
        config: DatabaseConfig,
        table: str,
        update_pattern: str,
        batch_size: int = 100,
        rate_limit: Optional[float] = None,  # updates per second, None = unlimited
        random_seed: int = 42,
    ):
        self.config = config
        self.table = table
        self.update_pattern = update_pattern
        self.batch_size = batch_size
        self.rate_limit = rate_limit
        self.stats = WriterStats()
        
        # Seed for reproducible update patterns
        random.seed(random_seed)
        Faker.seed(random_seed)
        self.fake = Faker()
        
        # Get row count for random ID selection
        with get_connection(config) as conn:
            with conn.cursor() as cursor:
                cursor.execute(f"SELECT COUNT(*) FROM {table}")
                self.row_count = cursor.fetchone()[0]
        
        if self.row_count == 0:
            raise ValueError(f"Table {table} is empty. Run seed first.")
    
    def _get_random_ids(self, count: int) -> list:
        """Get random row IDs to update."""
        return [random.randint(1, self.row_count) for _ in range(count)]
    
    def _update_jsonb_mutation(self, conn, ids: list) -> int:
        """
        Update JSONB column with new values.
        This creates new TOAST entries for each updated row.
        """
        updated = 0
        with conn.cursor() as cursor:
            for row_id in ids:
                # Generate new JSONB content that will require new TOAST storage
                new_body = self.fake.paragraph(nb_sentences=10)
                new_description = self.fake.paragraph(nb_sentences=5)
                
                cursor.execute(f"""
                    UPDATE {TABLE_JSONB}
                    SET 
                        data = jsonb_set(
                            jsonb_set(
                                jsonb_set(data, '{{body}}', %s::jsonb),
                                '{{description}}', %s::jsonb
                            ),
                            '{{metadata,updated_at}}', %s::jsonb
                        ),
                        updated_at = NOW()
                    WHERE id = %s
                """, (
                    json.dumps(new_body),
                    json.dumps(new_description),
                    json.dumps(datetime.now().isoformat()),
                    row_id,
                ))
                updated += cursor.rowcount
        return updated
    
    def _update_flag_only(self, conn, ids: list) -> int:
        """
        Update only scalar columns, leaving JSONB unchanged.
        This should reuse existing TOAST pointers (HOT update potential).
        """
        updated = 0
        statuses = ["pending", "active", "completed", "archived", "processing"]
        
        with conn.cursor() as cursor:
            for row_id in ids:
                new_status = random.choice(statuses)
                new_priority = random.randint(1, 10)
                
                cursor.execute(f"""
                    UPDATE {TABLE_JSONB_FLAGS}
                    SET 
                        status = %s,
                        priority = %s,
                        process_count = process_count + 1,
                        last_processed_at = NOW(),
                        updated_at = NOW()
                    WHERE id = %s
                """, (new_status, new_priority, row_id))
                updated += cursor.rowcount
        return updated
    
    def _update_normalized(self, conn, ids: list) -> int:
        """
        Update scalar columns in normalized table.
        Small, efficient updates with good HOT potential.
        """
        updated = 0
        statuses = ["pending", "active", "completed", "archived", "processing"]
        
        with conn.cursor() as cursor:
            for row_id in ids:
                new_status = random.choice(statuses)
                new_priority = random.randint(1, 10)
                new_view_count_increment = random.randint(1, 100)
                
                cursor.execute(f"""
                    UPDATE {TABLE_NORMALIZED}
                    SET 
                        status = %s,
                        priority = %s,
                        view_count = view_count + %s,
                        updated_at = NOW()
                    WHERE id = %s
                """, (new_status, new_priority, new_view_count_increment, row_id))
                updated += cursor.rowcount
        return updated
    
    def execute_batch(self) -> int:
        """Execute a single batch of updates."""
        ids = self._get_random_ids(self.batch_size)
        
        update_func = {
            "jsonb_mutation": self._update_jsonb_mutation,
            "flag_only": self._update_flag_only,
            "normalized": self._update_normalized,
        }.get(self.update_pattern)
        
        if update_func is None:
            raise ValueError(f"Unknown update pattern: {self.update_pattern}")
        
        with get_connection(self.config) as conn:
            start = time.perf_counter()
            try:
                updated = update_func(conn, ids)
                conn.commit()
                elapsed_ms = (time.perf_counter() - start) * 1000
                
                self.stats.updates_attempted += len(ids)
                self.stats.updates_successful += updated
                self.stats.total_time_ms += elapsed_ms
                
                return updated
            except Exception as e:
                conn.rollback()
                self.stats.updates_attempted += len(ids)
                self.stats.updates_failed += len(ids)
                print(f"Update batch failed: {e}")
                return 0
    
    def run(self, duration_seconds: float, stop_event=None) -> WriterStats:
        """
        Run update workload for specified duration.
        
        Args:
            duration_seconds: How long to run
            stop_event: Optional threading.Event to signal early stop
        
        Returns:
            WriterStats with execution statistics
        """
        self.stats = WriterStats()
        self.stats.start_time = datetime.now().isoformat()
        
        start_time = time.time()
        end_time = start_time + duration_seconds
        
        batch_count = 0
        while time.time() < end_time:
            if stop_event and stop_event.is_set():
                break
            
            batch_start = time.perf_counter()
            self.execute_batch()
            batch_elapsed = time.perf_counter() - batch_start
            batch_count += 1
            
            # Rate limiting
            if self.rate_limit:
                target_batch_time = self.batch_size / self.rate_limit
                if batch_elapsed < target_batch_time:
                    time.sleep(target_batch_time - batch_elapsed)
            
            # Progress update every 10 batches
            if batch_count % 10 == 0:
                elapsed = time.time() - start_time
                rate = self.stats.updates_successful / elapsed if elapsed > 0 else 0
                print(f"  Writer: {self.stats.updates_successful:,} updates, {rate:.0f}/sec")
        
        self.stats.end_time = datetime.now().isoformat()
        return self.stats


def main():
    parser = argparse.ArgumentParser(description="Execute update workload")
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
        "--batch-size",
        type=int,
        default=100,
        help="Updates per batch (default: 100)",
    )
    parser.add_argument(
        "--rate-limit",
        type=float,
        default=None,
        help="Max updates per second (default: unlimited)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed (default: 42)",
    )
    
    args = parser.parse_args()
    config = DatabaseConfig.from_env()
    
    writer = Writer(
        config=config,
        table=args.table,
        update_pattern=args.pattern,
        batch_size=args.batch_size,
        rate_limit=args.rate_limit,
        random_seed=args.seed,
    )
    
    print(f"Starting writer: table={args.table}, pattern={args.pattern}")
    print(f"Duration: {args.duration}s, Batch size: {args.batch_size}")
    
    stats = writer.run(args.duration)
    
    print("\n--- Writer Statistics ---")
    print(f"Updates attempted: {stats.updates_attempted:,}")
    print(f"Updates successful: {stats.updates_successful:,}")
    print(f"Updates failed: {stats.updates_failed:,}")
    print(f"Total time: {stats.total_time_ms:.0f}ms")
    if stats.updates_successful > 0:
        avg_time = stats.total_time_ms / stats.updates_successful
        print(f"Avg time per update: {avg_time:.2f}ms")


if __name__ == "__main__":
    main()
