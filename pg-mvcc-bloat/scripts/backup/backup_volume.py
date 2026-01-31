#!/usr/bin/env python3
"""
Docker volume snapshot backup.

Creates a tarball snapshot of the PostgreSQL data volume.
This is a faster alternative to pg_dump for full database state preservation.
"""
import argparse
import sys
import subprocess
from datetime import datetime
from pathlib import Path


VOLUME_NAME = "pg-mvcc-data"
CONTAINER_NAME = "pg-mvcc-postgres"


def backup_volume(
    backup_dir: Path,
    backup_name: str = None,
) -> Path:
    """
    Create a snapshot of the Docker volume.
    
    Args:
        backup_dir: Directory to store volume backups
        backup_name: Optional custom backup name (defaults to timestamp)
    
    Returns:
        Path to the created backup file
    """
    # Create backup directory if it doesn't exist
    backup_dir.mkdir(parents=True, exist_ok=True)
    
    # Generate backup filename
    if backup_name is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"volume_{timestamp}.tar.gz"
    elif not backup_name.endswith('.tar.gz'):
        backup_name = f"{backup_name}.tar.gz"
    
    backup_path = backup_dir / backup_name
    
    print(f"Creating Docker volume snapshot: {backup_path}")
    print(f"Volume: {VOLUME_NAME}")
    
    # Check if volume exists
    check_cmd = ["docker", "volume", "inspect", VOLUME_NAME]
    result = subprocess.run(check_cmd, capture_output=True)
    if result.returncode != 0:
        print(f"✗ Volume {VOLUME_NAME} not found!")
        print("Make sure PostgreSQL container is running: make infra")
        sys.exit(1)
    
    # Check if container is running
    check_container = ["docker", "ps", "-q", "-f", f"name={CONTAINER_NAME}"]
    result = subprocess.run(check_container, capture_output=True, text=True)
    
    if not result.stdout.strip():
        print(f"WARNING: Container {CONTAINER_NAME} is not running.")
        print("For consistent backup, the database should be stopped or in recovery mode.")
        response = input("Continue anyway? (yes/no): ")
        if response.lower() != "yes":
            print("Backup cancelled.")
            return None
    else:
        print("NOTE: Container is running. For best consistency, stop writes before backup.")
    
    # Create volume backup using a temporary container
    # This mounts the volume and creates a tarball of its contents
    cmd = [
        "docker", "run", "--rm",
        "-v", f"{VOLUME_NAME}:/data:ro",  # Read-only mount
        "-v", f"{backup_path.parent.absolute()}:/backup",
        "alpine:latest",
        "tar", "czf", f"/backup/{backup_path.name}",
        "-C", "/data", "."
    ]
    
    try:
        print("Creating tarball snapshot...")
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True
        )
        
        # Get backup file size
        size_mb = backup_path.stat().st_size / (1024 * 1024)
        print(f"\n✓ Volume snapshot created successfully!")
        print(f"  Location: {backup_path}")
        print(f"  Size: {size_mb:.2f} MB")
        
        return backup_path
        
    except subprocess.CalledProcessError as e:
        print(f"✗ Volume backup failed!")
        print(f"Error: {e}")
        if e.stderr:
            print(f"Details: {e.stderr}")
        sys.exit(1)
    except Exception as e:
        print(f"✗ Unexpected error: {e}")
        sys.exit(1)


def list_backups(backup_dir: Path) -> list:
    """List all available volume backups."""
    if not backup_dir.exists():
        return []
    
    backups = sorted(backup_dir.glob("*.tar.gz"), reverse=True)
    return backups


def main():
    parser = argparse.ArgumentParser(
        description="Backup Docker volume as tarball snapshot"
    )
    parser.add_argument(
        "--name",
        help="Custom backup name (default: timestamp-based)",
    )
    parser.add_argument(
        "--dir",
        default="backups/volume",
        help="Backup directory (default: backups/volume)",
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
            print(f"Available volume backups in {backup_dir}:")
            for backup in backups:
                size_mb = backup.stat().st_size / (1024 * 1024)
                mtime = datetime.fromtimestamp(backup.stat().st_mtime)
                print(f"  - {backup.name} ({size_mb:.2f} MB, {mtime.strftime('%Y-%m-%d %H:%M:%S')})")
        return
    
    # Create backup
    backup_volume(backup_dir, args.name)


if __name__ == "__main__":
    main()
