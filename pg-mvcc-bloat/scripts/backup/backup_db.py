#!/usr/bin/env python3
"""
PostgreSQL database backup using pg_dump.

Creates full database backups in custom format for efficient restoration.
"""
import argparse
import sys
import subprocess
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from common import DatabaseConfig


def backup_database(
    config: DatabaseConfig,
    backup_dir: Path,
    backup_name: str = None,
) -> Path:
    """
    Create a full database backup using pg_dump.
    
    Args:
        config: Database configuration
        backup_dir: Directory to store backups
        backup_name: Optional custom backup name (defaults to timestamp)
    
    Returns:
        Path to the created backup file
    """
    # Create backup directory if it doesn't exist
    backup_dir.mkdir(parents=True, exist_ok=True)
    
    # Generate backup filename
    if backup_name is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"backup_{timestamp}.dump"
    elif not backup_name.endswith('.dump'):
        backup_name = f"{backup_name}.dump"
    
    backup_path = backup_dir / backup_name
    
    print(f"Creating database backup: {backup_path}")
    print(f"Database: {config.database} on {config.host}:{config.port}")
    
    # Build pg_dump command
    # Using custom format (-Fc) for efficient compression and selective restore
    cmd = [
        "pg_dump",
        "-h", config.host,
        "-p", str(config.port),
        "-U", config.user,
        "-d", config.database,
        "-Fc",  # Custom format
        "-f", str(backup_path),
        "-v",  # Verbose
    ]
    
    # Set password environment variable
    env = {"PGPASSWORD": config.password}
    
    try:
        # Run pg_dump
        result = subprocess.run(
            cmd,
            env=env,
            capture_output=True,
            text=True,
            check=True
        )
        
        if result.stderr:
            print("pg_dump output:")
            print(result.stderr)
        
        # Get backup file size
        size_mb = backup_path.stat().st_size / (1024 * 1024)
        print(f"\n✓ Backup created successfully!")
        print(f"  Location: {backup_path}")
        print(f"  Size: {size_mb:.2f} MB")
        
        return backup_path
        
    except subprocess.CalledProcessError as e:
        print(f"✗ Backup failed!")
        print(f"Error: {e}")
        if e.stderr:
            print(f"Details: {e.stderr}")
        sys.exit(1)
    except Exception as e:
        print(f"✗ Unexpected error: {e}")
        sys.exit(1)


def list_backups(backup_dir: Path) -> list:
    """List all available database backups."""
    if not backup_dir.exists():
        return []
    
    backups = sorted(backup_dir.glob("*.dump"), reverse=True)
    return backups


def main():
    parser = argparse.ArgumentParser(
        description="Backup PostgreSQL database using pg_dump"
    )
    parser.add_argument(
        "--name",
        help="Custom backup name (default: timestamp-based)",
    )
    parser.add_argument(
        "--dir",
        default="backups/database",
        help="Backup directory (default: backups/database)",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List available backups",
    )
    
    args = parser.parse_args()
    
    # Resolve backup directory relative to project root
    project_root = Path(__file__).parent.parent.parent
    backup_dir = project_root / args.dir
    
    if args.list:
        backups = list_backups(backup_dir)
        if not backups:
            print(f"No backups found in {backup_dir}")
        else:
            print(f"Available backups in {backup_dir}:")
            for backup in backups:
                size_mb = backup.stat().st_size / (1024 * 1024)
                mtime = datetime.fromtimestamp(backup.stat().st_mtime)
                print(f"  - {backup.name} ({size_mb:.2f} MB, {mtime.strftime('%Y-%m-%d %H:%M:%S')})")
        return
    
    # Load database config
    config = DatabaseConfig.from_env()
    
    # Create backup
    backup_database(config, backup_dir, args.name)


if __name__ == "__main__":
    main()
