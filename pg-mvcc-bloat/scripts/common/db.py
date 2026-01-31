"""
Database configuration and connection utilities.
"""
import os
from dataclasses import dataclass
from contextlib import contextmanager
from typing import Generator

import psycopg2
from psycopg2.extras import RealDictCursor


@dataclass
class DatabaseConfig:
    """PostgreSQL connection configuration."""
    host: str = "localhost"
    port: int = 5432
    user: str = "experiment"
    password: str = "experiment_pass"
    database: str = "mvcc_experiment"
    
    @classmethod
    def from_env(cls) -> "DatabaseConfig":
        """Create config from environment variables."""
        return cls(
            host=os.getenv("PGHOST", "localhost"),
            port=int(os.getenv("PGPORT", "5432")),
            user=os.getenv("PGUSER", "experiment"),
            password=os.getenv("PGPASSWORD", "experiment_pass"),
            database=os.getenv("PGDATABASE", "mvcc_experiment"),
        )
    
    @property
    def connection_string(self) -> str:
        """Return psycopg2 connection string."""
        return f"postgresql://{self.user}:{self.password}@{self.host}:{self.port}/{self.database}"
    
    def to_dict(self) -> dict:
        """Return connection parameters as dict."""
        return {
            "host": self.host,
            "port": self.port,
            "user": self.user,
            "password": self.password,
            "dbname": self.database,
        }


@contextmanager
def get_connection(config: DatabaseConfig = None) -> Generator[psycopg2.extensions.connection, None, None]:
    """Get a database connection context manager."""
    if config is None:
        config = DatabaseConfig.from_env()
    
    conn = psycopg2.connect(**config.to_dict())
    try:
        yield conn
    finally:
        conn.close()


@contextmanager
def get_cursor(config: DatabaseConfig = None, dict_cursor: bool = True) -> Generator[psycopg2.extensions.cursor, None, None]:
    """Get a database cursor context manager."""
    cursor_factory = RealDictCursor if dict_cursor else None
    
    with get_connection(config) as conn:
        cursor = conn.cursor(cursor_factory=cursor_factory)
        try:
            yield cursor
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            cursor.close()


def run_migrations(config: DatabaseConfig = None, migrations_dir: str = None) -> None:
    """Run all SQL migrations in order."""
    import glob
    from pathlib import Path
    
    if migrations_dir is None:
        migrations_dir = Path(__file__).parent.parent.parent / "migrations"
    
    migration_files = sorted(glob.glob(str(migrations_dir / "*.sql")))
    
    with get_connection(config) as conn:
        with conn.cursor() as cursor:
            for migration_file in migration_files:
                print(f"Running migration: {migration_file}")
                with open(migration_file, 'r') as f:
                    sql = f.read()
                cursor.execute(sql)
            conn.commit()
    
    print(f"Successfully ran {len(migration_files)} migrations")
