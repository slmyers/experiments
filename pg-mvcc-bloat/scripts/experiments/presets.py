"""
Experiment presets defining configurations for different scenarios.

Each preset specifies table, update pattern, workload ratio,
autovacuum settings, and duration.
"""
from dataclasses import dataclass, field
from typing import Dict, Any, Optional


@dataclass
class ExperimentPreset:
    """Configuration for a single experiment scenario."""
    name: str
    description: str
    
    # Target table
    table: str
    
    # Update pattern
    update_pattern: str
    
    # Workload configuration
    read_workers: int = 0
    write_workers: int = 1
    batch_size: int = 100
    rate_limit: Optional[float] = None  # Updates per second, None = unlimited
    
    # Timing
    duration_seconds: int = 300
    plan_capture_interval: int = 60
    
    # Autovacuum mode (disabled, aggressive, default)
    autovacuum_mode: str = "disabled"
    
    # Additional configuration
    extra_config: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def read_write_ratio(self) -> str:
        return f"{self.read_workers}:{self.write_workers}"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "table": self.table,
            "update_pattern": self.update_pattern,
            "read_workers": self.read_workers,
            "write_workers": self.write_workers,
            "batch_size": self.batch_size,
            "rate_limit": self.rate_limit,
            "duration_seconds": self.duration_seconds,
            "plan_capture_interval": self.plan_capture_interval,
            "autovacuum_mode": self.autovacuum_mode,
            "read_write_ratio": self.read_write_ratio,
            "extra_config": self.extra_config,
        }


# =============================================================================
# Experiment Presets
# =============================================================================

PRESETS: Dict[str, ExperimentPreset] = {}


def register_preset(preset: ExperimentPreset) -> ExperimentPreset:
    """Register a preset in the global registry."""
    PRESETS[preset.name] = preset
    return preset


# -----------------------------------------------------------------------------
# Bloat Demonstration Presets
# -----------------------------------------------------------------------------

register_preset(ExperimentPreset(
    name="bloat-demo",
    description="Demonstrate worst-case MVCC bloat with rapid JSONB mutations and disabled autovacuum",
    table="documents_jsonb",
    update_pattern="jsonb_mutation",
    read_workers=0,
    write_workers=2,
    batch_size=100,
    rate_limit=None,  # Maximum speed
    duration_seconds=300,
    autovacuum_mode="disabled",
))

register_preset(ExperimentPreset(
    name="bloat-demo-short",
    description="Quick bloat demo for testing (60 seconds)",
    table="documents_jsonb",
    update_pattern="jsonb_mutation",
    read_workers=0,
    write_workers=2,
    batch_size=100,
    rate_limit=None,
    duration_seconds=60,
    autovacuum_mode="disabled",
))

# -----------------------------------------------------------------------------
# TOAST Behavior Comparison Presets
# -----------------------------------------------------------------------------

register_preset(ExperimentPreset(
    name="toast-mutation",
    description="Updates that modify JSONB content, creating new TOAST entries",
    table="documents_jsonb",
    update_pattern="jsonb_mutation",
    read_workers=1,
    write_workers=2,
    batch_size=100,
    rate_limit=500,  # 500 updates/sec for controlled comparison
    duration_seconds=300,
    autovacuum_mode="disabled",
))

register_preset(ExperimentPreset(
    name="toast-reuse",
    description="Updates only scalar columns, reusing TOAST pointers (HOT update potential)",
    table="documents_jsonb_with_flags",
    update_pattern="flag_only",
    read_workers=1,
    write_workers=2,
    batch_size=100,
    rate_limit=500,
    duration_seconds=300,
    autovacuum_mode="disabled",
))

# -----------------------------------------------------------------------------
# Normalized Schema Comparison
# -----------------------------------------------------------------------------

