"""Core configuration and settings"""

import os
from functools import lru_cache
from typing import Optional

class Settings:
    """Application settings"""
    
    # Database
    database_url: str = os.getenv(
        "DATABASE_URL",
        "postgresql+psycopg://rca_user:rca_password@localhost:5432/rca_dashboard"
    )
    database_pool_size: int = int(os.getenv("DATABASE_POOL_SIZE", "20"))
    database_max_overflow: int = int(os.getenv("DATABASE_MAX_OVERFLOW", "0"))
    
    # Logging
    log_level: str = os.getenv("LOG_LEVEL", "INFO")
    log_dir: str = os.getenv("LOG_DIR", "/var/log")
    
    # Processing
    metrics_aggregation_window: int = int(os.getenv("METRICS_AGGREGATION_WINDOW", "60"))  # seconds
    rca_correlation_window: int = int(os.getenv("RCA_CORRELATION_WINDOW", "300"))  # seconds
    max_log_file_size_mb: int = int(os.getenv("MAX_LOG_FILE_SIZE_MB", "5000"))
    
    # Storage
    log_storage_path: str = os.getenv("LOG_STORAGE_PATH", "./storage/logs")
    chart_storage_path: str = os.getenv("CHART_STORAGE_PATH", "./storage/charts")
    
    # API
    api_host: str = os.getenv("API_HOST", "0.0.0.0")
    api_port: int = int(os.getenv("API_PORT", "8000"))
    api_workers: int = int(os.getenv("API_WORKERS", "4"))
    
    # Visualization
    chart_dpi: int = int(os.getenv("CHART_DPI", "100"))
    chart_style: str = os.getenv("CHART_STYLE", "darkgrid")

@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance"""
    return Settings()

# Constants
class Constants:
    """System constants"""
    
    # Log source types
    LOG_SOURCE_NGINX = "nginx"
    LOG_SOURCE_GUNICORN = "gunicorn"
    LOG_SOURCE_UVICORN = "uvicorn"
    LOG_SOURCE_APPLICATION = "application"
    
    # HTTP Status Codes
    ERROR_4XX_MIN = 400
    ERROR_4XX_MAX = 499
    ERROR_5XX_MIN = 500
    ERROR_5XX_MAX = 599
    
    # Latency thresholds (milliseconds)
    LATENCY_THRESHOLD_SLOW = 1000  # > 1 second
    LATENCY_THRESHOLD_CRITICAL = 5000  # > 5 seconds
    
    # Time windows
    METRICS_WINDOW_1MIN = 60
    METRICS_WINDOW_5MIN = 300
    METRICS_WINDOW_1HOUR = 3600
    METRICS_WINDOW_1DAY = 86400
    
    # RCA event types
    RCA_EVENT_ERROR = "error"
    RCA_EVENT_LATENCY = "latency"
    RCA_EVENT_TIMEOUT = "timeout"
    RCA_EVENT_CRASH = "crash"
    RCA_EVENT_RESOURCE = "resource"
    RCA_EVENT_UPSTREAM = "upstream"
