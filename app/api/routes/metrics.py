"""Metrics endpoints"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from typing import Dict

from app.storage.database import get_db
from app.processors.metrics import MetricsProcessor

router = APIRouter()

@router.get("/request-metrics")
async def get_request_metrics(
    component: str,
    start_time: datetime,
    end_time: datetime,
    db: Session = Depends(get_db)
) -> Dict:
    """
    Get aggregated request metrics for a component
    
    Returns:
        request_count, error_count, error_rate, p50_latency, p99_latency, p999_latency
    """
    if db is None:
        # Return demo metrics
        return {
            "request_count": 1839,
            "error_count": 444,
            "error_rate": 0.241,
            "p50_latency": 45.2,
            "p99_latency": 234.5,
            "p999_latency": 1823.1,
            "note": "Demo data - database not available"
        }
    
    processor = MetricsProcessor(db)
    metrics = processor.aggregate_request_metrics(component, start_time, end_time)
    return metrics

@router.get("/error-distribution")
async def get_error_distribution(
    component: str,
    start_time: datetime,
    end_time: datetime,
    db: Session = Depends(get_db)
) -> Dict[int, int]:
    """
    Get error count distribution by HTTP status code
    """
    if db is None:
        # Return demo error distribution
        return {
            "400": 58,
            "403": 34,
            "404": 352,
            "note": "Demo data - database not available"
        }
    
    processor = MetricsProcessor(db)
    distribution = processor.aggregate_error_by_status(component, start_time, end_time)
    return distribution

@router.get("/latency-by-endpoint")
async def get_latency_by_endpoint(
    component: str,
    start_time: datetime,
    end_time: datetime,
    db: Session = Depends(get_db)
) -> Dict:
    """
    Get latency metrics aggregated by endpoint
    """
    if db is None:
        # Return demo latency data
        return {
            "/": {"p50": 45, "p99": 234, "p999": 1823},
            "/cart/view/": {"p50": 52, "p99": 412, "p999": 2341},
            "/robots.txt": {"p50": 23, "p99": 98, "p999": 456},
            "note": "Demo data - database not available"
        }
    
    processor = MetricsProcessor(db)
    endpoints = processor.aggregate_latency_by_endpoint(component, start_time, end_time)
    return endpoints

@router.get("/slow-requests")
async def get_slow_requests(
    component: str,
    start_time: datetime,
    end_time: datetime,
    threshold_ms: int = 1000,
    db: Session = Depends(get_db)
) -> list:
    """
    Get requests exceeding latency threshold
    """
    if db is None:
        return []
    
    processor = MetricsProcessor(db)
    slow_requests = processor.identify_slow_requests(
        component, start_time, end_time, threshold_ms
    )
    return slow_requests

@router.get("/error-rate-trend")
async def get_error_rate_trend(
    component: str,
    start_time: datetime,
    end_time: datetime,
    db: Session = Depends(get_db)
) -> list:
    """
    Get error rate trend over time (windowed)
    """
    if db is None:
        return []
    
    processor = MetricsProcessor(db)
    trend = processor.get_error_rate_trend(component, start_time, end_time)
    
    return [
        {"timestamp": ts.isoformat(), "error_rate": rate}
        for ts, rate in trend
    ]

@router.get("/latency-trend")
async def get_latency_trend(
    component: str,
    start_time: datetime,
    end_time: datetime,
    percentile: float = 0.99,
    db: Session = Depends(get_db)
) -> list:
    """
    Get latency percentile trend over time
    """
    if db is None:
        return []
    
    processor = MetricsProcessor(db)
    trend = processor.get_latency_trend(component, start_time, end_time, percentile)
    
    return [
        {"timestamp": ts.isoformat(), "latency_ms": latency}
        for ts, latency in trend
    ]
