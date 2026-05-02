"""Dashboard aggregation endpoints"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from typing import Dict

from app.storage.database import get_db
from app.models.schemas import MetricsSnapshot
from app.processors.metrics import MetricsProcessor

router = APIRouter()

@router.get("/metrics-snapshot")
async def get_metrics_snapshot(db: Session = Depends(get_db)) -> MetricsSnapshot:
    """
    Get current system metrics snapshot (last 1 minute)
    """
    now = datetime.utcnow()
    one_minute_ago = now - timedelta(minutes=1)
    
    if db is None:
        # Return demo metrics snapshot
        return MetricsSnapshot(
            timestamp=now,
            request_count=1839,
            error_count=444,
            error_rate=0.2415,
            p50_latency=45.2,
            p99_latency=234.5,
            p99_9_latency=1823.1,
            cpu_percent=45.2,
            memory_percent=62.8,
            disk_percent=58.5
        )
    
    processor = MetricsProcessor(db)
    
    # Aggregate across all components
    nginx_metrics = processor.aggregate_request_metrics('nginx', one_minute_ago, now)
    gunicorn_metrics = processor.aggregate_request_metrics('gunicorn', one_minute_ago, now)
    app_metrics = processor.aggregate_request_metrics('application', one_minute_ago, now)
    
    total_requests = (
        nginx_metrics['request_count'] +
        gunicorn_metrics['request_count'] +
        app_metrics['request_count']
    )
    
    total_errors = (
        nginx_metrics['error_count'] +
        gunicorn_metrics['error_count'] +
        app_metrics['error_count']
    )
    
    error_rate = total_errors / total_requests if total_requests > 0 else 0
    
    # Calculate mean latencies
    p50 = (nginx_metrics['p50_latency'] + gunicorn_metrics['p50_latency'] + app_metrics['p50_latency']) / 3
    p99 = (nginx_metrics['p99_latency'] + gunicorn_metrics['p99_latency'] + app_metrics['p99_latency']) / 3
    p999 = (nginx_metrics['p999_latency'] + gunicorn_metrics['p999_latency'] + app_metrics['p999_latency']) / 3
    
    return MetricsSnapshot(
        timestamp=now,
        request_count=total_requests,
        error_count=total_errors,
        error_rate=round(error_rate, 4),
        p50_latency=round(p50, 2),
        p99_latency=round(p99, 2),
        p99_9_latency=round(p999, 2),
        cpu_percent=45.2,
        memory_percent=62.8,
        disk_percent=58.5
    )

@router.get("/component-health")
async def get_component_health(db: Session = Depends(get_db)) -> Dict:
    """
    Get health status of all components
    """
    components = ['nginx', 'gunicorn', 'uvicorn', 'application']
    
    now = datetime.utcnow()
    five_mins_ago = now - timedelta(minutes=5)
    
    if db is None:
        # Return demo health status
        health_status = {
            "nginx": {
                "status": "healthy",
                "health_score": 95,
                "request_count": 1839,
                "error_rate": 0.2415,
                "p99_latency": 234.5,
            },
            "gunicorn": {
                "status": "healthy",
                "health_score": 92,
                "request_count": 0,
                "error_rate": 0,
                "p99_latency": 0,
            },
            "uvicorn": {
                "status": "healthy",
                "health_score": 93,
                "request_count": 0,
                "error_rate": 0,
                "p99_latency": 0,
            },
            "application": {
                "status": "healthy",
                "health_score": 91,
                "request_count": 0,
                "error_rate": 0,
                "p99_latency": 0,
            },
        }
        return health_status
    
    processor = MetricsProcessor(db)
    
    health_status = {}
    
    for component in components:
        metrics = processor.aggregate_request_metrics(component, five_mins_ago, now)
        
        # Determine health based on error rate and latency
        if metrics['request_count'] == 0:
            status = "no_data"
            health_score = 0
        else:
            error_rate = metrics['error_rate']
            p99_latency = metrics['p99_latency']
            
            # Simple health score calculation
            if error_rate > 0.1:
                status = "critical"
                health_score = 20
            elif error_rate > 0.05:
                status = "warning"
                health_score = 50
            elif p99_latency > 5000:
                status = "warning"
                health_score = 60
            else:
                status = "healthy"
                health_score = 95
        
        health_status[component] = {
            "status": status,
            "health_score": health_score,
            "request_count": metrics['request_count'],
            "error_rate": metrics['error_rate'],
            "p99_latency": metrics['p99_latency'],
        }
    
    return health_status

@router.get("/recent-incidents")
async def get_recent_incidents(limit: int = 10, db: Session = Depends(get_db)) -> Dict:
    """
    Get recent RCA incidents for dashboard display
    """
    if db is None:
        return {
            "total_incidents": 0,
            "incidents": [],
            "note": "Demo mode - database not available"
        }
    
    from app.models.orm import RCAAnalysis
    
    now = datetime.utcnow()
    one_day_ago = now - timedelta(days=1)
    
    incidents = db.query(RCAAnalysis).filter(
        RCAAnalysis.timestamp >= one_day_ago
    ).order_by(RCAAnalysis.timestamp.desc()).limit(limit).all()
    
    return {
        "total_incidents": len(incidents),
        "incidents": [
            {
                "incident_id": inc.incident_id,
                "incident_type": inc.incident_type,
                "severity": inc.severity,
                "timestamp": inc.timestamp.isoformat(),
                "root_cause": inc.root_cause,
                "confidence_score": inc.confidence_score,
            }
            for inc in incidents
        ]
    }
