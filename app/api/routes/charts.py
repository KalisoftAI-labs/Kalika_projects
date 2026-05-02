"""Chart generation and caching endpoints"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from typing import Dict
import logging

from app.storage.database import get_db
from app.processors.metrics import MetricsProcessor
from app.visualization.charts import ChartGenerator

logger = logging.getLogger(__name__)

router = APIRouter()

@router.get("/error-trend")
async def get_error_trend_chart(
    component: str,
    start_time: datetime,
    end_time: datetime,
    db: Session = Depends(get_db)
) -> Dict:
    """
    Generate error rate trend chart
    """
    processor = MetricsProcessor(db)
    trend = processor.get_error_rate_trend(component, start_time, end_time)
    
    generator = ChartGenerator()
    chart_base64 = generator.generate_error_trend_chart(
        trend,
        title=f"Error Rate Trend - {component}"
    )
    
    return {
        "chart_type": "error_trend",
        "component": component,
        "image": f"data:image/png;base64,{chart_base64}",
        "generated_at": datetime.utcnow().isoformat()
    }

@router.get("/latency-distribution")
async def get_latency_distribution_chart(
    component: str,
    start_time: datetime,
    end_time: datetime,
    db: Session = Depends(get_db)
) -> Dict:
    """
    Generate latency distribution chart
    """
    from app.models.orm import LogEntry
    
    logs = db.query(LogEntry).filter(
        LogEntry.source == component,
        LogEntry.timestamp >= start_time,
        LogEntry.timestamp <= end_time,
        LogEntry.response_time.isnot(None)
    ).all()
    
    latencies = [log.response_time for log in logs]
    
    generator = ChartGenerator()
    chart_base64 = generator.generate_latency_distribution_chart(
        latencies,
        title=f"Latency Distribution - {component}"
    )
    
    return {
        "chart_type": "latency_distribution",
        "component": component,
        "data_points": len(latencies),
        "image": f"data:image/png;base64,{chart_base64}",
        "generated_at": datetime.utcnow().isoformat()
    }

@router.get("/errors-by-status")
async def get_errors_by_status_chart(
    component: str,
    start_time: datetime,
    end_time: datetime,
    db: Session = Depends(get_db)
) -> Dict:
    """
    Generate chart of errors by HTTP status code
    """
    processor = MetricsProcessor(db)
    error_dist = processor.aggregate_error_by_status(component, start_time, end_time)
    
    generator = ChartGenerator()
    chart_base64 = generator.generate_error_by_status_chart(
        error_dist,
        title=f"Errors by Status Code - {component}"
    )
    
    return {
        "chart_type": "errors_by_status",
        "component": component,
        "image": f"data:image/png;base64,{chart_base64}",
        "generated_at": datetime.utcnow().isoformat()
    }

@router.get("/latency-by-endpoint")
async def get_latency_by_endpoint_chart(
    component: str,
    start_time: datetime,
    end_time: datetime,
    db: Session = Depends(get_db)
) -> Dict:
    """
    Generate latency comparison by endpoint
    """
    processor = MetricsProcessor(db)
    endpoints_data = processor.aggregate_latency_by_endpoint(component, start_time, end_time)
    
    generator = ChartGenerator()
    chart_base64 = generator.generate_latency_by_endpoint_chart(
        endpoints_data,
        title=f"Latency by Endpoint (p99) - {component}"
    )
    
    return {
        "chart_type": "latency_by_endpoint",
        "component": component,
        "endpoints": len(endpoints_data),
        "image": f"data:image/png;base64,{chart_base64}",
        "generated_at": datetime.utcnow().isoformat()
    }

@router.get("/system-health")
async def get_system_health_chart(
    start_time: datetime,
    end_time: datetime,
    db: Session = Depends(get_db)
) -> Dict:
    """
    Generate system health metrics visualization
    """
    from app.models.orm import SystemMetric
    
    metrics = db.query(SystemMetric).filter(
        SystemMetric.timestamp >= start_time,
        SystemMetric.timestamp <= end_time
    ).order_by(SystemMetric.timestamp.asc()).all()
    
    metrics_data = [
        {
            'cpu_percent': m.cpu_percent or 0,
            'memory_percent': m.memory_percent or 0,
            'disk_percent': m.disk_percent or 0,
            'load_average_1min': m.load_average_1min or 0,
            'load_average_5min': m.load_average_5min or 0,
            'load_average_15min': m.load_average_15min or 0,
        }
        for m in metrics
    ]
    
    generator = ChartGenerator()
    chart_base64 = generator.generate_system_health_chart(metrics_data)
    
    return {
        "chart_type": "system_health",
        "image": f"data:image/png;base64,{chart_base64}",
        "generated_at": datetime.utcnow().isoformat()
    }

@router.get("/request-volume")
async def get_request_volume_chart(
    component: str,
    start_time: datetime,
    end_time: datetime,
    db: Session = Depends(get_db)
) -> Dict:
    """
    Generate request volume timeline
    """
    processor = MetricsProcessor(db, window_size=60)
    
    current = start_time
    volume_data = []
    
    while current < end_time:
        window_end = current + timedelta(seconds=60)
        metrics = processor.aggregate_request_metrics(component, current, window_end)
        volume_data.append((current, metrics['request_count']))
        current = window_end
    
    generator = ChartGenerator()
    chart_base64 = generator.generate_request_volume_chart(
        volume_data,
        title=f"Request Volume - {component}"
    )
    
    return {
        "chart_type": "request_volume",
        "component": component,
        "image": f"data:image/png;base64,{chart_base64}",
        "generated_at": datetime.utcnow().isoformat()
    }