register_preset(ExperimentPreset(
    name="normalized-stability",
    description="Normalized table with aggressive autovacuum showing stable performance",
    table="documents_normalized",
    update_pattern="normalized",
    read_workers=1,
    write_workers=2,
    batch_size=100,
    rate_limit=500,
    duration_seconds=300,
    autovacuum_mode="aggressive",
))

register_preset(ExperimentPreset(
    name="normalized-no-vacuum",
    description="Normalized table without autovacuum for comparison",
    table="documents_normalized",
    update_pattern="normalized",
    read_workers=1,
    write_workers=2,
    batch_size=100,
    rate_limit=500,
    duration_seconds=300,
    autovacuum_mode="disabled",
))

# -----------------------------------------------------------------------------
# Read/Write Workload Presets
# -----------------------------------------------------------------------------

register_preset(ExperimentPreset(
    name="read-heavy",
    description="Read-heavy workload (10:1 ratio) showing query degradation under light writes",
    table="documents_jsonb",
    update_pattern="jsonb_mutation",
    read_workers=10,
    write_workers=1,
    batch_size=50,
    rate_limit=100,  # Slow writes to allow reads to complete
    duration_seconds=300,
    plan_capture_interval=30,  # More frequent plan captures
    autovacuum_mode="disabled",
))

register_preset(ExperimentPreset(
    name="write-heavy",
    description="Write-heavy workload (1:10 ratio) showing rapid bloat accumulation",
    table="documents_jsonb",
    update_pattern="jsonb_mutation",
    read_workers=1,
    write_workers=10,
    batch_size=100,
    rate_limit=None,
    duration_seconds=300,
    autovacuum_mode="disabled",
))

register_preset(ExperimentPreset(
    name="balanced",
    description="Balanced read/write workload (5:5 ratio)",
    table="documents_jsonb",
    update_pattern="jsonb_mutation",
    read_workers=5,
    write_workers=5,
    batch_size=100,
    rate_limit=200,
    duration_seconds=300,
    autovacuum_mode="disabled",
))

# -----------------------------------------------------------------------------
# Vacuum Recovery Presets
# -----------------------------------------------------------------------------

register_preset(ExperimentPreset(
    name="vacuum-recovery",
    description="Run after bloat-demo to measure VACUUM FULL recovery",
    table="documents_jsonb",
    update_pattern="jsonb_mutation",
    read_workers=5,
    write_workers=0,  # Read-only to measure query performance
    batch_size=100,
    duration_seconds=60,
    autovacuum_mode="disabled",
    extra_config={
        "run_vacuum_full_before": True,
        "measure_vacuum_time": True,
    },
))

# -----------------------------------------------------------------------------
# Autovacuum Comparison Presets
# -----------------------------------------------------------------------------

# These presets use IDENTICAL workloads to show autovacuum impact
register_preset(ExperimentPreset(
    name="autovacuum-default",
    description="JSONB updates with default autovacuum settings (moderate workload)",
    table="documents_jsonb",
    update_pattern="jsonb_mutation",
    read_workers=2,
    write_workers=1,
    batch_size=50,
    rate_limit=50,  # Slow enough for default autovacuum
    duration_seconds=600,  # Longer to see autovacuum effects
    autovacuum_mode="default",
))

register_preset(ExperimentPreset(
    name="autovacuum-aggressive",
    description="JSONB updates with aggressive autovacuum (same rate as default for comparison)",
    table="documents_jsonb",
    update_pattern="jsonb_mutation",
    read_workers=2,
    write_workers=1,
    batch_size=50,
    rate_limit=50,  # Match autovacuum-default for fair comparison
    duration_seconds=600,
    autovacuum_mode="aggressive",
))

register_preset(ExperimentPreset(
    name="autovacuum-comparison-disabled",
    description="Same workload as autovacuum presets but with vacuum disabled (for comparison)",
    table="documents_jsonb",
    update_pattern="jsonb_mutation",
    read_workers=2,
    write_workers=1,
    batch_size=50,
    rate_limit=50,  # Same rate as other autovacuum presets
    duration_seconds=600,
    autovacuum_mode="disabled",
))


