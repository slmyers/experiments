#!/usr/bin/env python3
"""
Utility functions for the API server
"""

import csv
from pathlib import Path
from typing import List, Dict

def parse_csv_metrics(csv_path: Path) -> List[Dict]:
    """Parse metrics from a CSV file"""
    metrics = []
    
    with open(csv_path, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            metric = {}
            for key, value in row.items():
                # Convert to appropriate type
                if key in ['timestamp']:
                    metric[key] = value
                elif key in ['elapsed_seconds']:
                    metric[key] = float(value)
                else:
                    try:
                        metric[key] = int(value)
                    except (ValueError, TypeError):
                        metric[key] = value
            metrics.append(metric)
    
    return metrics

def format_size(bytes_value: int) -> str:
    """Format bytes to human readable format"""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if bytes_value < 1024.0:
            return f"{bytes_value:.2f} {unit}"
        bytes_value /= 1024.0
    return f"{bytes_value:.2f} PB"
