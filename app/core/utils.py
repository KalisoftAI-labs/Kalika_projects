"""Utility functions for RCA Dashboard"""

import os
from pathlib import Path
from datetime import datetime
import pytz

def ensure_storage_dirs():
    """Create required storage directories"""
    from app.core.config import get_settings
    
    settings = get_settings()
    
    dirs = [
        settings.log_storage_path,
        settings.chart_storage_path,
    ]
    
    for dir_path in dirs:
        Path(dir_path).mkdir(parents=True, exist_ok=True)

def get_timestamp_utc() -> datetime:
    """Get current UTC timestamp"""
    return datetime.now(pytz.UTC)

def parse_timestamp(ts_str: str) -> datetime:
    """Parse ISO format timestamp"""
    try:
        return datetime.fromisoformat(ts_str.replace('Z', '+00:00'))
    except Exception:
        return get_timestamp_utc()

def format_timestamp(dt: datetime) -> str:
    """Format datetime to ISO string"""
    return dt.isoformat()