def get_preset(name: str) -> ExperimentPreset:
    """Get a preset by name."""
    if name not in PRESETS:
        available = ", ".join(sorted(PRESETS.keys()))
        raise ValueError(f"Unknown preset: {name}. Available: {available}")
    return PRESETS[name]


def list_presets() -> Dict[str, str]:
    """List all available presets with descriptions."""
    return {name: preset.description for name, preset in sorted(PRESETS.items())}


# -----------------------------------------------------------------------------
# HOT Update Comparison Presets
# -----------------------------------------------------------------------------

register_preset(ExperimentPreset(
    name="hot-updates-no-vacuum",
    description="HOT-eligible updates without autovacuum (should still benefit from HOT)",
    table="documents_jsonb_with_flags",
    update_pattern="flag_only",
    read_workers=2,
    write_workers=2,
    batch_size=100,
    rate_limit=200,
    duration_seconds=300,
    autovacuum_mode="disabled",
))

register_preset(ExperimentPreset(
    name="hot-updates-with-vacuum",
    description="HOT-eligible updates with autovacuum enabled (cleanup old versions)",
    table="documents_jsonb_with_flags",
    update_pattern="flag_only",
    read_workers=2,
    write_workers=2,
    batch_size=100,
    rate_limit=200,
    duration_seconds=300,
    autovacuum_mode="aggressive",
))

# -----------------------------------------------------------------------------
# Real-world Scenario Presets
# -----------------------------------------------------------------------------

register_preset(ExperimentPreset(
    name="production-simulation",
    description="Simulates production workload with balanced load and aggressive autovacuum",
    table="documents_jsonb",
    update_pattern="jsonb_mutation",
    read_workers=8,
    write_workers=2,
    batch_size=50,
    rate_limit=80,  # Slower writes to allow autovacuum to keep up
    duration_seconds=600,
    autovacuum_mode="aggressive",  # Need aggressive for JSONB bloat
))

register_preset(ExperimentPreset(
    name="high-churn-aggressive-vacuum",
    description="High-update scenario with aggressive autovacuum to prevent bloat",
    table="documents_jsonb",
    update_pattern="jsonb_mutation",
    read_workers=2,
    write_workers=4,
    batch_size=50,
    rate_limit=150,  # Moderate rate to allow vacuum cycles
    duration_seconds=600,
    autovacuum_mode="aggressive",
))

register_preset(ExperimentPreset(
    name="optimal-vacuum",
    description="Production workload with optimally tuned autovacuum settings",
    table="documents_jsonb",
    update_pattern="jsonb_mutation",
    read_workers=8,
    write_workers=3,
    batch_size=50,
    rate_limit=100,
    duration_seconds=900,  # Longer to see sustained performance
    autovacuum_mode="aggressive",
    extra_config={
        "monitor_buffer_cache": True,
        "monitor_index_bloat": True,
        "per_table_settings": {
            "documents_jsonb": {
                "autovacuum_vacuum_scale_factor": 0.02,  # 2% trigger
                "autovacuum_vacuum_threshold": 50,
                "autovacuum_vacuum_cost_delay": 5,  # Fast cleanup
                "autovacuum_naptime": 10,  # Check every 10 seconds
            }
        }
    },
))


def get_presets_for_comparison() -> Dict[str, list]:
    """Get preset groups for comparison experiments."""
    return {
        "toast_behavior": ["toast-mutation", "toast-reuse"],
        "schema_design": ["bloat-demo", "normalized-stability"],
        "workload_patterns": ["read-heavy", "write-heavy", "balanced"],
        "autovacuum_impact": ["autovacuum-comparison-disabled", "autovacuum-default", "autovacuum-aggressive"],
        "hot_updates": ["hot-updates-no-vacuum", "hot-updates-with-vacuum"],
        "production_scenarios": ["production-simulation", "high-churn-aggressive-vacuum", "optimal-vacuum"],
    }
