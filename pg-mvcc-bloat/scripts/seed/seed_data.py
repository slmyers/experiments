"""
Deterministic seed data generator for experiment tables.

Uses fixed random seed for exact reproducibility across runs.
Generates ~3KB JSONB documents that will be TOASTed by PostgreSQL.
"""
import argparse
import json
import random
import sys
from datetime import datetime, timedelta
from typing import Generator, List, Dict, Any

from faker import Faker
from tqdm import tqdm

sys.path.insert(0, str(__file__).rsplit("/", 2)[0])
from common import (
    DatabaseConfig,
    get_connection,
    TABLE_JSONB,
    TABLE_JSONB_FLAGS,
    TABLE_NORMALIZED,
    DEFAULT_RANDOM_SEED,
    DEFAULT_ROW_COUNT,
    DEFAULT_BATCH_SIZE,
    sizeof_fmt,
)


def create_faker(seed: int) -> Faker:
    """Create a seeded Faker instance for reproducible data."""
    Faker.seed(seed)
    random.seed(seed)
    return Faker()


def generate_large_jsonb_document(fake: Faker, doc_id: int) -> Dict[str, Any]:
    """
    Generate a JSONB document of approximately 3KB.
    
    Structure designed to be realistic and large enough to trigger TOAST storage.
    PostgreSQL TOAST threshold is ~2KB, so 3KB ensures TOASTing.
    """
    # Generate enough content to reach ~3KB
    return {
        "id": doc_id,
        "title": fake.sentence(nb_words=12),
        "body": fake.paragraph(nb_sentences=25),  # ~1500-2000 chars
        "summary": fake.paragraph(nb_sentences=8),  # ~400-600 chars
        "status": random.choice(["pending", "active", "completed", "archived"]),
        "priority": random.randint(1, 10),
        "author": {
            "name": fake.name(),
            "email": fake.email(),
            "department": fake.job(),
            "employee_id": fake.uuid4(),
            "bio": fake.paragraph(nb_sentences=3),
            "location": fake.city(),
            "timezone": fake.timezone(),
        },
        "metadata": {
            "created_at": fake.date_time_this_year().isoformat(),
            "updated_at": fake.date_time_this_month().isoformat(),
            "version": random.randint(1, 100),
            "source": random.choice(["api", "web", "mobile", "import", "system"]),
            "tags": [fake.word() for _ in range(random.randint(5, 12))],
            "category": fake.word(),
            "subcategory": fake.word(),
            "keywords": [fake.word() for _ in range(random.randint(8, 15))],
        },
        "metrics": {
            "view_count": random.randint(0, 10000),
            "edit_count": random.randint(0, 100),
            "share_count": random.randint(0, 500),
            "comment_count": random.randint(0, 200),
            "like_count": random.randint(0, 1000),
            "bookmark_count": random.randint(0, 300),
        },
        "settings": {
            "is_public": random.choice([True, False]),
            "allow_comments": random.choice([True, False]),
            "notification_enabled": random.choice([True, False]),
            "auto_archive_days": random.choice([30, 60, 90, None]),
            "visibility": random.choice(["public", "private", "friends", "organization"]),
            "language": fake.language_code(),
        },
        # Add extra content to ensure we hit ~3KB for TOAST
        "description": fake.paragraph(nb_sentences=8),
        "notes": fake.paragraph(nb_sentences=5),
        "comments": [
            {
                "user": fake.name(),
                "text": fake.sentence(nb_words=10),
                "timestamp": fake.date_time_this_month().isoformat(),
            }
            for _ in range(random.randint(2, 5))
        ],
        "attachments": [
            {
                "filename": fake.file_name(),
                "size": random.randint(1000, 1000000),
                "type": random.choice(["image", "pdf", "doc", "spreadsheet"]),
            }
            for _ in range(random.randint(1, 3))
        ],
    }


def generate_rows(
    fake: Faker,
    count: int,
    batch_size: int,
) -> Generator[List[Dict[str, Any]], None, None]:
    """Generate rows in batches for efficient insertion."""
    batch = []
    for i in range(1, count + 1):
        doc = generate_large_jsonb_document(fake, i)
        batch.append(doc)
        
        if len(batch) >= batch_size:
            yield batch
            batch = []
    
    if batch:
        yield batch


def insert_documents_jsonb(conn, documents: List[Dict[str, Any]]) -> int:
    """Insert documents into documents_jsonb table."""
    with conn.cursor() as cursor:
        values = [(json.dumps(doc),) for doc in documents]
        args_str = ",".join(
            cursor.mogrify("(%s)", v).decode("utf-8") for v in values
        )
        cursor.execute(f"INSERT INTO {TABLE_JSONB} (data) VALUES {args_str}")
    return len(documents)


def insert_documents_jsonb_with_flags(conn, documents: List[Dict[str, Any]]) -> int:
    """Insert documents into documents_jsonb_with_flags table."""
    with conn.cursor() as cursor:
        values = [
            (
                doc.get("status", "pending"),
                doc.get("priority", 0),
                0,  # process_count
                json.dumps(doc),
            )
            for doc in documents
        ]
        args_str = ",".join(
            cursor.mogrify("(%s, %s, %s, %s)", v).decode("utf-8") for v in values
        )
        cursor.execute(
            f"INSERT INTO {TABLE_JSONB_FLAGS} (status, priority, process_count, data) VALUES {args_str}"
        )
    return len(documents)


