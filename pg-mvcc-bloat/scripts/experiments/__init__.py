"""Experiment configuration and execution module."""
from .presets import (
    ExperimentPreset,
    PRESETS,
    get_preset,
    list_presets,
    get_presets_for_comparison,
)

__all__ = [
    "ExperimentPreset",
    "PRESETS",
    "get_preset",
    "list_presets",
    "get_presets_for_comparison",
]
