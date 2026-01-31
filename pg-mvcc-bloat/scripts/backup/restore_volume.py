#!/usr/bin/env python3
"""
Docker volume restoration from tarball snapshot.

Restores a PostgreSQL data volume from a tarball backup.
WARNING: This will replace all data in the volume!
"""
import argparse
import sys
import subprocess
from pathlib import Path


VOLUME_NAME = "pg-mvcc-data"
CONTAINER_NAME = "pg-mvcc-postgres"


def restore_volume(backup_path: Path) -> None:
    """
    Restore a Docker volume from a tarball backup.
    
    Args:
        backup_path: Path to the backup file (.tar.gz)
    """
    if not backup_path.exists():
        print(f"✗ Backup file not found: {backup_path}")
        sys.exit(1)
    
    print(f"Restoring Docker volume from: {backup_path}")
    print(f"Target volume: {VOLUME_NAME}")
    
    # Check if container is running
    check_container = ["docker", "ps", "-q", "-f", f"name={CONTAINER_NAME}"]
    result = subprocess.run(check_container, capture_output=True, text=True)
    
    if result.stdout.strip():
        print(f"\n✗ Container {CONTAINER_NAME} is currently running!")
        print("You must stop the container before restoring the volume.")
        print("Run: make down")
        sys.exit(1)
    
    # Confirm destructive operation
    print("\n⚠️  WARNING: This will REPLACE ALL DATA in the volume!")
    print(f"   Volume: {VOLUME_NAME}")
    response = input("\nType 'yes' to continue: ")
    if response.lower() != "yes":
        print("Restore cancelled.")
        return
    
    # Check if volume exists, create if not
    check_cmd = ["docker", "volume", "inspect", VOLUME_NAME]
    result = subprocess.run(check_cmd, capture_output=True)
    
    if result.returncode != 0:
        print(f"Creating volume {VOLUME_NAME}...")
        create_cmd = ["docker", "volume", "create", VOLUME_NAME]
        subprocess.run(create_cmd, check=True)
    else:
        # Volume exists, need to clear it first
        print("Clearing existing volume data...")
        clear_cmd = [
            "docker", "run", "--rm",
            "-v", f"{VOLUME_NAME}:/data",
            "alpine:latest",
            "sh", "-c", "rm -rf /data/* /data/.[!.]* /data/..?*"
        ]
        try:
            subprocess.run(clear_cmd, check=True, capture_output=True)
        except subprocess.CalledProcessError as e:
            print(f"Warning: Could not fully clear volume: {e}")
    
    # Restore volume from backup
    cmd = [
        "docker", "run", "--rm",
        "-v", f"{VOLUME_NAME}:/data",
        "-v", f"{backup_path.parent.absolute()}:/backup:ro",
        "alpine:latest",
        "tar", "xzf", f"/backup/{backup_path.name}",
        "-C", "/data"
    ]
    
    try:
        print("Extracting tarball to volume...")
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True
        )
        
        print(f"\n✓ Volume restored successfully!")
        print(f"  From: {backup_path}")
        print(f"  To: {VOLUME_NAME}")
        print(f"\nYou can now start the container with: make infra")
        
    except subprocess.CalledProcessError as e:
        print(f"✗ Volume restore failed!")
        print(f"Error: {e}")
        if e.stderr:
            print(f"Details: {e.stderr}")
        sys.exit(1)
    except Exception as e:
        print(f"✗ Unexpected error: {e}")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description="Restore Docker volume from tarball snapshot"
    )
    parser.add_argument(
        "backup",
        help="Backup file to restore (.tar.gz file)",
    )
    
    args = parser.parse_args()
    
    # Resolve backup path
    backup_path = Path(args.backup)
    if not backup_path.is_absolute():
        # Try relative to project root
        project_root = Path(__file__).parent.parent.parent
        backup_path = project_root / backup_path
    
    # Restore volume
    restore_volume(backup_path)


if __name__ == "__main__":
    main()
