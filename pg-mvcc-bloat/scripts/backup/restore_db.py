#!/usr/bin/env python3
"""
PostgreSQL database restoration using pg_restore.

Restores database backups created with pg_dump custom format.
"""
import argparse
import sys
import subprocess
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from common import DatabaseConfig


def restore_database(
    config: DatabaseConfig,
    backup_path: Path,
    clean: bool = False,
) -> None:
    """
    Restore a database from a pg_dump backup file.
    
    Args:
        config: Database configuration
        backup_path: Path to the backup file (.dump)
        clean: Whether to clean (drop) database objects before restoring
    """
    if not backup_path.exists():
        print(f"✗ Backup file not found: {backup_path}")
        sys.exit(1)
    
    print(f"Restoring database from: {backup_path}")
    print(f"Target database: {config.database} on {config.host}:{config.port}")
    
    if clean:
        print("WARNING: --clean flag will drop existing database objects!")
        response = input("Continue? (yes/no): ")
        if response.lower() != "yes":
            print("Restore cancelled.")
            return
    
    # Build pg_restore command
    cmd = [
        "pg_restore",
        "-h", config.host,
        "-p", str(config.port),
        "-U", config.user,
        "-d", config.database,
        "-v",  # Verbose
    ]
    
    if clean:
        cmd.append("-c")  # Clean (drop) database objects before recreating
    
    cmd.append(str(backup_path))
    
    # Set password environment variable
    env = {"PGPASSWORD": config.password}
    
    try:
        # Run pg_restore
        result = subprocess.run(
            cmd,
            env=env,
            capture_output=True,
            text=True,
            check=False  # Don't raise on non-zero exit (pg_restore returns warnings)
        )
        
        if result.stdout:
            print("pg_restore output:")
            print(result.stdout)
        
        if result.stderr:
            print("pg_restore messages:")
            print(result.stderr)
        
        # Check for actual errors (ignore warnings)
        if result.returncode != 0 and "ERROR" in result.stderr:
            print(f"\n✗ Restore completed with errors!")
            print(f"Exit code: {result.returncode}")
            sys.exit(1)
        
        print(f"\n✓ Database restored successfully!")
        print(f"  From: {backup_path}")
        print(f"  To: {config.database}")
        
    except Exception as e:
        print(f"✗ Restore failed: {e}")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description="Restore PostgreSQL database from pg_dump backup"
    )
    parser.add_argument(
        "backup",
        help="Backup file to restore (.dump file)",
    )
    parser.add_argument(
        "--clean",
        action="store_true",
        help="Clean (drop) database objects before restoring",
    )
    
    args = parser.parse_args()
    
    # Resolve backup path
    backup_path = Path(args.backup)
    if not backup_path.is_absolute():
        # Try relative to project root
        project_root = Path(__file__).parent.parent.parent
        backup_path = project_root / backup_path
    
    # Load database config
    config = DatabaseConfig.from_env()
    
    # Restore database
    restore_database(config, backup_path, args.clean)


if __name__ == "__main__":
    main()
