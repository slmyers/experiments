"""
Common utilities and constants.
"""
from pathlib import Path

# Project paths
PROJECT_ROOT = Path(__file__).parent.parent.parent
MIGRATIONS_DIR = PROJECT_ROOT / "migrations"
OUTPUT_DIR = PROJECT_ROOT / "output"
METRICS_DIR = OUTPUT_DIR / "metrics"
PLANS_DIR = OUTPUT_DIR / "plans"
REPORTS_DIR = OUTPUT_DIR / "reports"

# Ensure output directories exist
for directory in [OUTPUT_DIR, METRICS_DIR, PLANS_DIR, REPORTS_DIR]:
    directory.mkdir(parents=True, exist_ok=True)


# Table names
TABLE_JSONB = "documents_jsonb"
TABLE_JSONB_FLAGS = "documents_jsonb_with_flags"
TABLE_NORMALIZED = "documents_normalized"

ALL_TABLES = [TABLE_JSONB, TABLE_JSONB_FLAGS, TABLE_NORMALIZED]


# Default experiment settings
DEFAULT_RANDOM_SEED = 42
DEFAULT_ROW_COUNT = 1_000_000
DEFAULT_BATCH_SIZE = 1000
DEFAULT_DURATION_SECONDS = 300
DEFAULT_POLL_INTERVAL = None  # Calculated as duration / 60


def get_run_id(preset_name: str) -> str:
    """Generate a run ID with preset name and timestamp."""
    from datetime import datetime
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{preset_name}_{timestamp}"


def get_poll_interval(duration_seconds: int, override: int = None) -> float:
    """Calculate polling interval for ~60 data points, with minimum of 1 second."""
    if override is not None:
        return override
    return max(1.0, duration_seconds / 60)


def sizeof_fmt(num: float, suffix: str = "B") -> str:
    """Format bytes to human readable string."""
    for unit in ("", "Ki", "Mi", "Gi", "Ti", "Pi", "Ei", "Zi"):
        if abs(num) < 1024.0:
            return f"{num:3.1f}{unit}{suffix}"
        num /= 1024.0
    return f"{num:.1f}Yi{suffix}"