def insert_documents_normalized(conn, documents: List[Dict[str, Any]]) -> int:
    """Insert documents into documents_normalized table."""
    with conn.cursor() as cursor:
        values = [
            (
                doc.get("title", ""),
                doc.get("body", ""),
                doc.get("status", "pending"),
                doc.get("priority", 0),
                doc.get("author", {}).get("name", ""),
                doc.get("author", {}).get("email", ""),
                doc.get("metadata", {}).get("category", ""),
                doc.get("metadata", {}).get("tags", []),
                doc.get("metrics", {}).get("view_count", 0),
                json.dumps({
                    "settings": doc.get("settings", {}),
                    "metrics": doc.get("metrics", {}),
                }),
            )
            for doc in documents
        ]
        args_str = ",".join(
            cursor.mogrify(
                "(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)", v
            ).decode("utf-8")
            for v in values
        )
        cursor.execute(
            f"""INSERT INTO {TABLE_NORMALIZED} 
                (title, body, status, priority, author_name, author_email, 
                 category, tags, view_count, metadata) 
                VALUES {args_str}"""
        )
    return len(documents)


def seed_table(
    table: str,
    count: int,
    batch_size: int,
    seed: int,
    config: DatabaseConfig,
) -> None:
    """Seed a specific table with deterministic data."""
    fake = create_faker(seed)
    
    insert_func = {
        TABLE_JSONB: insert_documents_jsonb,
        TABLE_JSONB_FLAGS: insert_documents_jsonb_with_flags,
        TABLE_NORMALIZED: insert_documents_normalized,
    }[table]
    
    print(f"\nSeeding {table} with {count:,} rows (seed={seed})...")
    
    with get_connection(config) as conn:
        # Truncate existing data
        with conn.cursor() as cursor:
            cursor.execute(f"TRUNCATE {table} RESTART IDENTITY CASCADE")
        conn.commit()
        
        # Insert in batches with progress bar
        total_inserted = 0
        with tqdm(total=count, desc=f"Inserting into {table}") as pbar:
            for batch in generate_rows(fake, count, batch_size):
                inserted = insert_func(conn, batch)
                conn.commit()
                total_inserted += inserted
                pbar.update(inserted)
        
        # Get final table size
        with conn.cursor() as cursor:
            cursor.execute(f"""
                SELECT 
                    pg_size_pretty(pg_relation_size('{table}')) as table_size,
                    pg_size_pretty(pg_total_relation_size('{table}')) as total_size,
                    pg_size_pretty(COALESCE(
                        pg_relation_size(
                            (SELECT reltoastrelid FROM pg_class WHERE relname = '{table}')
                        ), 0
                    )) as toast_size
            """)
            sizes = cursor.fetchone()
        
        print(f"  Table size: {sizes[0]}, TOAST size: {sizes[2]}, Total: {sizes[1]}")
        
        # ANALYZE to update statistics (critical for n_live_tup)
        print(f"  Running ANALYZE on {table}...")
        with conn.cursor() as cursor:
            cursor.execute(f"ANALYZE {table}")
        conn.commit()
        print(f"  Statistics updated")


def seed_all_tables(
    count: int,
    batch_size: int,
    seed: int,
    config: DatabaseConfig,
) -> None:
    """Seed all experiment tables with deterministic data."""
    tables = [TABLE_JSONB, TABLE_JSONB_FLAGS, TABLE_NORMALIZED]
    
    print(f"Seeding all tables with {count:,} rows each")
    print(f"Random seed: {seed}")
    print(f"Batch size: {batch_size}")
    
    for table in tables:
        # Reset seed for each table to ensure consistency
        seed_table(table, count, batch_size, seed, config)
    
    print("\n✓ All tables seeded successfully")


def main():
    parser = argparse.ArgumentParser(
        description="Seed experiment tables with deterministic test data"
    )
    parser.add_argument(
        "--table",
        choices=[TABLE_JSONB, TABLE_JSONB_FLAGS, TABLE_NORMALIZED, "all"],
        default="all",
        help="Table to seed (default: all)",
    )
    parser.add_argument(
        "--count",
        type=int,
        default=DEFAULT_ROW_COUNT,
        help=f"Number of rows to generate (default: {DEFAULT_ROW_COUNT:,})",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=DEFAULT_BATCH_SIZE,
        help=f"Batch size for inserts (default: {DEFAULT_BATCH_SIZE})",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=DEFAULT_RANDOM_SEED,
        help=f"Random seed for reproducibility (default: {DEFAULT_RANDOM_SEED})",
    )
    
    args = parser.parse_args()
    config = DatabaseConfig.from_env()
    
    start_time = datetime.now()
    
    if args.table == "all":
        seed_all_tables(args.count, args.batch_size, args.seed, config)
    else:
        seed_table(args.table, args.count, args.batch_size, args.seed, config)
    
    elapsed = datetime.now() - start_time
    print(f"\nTotal time: {elapsed}")


if __name__ == "__main__":
    main()
